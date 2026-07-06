import logging
import os
import sys
from datetime import date as date_type
from enum import Enum

from dotenv import load_dotenv

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_api_dir = os.path.dirname(os.path.abspath(__file__))
for _p in [_project_root, _api_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

load_dotenv(os.path.join(_project_root, ".env"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

import io
from typing import Optional

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_NAME,
    create_access_token,
    get_current_user,
    get_user_by_email,
    require_manager,
    verify_password,
)
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from agents.execution_agent import run_execution_agent
from agents.report_agent import run_report_agent
from chromadb_setup.setup import setup_chromadb
from data.database import (
    _connection,
    get_all_requests,
    get_latest_meeting_report,
    get_request_by_id,
    get_requests_by_user,
    init_db,
    insert_request,
    is_valid_transition,
    save_meeting_report,
    update_request_after_clarification,
    update_request_priority,
    update_request_status,
)
from graph.workflow import run_workflow

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Awla API",
    description="AI-powered internal data request governance",
    version="2.0.0",
)

# ── Rate limiting ────────────────────────────────────────────────────────────
# Protects the login endpoint from credential-stuffing and the LLM-triggering
# endpoints from unbounded cost amplification (audit finding H1).

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Restricted to an explicit allowlist instead of "*" (audit finding M1).
# ALLOWED_ORIGINS is a comma-separated list; defaults cover local dev only.
# allow_credentials=True is required for the httpOnly auth cookie (H14) to
# be sent cross-origin from the React dev server -- this is only safe
# because allow_origins is an explicit list, never "*", which browsers
# reject combining with credentials anyway.

_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
] or ["http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Initialise DB tables and (non-production only) seed demo users on startup
init_db()

# Built once at startup and reused for every request (previously nothing
# ever built or attached a Chroma client to the workflow at all -- see
# graph/workflow.py's run_workflow docstring and audit finding C9).
_chroma_client = setup_chromadb()


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class RequestFormat(str, Enum):
    dashboard = "Dashboard"
    excel = "Excel"
    pdf = "PDF"


class RequestStatusEnum(str, Enum):
    pending_clarification = "pending_clarification"
    pending_approval = "pending_approval"
    open = "open"
    in_progress = "in_progress"
    overdue = "overdue"
    completed = "completed"
    rejected = "rejected"


def _validate_iso_date(v: str) -> str:
    try:
        date_type.fromisoformat(v)
    except (ValueError, TypeError):
        raise ValueError("must be an ISO date string, e.g. 2026-07-05")
    return v


class RequestSubmission(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    department: Optional[str] = ""
    report_type: str = Field(..., max_length=100)
    format: RequestFormat
    deadline: str
    days_open: Optional[int] = 0

    @field_validator("deadline")
    @classmethod
    def _deadline_is_date(cls, v):
        return _validate_iso_date(v)


class ClarificationSubmission(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000)


class StatusUpdate(BaseModel):
    status: RequestStatusEnum


class PriorityUpdate(BaseModel):
    score: float = Field(..., ge=1.0, le=10.0)
    reason: Optional[str] = Field("", max_length=1000)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_analysis(data: dict):
    """Run the LLM workflow and return (clarification, priority) dicts."""
    result = run_workflow(data, chroma_client=_chroma_client)
    clarification = result.get("clarification_result", {})
    priority = result.get("priority_result", {})
    return clarification, _sanitize_priority(priority)


def _require_ownership(current_user: dict, req: dict):
    if current_user["role"] != "manager" and req.get("submitted_by") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")


def _sanitize_priority(priority: dict) -> dict:
    """Defense-in-depth against prompt injection or a malformed LLM
    response manipulating the persisted priority score (audit finding C6):
    clamps the score to [1, 10] and validates the recommendation
    server-side regardless of what the agent returned, instead of trusting
    the LLM's output verbatim."""
    if not isinstance(priority, dict):
        priority = {}
    try:
        score = float(priority.get("score", 0) or 0)
    except (TypeError, ValueError):
        score = 0.0
    score = round(max(1.0, min(10.0, score)) if score else 1.0, 1)

    rec = priority.get("recommendation")
    if rec not in ("HIGH", "MEDIUM", "LOW"):
        rec = "HIGH" if score >= 8 else "MEDIUM" if score >= 5 else "LOW"

    reasons = priority.get("reasons")
    reasons = reasons[:5] if isinstance(reasons, list) else []

    rag_references = priority.get("rag_references")
    rag_references = rag_references[:5] if isinstance(rag_references, list) else []

    return {
        "score": score,
        "recommendation": rec,
        "reasons": reasons,
        "rag_references": rag_references,
    }


@app.get("/")
def root():
    return {"system": "Awla API", "version": "2.0.0"}


@app.get("/health")
def health():
    try:
        with _connection() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        logger.exception("Health check: database connectivity failed")
        db_ok = False
    body = {"status": "ok" if db_ok else "degraded", "database": db_ok}
    return JSONResponse(status_code=200 if db_ok else 503, content=body)


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
@limiter.limit("10/minute")
def login(request: Request, response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token({"sub": user["email"]})
    # httpOnly cookie for the React browser client (audit finding H14) --
    # JS can't read this, so an XSS bug can no longer exfiltrate the
    # session token the way it could from localStorage. Also returned in
    # the response body for non-browser clients (tests, curl, scripts)
    # that authenticate via a plain Authorization header instead.
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("ENVIRONMENT", "development").lower() == "production",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "department": user["department"],
        },
    }


@app.post("/api/auth/logout")
def logout(response: Response):
    # JS cannot delete an httpOnly cookie itself, so the server has to.
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "name": current_user["name"],
        "email": current_user["email"],
        "role": current_user["role"],
        "department": current_user["department"],
    }


