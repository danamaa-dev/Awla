import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { submitRequest, submitClarification, approveRequest, rejectRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import PriorityBadge from '../components/PriorityBadge'

const DEPARTMENTS  = ['Finance', 'HR', 'Operations', 'Marketing', 'Sales', 'Security', 'Procurement', 'Other']
const REPORT_TYPES = ['Sales', 'HR', 'Finance', 'Operations', 'Security', 'Analytics', 'Other']
const FORMATS = ['Excel', 'Dashboard', 'PDF']

function todayStr() {
  return new Date().toISOString().split('T')[0]
}

const AGENT_STEPS = [
  {
    key: 'clarification',
    name: 'Clarification Agent',
    detail: 'Checks whether the request contains enough detail to proceed.',
  },
  {
    key: 'priority',
    name: 'Priority Agent',
    detail: 'Scores urgency and business impact against organizational policies.',
  },
  {
    key: 'decision',
    name: 'Decision',
    detail: 'Manager reviews the AI analysis and approves or rejects.',
  },
]

function AgentProgress({ activeStep, doneSteps }) {
  return (
    <div className="agent-steps">
      {AGENT_STEPS.map((step, i) => {
        const isDone   = doneSteps.includes(step.key)
        const isActive = activeStep === step.key
        return (
          <div key={step.key} className="agent-step">
            <div className={`step-icon ${isDone ? 'done-icon' : isActive ? 'active' : 'idle'}`}>
              {isDone ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              ) : i + 1}
            </div>
            <div className="step-body">
              <div className="step-name" style={{
                color: isDone ? 'var(--success)' : isActive ? 'var(--accent-indigo)' : 'var(--text-heading)',
              }}>
                {step.name}
                {isActive && (
                  <span style={{ marginLeft: '8px', display: 'inline-flex', gap: '3px', verticalAlign: 'middle' }}>
                    <span className="pulse-dot" style={{ animationDelay: '0s' }} />
                    <span className="pulse-dot" style={{ animationDelay: '0.2s' }} />
                    <span className="pulse-dot" style={{ animationDelay: '0.4s' }} />
                  </span>
                )}
              </div>
              <div className="step-detail">{step.detail}</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function NewRequest() {
  const navigate   = useNavigate()
  const { user }   = useAuth()
  const isManager  = user?.role === 'manager'

  const [form, setForm] = useState({
    title:       '',
    description: '',
    department:  user?.department || 'Finance',
    report_type: 'Sales',
    format:      'Excel',
    deadline:    todayStr(),
  })

  const [phase, setPhase]                   = useState('form')
  const [activeStep, setActiveStep]         = useState(null)
  const [doneSteps, setDoneSteps]           = useState([])
  const [requestId, setRequestId]           = useState(null)
  const [clarifications, setClarifications] = useState([])
  const [aiResult, setAiResult]             = useState(null)
  const [customScore, setCustomScore]       = useState(null)
  const [error, setError]                   = useState(null)
  const [successMsg, setSuccessMsg]         = useState(null)

  const descLen = form.description.length
  const isValid = form.title.trim().length > 0 && descLen >= 50 && form.deadline

  function set(field, value) {
    setForm(prev => ({ ...prev, [field]: value }))
    setError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!isValid) return

    setError(null)
    setPhase('analyzing')
    setActiveStep('clarification')
    setDoneSteps([])

    try {
      // department is auto-set from user profile on the server
      const res = await submitRequest({ ...form, days_open: 0 })
      const { id, status, clarification, priority } = res.data

      setRequestId(id)
      setDoneSteps(['clarification'])

      if (status === 'pending_clarification' || clarification?.status === 'incomplete') {
        setClarifications(clarification?.questions || [])
        setActiveStep(null)
        setPhase('clarification')
        return
      }

      setActiveStep('priority')
      await new Promise(r => setTimeout(r, 350))
      setDoneSteps(['clarification', 'priority'])
      setAiResult(priority)
      setCustomScore(priority?.score ?? 5)
      setActiveStep('decision')
      setPhase('decision')
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to connect to the backend.')
      setPhase('form')
      setActiveStep(null)
      setDoneSteps([])
    }
  }

  async function handleClarificationResubmit(e) {
    e.preventDefault()
    if (!requestId) return

    setError(null)
    setPhase('analyzing')
    setActiveStep('clarification')
    setDoneSteps([])

    try {
      const res = await submitClarification(requestId, { description: form.description })
      const { status, clarification, priority } = res.data

      setDoneSteps(['clarification'])

      if (status === 'pending_clarification' || clarification?.status === 'incomplete') {
        setClarifications(clarification?.questions || [])
        setActiveStep(null)
        setPhase('clarification')
        return
      }

      setActiveStep('priority')
      await new Promise(r => setTimeout(r, 350))
      setDoneSteps(['clarification', 'priority'])
      setAiResult(priority)
      setCustomScore(priority?.score ?? 5)
      setActiveStep('decision')
      setPhase('decision')
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Resubmission failed.')
      setPhase('clarification')
    }
  }

  async function handleApprove(score) {
    if (!requestId) return
    setError(null)
    try {
      await approveRequest(requestId)
      setDoneSteps(['clarification', 'priority', 'decision'])
      setSuccessMsg('Request approved and added to the dashboard.')
      setTimeout(() => navigate('/'), 1400)
    } catch (err) {
      setError(err.response?.data?.detail || 'Approval failed.')
    }
  }

  async function handleReject() {
    if (!requestId) return
    setError(null)
    try {
      await rejectRequest(requestId)
      setSuccessMsg('Request rejected.')
      setTimeout(() => navigate('/'), 1400)
    } catch (err) {
      setError(err.response?.data?.detail || 'Rejection failed.')
    }
  }

  function handleEmployeeDone() {
    // Request already saved as pending_approval — just go to dashboard
    navigate('/')
  }

  return (
    <div className="page-narrow">
      <p className="page-subtitle">Submit a new internal data request</p>

      {successMsg && <div className="alert-success">{successMsg}</div>}
      {error      && <div className="alert-error">{error}</div>}

      {/* Agent progress panel — shown during analysis and decision */}
      {(phase === 'analyzing' || phase === 'decision' || phase === 'clarification') && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '16px' }}>
            AI Agent Activity
          </div>
          <AgentProgress activeStep={activeStep} doneSteps={doneSteps} />
        </div>
      )}

      {/* Initial form */}
      {phase === 'form' && (
        <div className="form-card">
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '18px' }}>
              <label className="label">Requesting Department</label>
              <select
                className="form-select"
                value={form.department}
                onChange={e => set('department', e.target.value)}
              >
                {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

            <div className="form-section-title">Request Details</div>

            <div style={{ marginBottom: '16px' }}>
              <label className="label">Request Title</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Monthly Sales Report"
                value={form.title}
                onChange={e => set('title', e.target.value)}
                required
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label className="label">Description</label>
              <textarea
                className="form-textarea"
                placeholder="Describe the report in detail — include time period, key metrics, data source, and expected output format..."
                value={form.description}
                onChange={e => set('description', e.target.value)}
                rows={5}
              />
              <div className={`char-count ${descLen >= 50 ? 'ok' : 'error'}`}>
                {descLen} / 50 minimum characters
              </div>
            </div>

            <div className="form-section-title">Specifications</div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
              <div>
                <label className="label">Report Type</label>
                <select className="form-select" value={form.report_type} onChange={e => set('report_type', e.target.value)}>
                  {REPORT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Delivery Format</label>
                <select className="form-select" value={form.format} onChange={e => set('format', e.target.value)}>
                  {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label className="label">Deadline</label>
              <input
                type="date"
                lang="en"
                className="form-input"
                min={todayStr()}
                value={form.deadline}
                onChange={e => set('deadline', e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              disabled={!isValid}
              className="btn-submit"
            >
              Analyze with AI
            </button>
          </form>
        </div>
      )}

      {/* Clarification form */}
      {phase === 'clarification' && (
        <div className="form-card">
          <div className="alert-warning">
            <strong>More information needed.</strong> Update your description to address the points below, then resubmit.
          </div>
          {clarifications.map((q, i) => (
            <div key={i} style={{
              color: 'var(--text-heading)', fontSize: '13px',
              paddingLeft: '12px', borderLeft: '3px solid var(--warning-border)',
              marginBottom: '8px', lineHeight: 1.55,
            }}>
              {i + 1}. {q}
            </div>
          ))}
          <form onSubmit={handleClarificationResubmit} style={{ marginTop: '20px' }}>
            <label className="label">Updated Description</label>
            <textarea
              className="form-textarea"
              value={form.description}
              onChange={e => set('description', e.target.value)}
              rows={5}
              style={{ marginBottom: '16px' }}
            />
            <button type="submit" className="btn-submit">Resubmit</button>
          </form>
        </div>
      )}

      {/* AI result + decision */}
      {phase === 'decision' && aiResult && (
        <>
          {/* AI result card */}
          <div className="form-card" style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '12px' }}>
              AI Analysis Result
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '16px', marginBottom: '20px' }}>
              <div style={{ color: 'var(--text)', fontSize: '52px', fontWeight: 800, lineHeight: 1 }}>
                {aiResult.score}
              </div>
              <div style={{ paddingBottom: '8px' }}>
                <div style={{ color: 'var(--text-dim)', fontSize: '13px' }}>out of 10</div>
                <div style={{ marginTop: '6px' }}><PriorityBadge score={aiResult.score} /></div>
              </div>
            </div>

            {aiResult.reasons?.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-dim)', fontWeight: 500, marginBottom: '8px' }}>Reasons</div>
                {aiResult.reasons.map((r, i) => (
                  <div key={i} style={{
                    color: 'var(--text-heading)', fontSize: '13px',
                    paddingLeft: '12px', borderLeft: '3px solid var(--accent-indigo)',
                    marginBottom: '6px', lineHeight: 1.55,
                  }}>{r}</div>
                ))}
              </div>
            )}

            {aiResult.rag_references?.length > 0 && (
              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-dim)', fontWeight: 500, marginBottom: '6px' }}>Policy References</div>
                {aiResult.rag_references.map((ref, i) => (
                  <div key={i} style={{ color: 'var(--text-faint)', fontSize: '12px', marginBottom: '3px' }}>{ref}</div>
                ))}
              </div>
            )}
          </div>

          {/* Decision card */}
          <div className="form-card">
            {isManager ? (
              <>
                <div style={{ color: 'var(--text)', fontSize: '15px', fontWeight: 600, marginBottom: '20px' }}>
                  Manager Decision
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <button
                    onClick={() => handleApprove(aiResult.score)}
                    className="btn-primary"
                    style={{ padding: '12px' }}
                  >
                    Approve (Score: {aiResult.score})
                  </button>
                  <button
                    onClick={handleReject}
                    className="btn-danger"
                    style={{ padding: '12px' }}
                  >
                    Reject
                  </button>
                </div>

                <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--surface-3)' }}>
                  <label className="label">Approve with custom score</label>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <input
                      type="number" min="1" max="10" step="0.5"
                      value={customScore ?? aiResult.score}
                      onChange={e => setCustomScore(parseFloat(e.target.value))}
                      className="form-input"
                      style={{ width: '100px' }}
                    />
                    <button
                      onClick={() => handleApprove(customScore ?? aiResult.score)}
                      className="btn-secondary"
                      style={{ padding: '10px 16px', fontSize: '13px', whiteSpace: 'nowrap' }}
                    >
                      Approve with {customScore ?? aiResult.score}
                    </button>
                  </div>
                </div>
              </>
            ) : (
              /* Employee view — request is already pending_approval */
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'center' }}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="9 12 11 14 15 10"/>
                  </svg>
                </div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text)', marginBottom: '8px' }}>
                  Request Submitted for Review
                </div>
                <div style={{ fontSize: '14px', color: 'var(--text-dim)', marginBottom: '20px' }}>
                  Your request (priority score: {aiResult.score}) has been sent to a manager for approval.
                </div>
                <button onClick={handleEmployeeDone} className="btn-primary" style={{ padding: '10px 24px' }}>
                  Back to Dashboard
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