# ── Request endpoints ─────────────────────────────────────────────────────────

@app.post("/api/requests", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def submit_request(
    request: Request,
    data: RequestSubmission,
    current_user: dict = Depends(get_current_user),
):
    # Department always comes from the logged-in user's profile
    req_data = {
        **data.model_dump(),
        "format": data.format.value,
        "department": current_user["department"],
        "submitted_by": current_user["id"],
        "submitted_by_name": current_user["name"],
        "submitted_by_department": current_user["department"],
        "status": "pending_clarification",
        "priority_score": 0,
        "recommendation": "MEDIUM",
        "reasons": [],
    }
    req_id = insert_request(req_data)

    try:
        clarification, priority = _run_analysis(req_data)
    except Exception:
        logger.exception("AI workflow failed for request %s; leaving pending_clarification", req_id)
        return {
            "id": req_id,
            "status": "pending_clarification",
            "clarification": {"status": "incomplete", "questions": [
                "Our AI assistant is temporarily unavailable. Please resubmit "
                "your description in a moment to continue."
            ]},
            "priority": None,
        }

    clarification_status = clarification.get("status", "incomplete")
    questions = clarification.get("questions", [])

    if clarification_status == "incomplete" and questions:
        return {
            "id": req_id,
            "status": "pending_clarification",
            "clarification": {"status": "incomplete", "questions": questions},
            "priority": None,
        }

    update_request_after_clarification(
        req_id,
        description=data.description,
        status="pending_approval",
        priority_score=priority.get("score", 0),
        recommendation=priority.get("recommendation", "MEDIUM"),
        reasons=priority.get("reasons", []),
    )
    return {
        "id": req_id,
        "status": "pending_approval",
        "clarification": {"status": "complete", "questions": []},
        "priority": {
            "score": priority.get("score", 0),
            "recommendation": priority.get("recommendation", "MEDIUM"),
            "reasons": priority.get("reasons", []),
            "rag_references": priority.get("rag_references", []),
        },
    }


@app.post("/api/requests/{request_id}/clarification")
@limiter.limit("20/minute")
def submit_clarification(
    request: Request,
    request_id: int,
    data: ClarificationSubmission,
    current_user: dict = Depends(get_current_user),
):
    req = get_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _require_ownership(current_user, req)

    # A request can only be re-clarified while it's actually awaiting
    # clarification — otherwise a submitter could resurrect a rejected or
    # completed request by calling this endpoint (audit finding H12).
    if req["status"] != "pending_clarification":
        raise HTTPException(
            status_code=409,
            detail=f"Request is '{req['status']}' and is not awaiting clarification",
        )

    workflow_data = {**req, "description": data.description}
    try:
        clarification, priority = _run_analysis(workflow_data)
    except Exception:
        logger.exception("AI workflow failed for clarification on request %s", request_id)
        raise HTTPException(status_code=502, detail="AI assistant is temporarily unavailable")

    clarification_status = clarification.get("status", "incomplete")
    questions = clarification.get("questions", [])

    if clarification_status == "incomplete" and questions:
        update_request_after_clarification(
            request_id, data.description, "pending_clarification", 0, "MEDIUM", []
        )
        return {
            "id": request_id,
            "status": "pending_clarification",
            "clarification": {"status": "incomplete", "questions": questions},
            "priority": None,
        }

    update_request_after_clarification(
        request_id,
        description=data.description,
        status="pending_approval",
        priority_score=priority.get("score", 0),
        recommendation=priority.get("recommendation", "MEDIUM"),
        reasons=priority.get("reasons", []),
    )
    return {
        "id": request_id,
        "status": "pending_approval",
        "clarification": {"status": "complete", "questions": []},
        "priority": {
            "score": priority.get("score", 0),
            "recommendation": priority.get("recommendation", "MEDIUM"),
            "reasons": priority.get("reasons", []),
            "rag_references": priority.get("rag_references", []),
        },
    }


@app.get("/api/requests")
def list_requests(current_user: dict = Depends(get_current_user)):
    if current_user["role"] == "manager":
        return get_all_requests()
    return get_requests_by_user(current_user["id"])


@app.get("/api/requests/{request_id}")
def get_single_request(request_id: int, current_user: dict = Depends(get_current_user)):
    req = get_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _require_ownership(current_user, req)
    return req


def _transition_or_409(req: dict, new_status: str):
    if not is_valid_transition(req["status"], new_status):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move request from '{req['status']}' to '{new_status}'",
        )


@app.patch("/api/requests/{request_id}/approve")
def approve_request(request_id: int, current_user: dict = Depends(require_manager)):
    req = get_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _transition_or_409(req, "open")
    update_request_status(request_id, "open")
    return {"id": request_id, "status": "open"}


@app.patch("/api/requests/{request_id}/reject")
def reject_request(request_id: int, current_user: dict = Depends(require_manager)):
    req = get_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _transition_or_409(req, "rejected")
    update_request_status(request_id, "rejected")
    return {"id": request_id, "status": "rejected"}


@app.patch("/api/requests/{request_id}/status")
def set_status(
    request_id: int,
    body: StatusUpdate,
    current_user: dict = Depends(require_manager),
):
    req = get_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _transition_or_409(req, body.status.value)
    update_request_status(request_id, body.status.value)
    return {"id": request_id, "status": body.status.value}


@app.patch("/api/requests/{request_id}/priority")
def set_priority(
    request_id: int,
    body: PriorityUpdate,
    current_user: dict = Depends(require_manager),
):
    req = get_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    update_request_priority(request_id, body.score, body.reason)
    return {"id": request_id, "priority_score": body.score}


# ── Report endpoint ───────────────────────────────────────────────────────────

@app.post("/api/reports/meeting", status_code=status.HTTP_201_CREATED)
def meeting_report(current_user: dict = Depends(require_manager)):
    all_reqs = get_all_requests()
    report_data = [
        {
            "title":          r["title"],
            "status":         r["status"],
            "priority_score": r["priority_score"],
            "days_open":      r.get("days_open", 0),
            "department":     r["department"],
        }
        for r in all_reqs
    ]
    result = run_report_agent(report_data)
    save_meeting_report(result)
    return result


@app.get("/api/reports/meeting/latest")
def latest_meeting_report(current_user: dict = Depends(require_manager)):
    report, created_at = get_latest_meeting_report()
    if report is None:
        return {"report": None, "created_at": None}
    return {"report": report, "created_at": created_at}


# ── Charts endpoint ───────────────────────────────────────────────────────────

@app.get("/api/requests/{request_id}/charts")
def get_charts(request_id: int, current_user: dict = Depends(get_current_user)):
    req = get_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _require_ownership(current_user, req)

    result = run_execution_agent(req)
    if "error" in result:
        logger.error("get_charts failed for request %s: %s", request_id, result["error"])
        raise HTTPException(status_code=500, detail="Report generation failed")

    return {
        "report_title": result["report_title"],
        "chart_type":   result["chart_type"],
        "group_by":     result["group_by"],
        "metric":       result["metric"],
        "data":         result["data"].to_dict(orient="records"),
        "summary":      result.get("summary", ""),
    }


@app.get("/api/requests/{request_id}/execute")
def execute_request(request_id: int, current_user: dict = Depends(get_current_user)):
    """
    Runs the execution agent and returns the output in the format
    the requester originally asked for: Dashboard (JSON), Excel, or PDF.
    """
    req = get_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _require_ownership(current_user, req)

    result = run_execution_agent(req)
    if "error" in result:
        logger.error("execute_request failed for request %s: %s", request_id, result["error"])
        raise HTTPException(status_code=500, detail="Report generation failed")

    fmt = (req.get("format") or "Dashboard").strip()
    df = result["data"]
    safe_title = result["report_title"].replace(" ", "_").replace("/", "-")

    # ── Excel ────────────────────────────────────────────────────────────────
    if fmt == "Excel":
        import pandas as _pd
        buf = io.BytesIO()
        with _pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Report")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.xlsx"'},
        )

    # ── PDF ──────────────────────────────────────────────────────────────────
    if fmt == "PDF":
        from fpdf import FPDF

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, result["report_title"], ln=True, align="C")
        pdf.ln(4)

        # Summary
        if result.get("summary"):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 6, result["summary"])
            pdf.ln(4)

        # Table header
        cols = list(df.columns)
        col_w = min(180 // len(cols), 60)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(79, 70, 229)
        pdf.set_text_color(255, 255, 255)
        for col in cols:
            pdf.cell(col_w, 8, str(col).upper(), border=1, fill=True)
        pdf.ln()

        # Table rows
        pdf.set_font("Helvetica", "", 9)
        for i, (_, row) in enumerate(df.iterrows()):
            pdf.set_fill_color(249, 250, 251) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(30, 30, 30)
            for col in cols:
                val = str(round(row[col], 2)) if isinstance(row[col], float) else str(row[col])
                pdf.cell(col_w, 7, val, border=1, fill=True)
            pdf.ln()

        buf = io.BytesIO(pdf.output())
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
        )

    # ── Dashboard (default) ──────────────────────────────────────────────────
    return {
        "report_title": result["report_title"],
        "chart_type":   result["chart_type"],
        "group_by":     result["group_by"],
        "metric":       result["metric"],
        "data":         df.to_dict(orient="records"),
        "summary":      result.get("summary", ""),
    }
