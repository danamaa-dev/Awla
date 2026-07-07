import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import PriorityBadge from './PriorityBadge'
import StatusBadge from './StatusBadge'
import ExecutionModal from './ExecutionModal'
import { updateStatus, updatePriority, approveRequest, rejectRequest, executeRequest } from '../api/client'

const STATUS_OPTIONS = [
  { value: 'open',        label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'overdue',     label: 'Overdue' },
  { value: 'completed',   label: 'Completed' },
  { value: 'rejected',    label: 'Rejected' },
]

function agentBadges(request) {
  const hasScore = request.priority_score != null && request.priority_score > 0
  const isDone   = request.status === 'completed'
  return [
    { name: 'Clarification', done: true },
    { name: 'Priority',      done: hasScore },
    { name: 'Execution',     done: isDone },
  ]
}

export default function RequestCard({ request, onUpdate }) {
  const { user } = useAuth()
  const isManager = user?.role === 'manager'

  const [showUpdate, setShowUpdate] = useState(false)
  const [newStatus, setNewStatus]   = useState(request.status)
  const [newScore, setNewScore]     = useState(request.priority_score)
  const [reason, setReason]         = useState('')
  const [chartResult, setChartResult] = useState(null)
  const [executing, setExecuting]   = useState(false)
  const [approving, setApproving]   = useState(false)
  const [error, setError]           = useState(null)

  async function handleSave() {
    setError(null)
    try {
      if (newStatus !== request.status) {
        await updateStatus(request.id, newStatus)
      }
      if (parseFloat(newScore) !== request.priority_score) {
        await updatePriority(request.id, parseFloat(newScore), reason || 'Manual adjustment')
      }
      setShowUpdate(false)
      setReason('')
      if (onUpdate) onUpdate()
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed.')
    }
  }

  async function handleApprove() {
    setApproving(true)
    setError(null)
    try {
      await approveRequest(request.id)
      if (onUpdate) onUpdate()
    } catch (err) {
      setError(err.response?.data?.detail || 'Approval failed.')
    } finally {
      setApproving(false)
    }
  }

  async function handleReject() {
    setApproving(true)
    setError(null)
    try {
      await rejectRequest(request.id)
      if (onUpdate) onUpdate()
    } catch (err) {
      setError(err.response?.data?.detail || 'Rejection failed.')
    } finally {
      setApproving(false)
    }
  }

  async function handleExecute() {
    setExecuting(true)
    setError(null)
    const fmt = request.format || 'Dashboard'
    try {
      const res = await executeRequest(request.id, fmt)

      if (fmt === 'Dashboard') {
        setChartResult(res.data)
      } else {
        // Excel or PDF — trigger browser download
        const ext  = fmt === 'PDF' ? 'pdf' : 'xlsx'
        const mime = fmt === 'PDF' ? 'application/pdf'
                   : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        const url  = URL.createObjectURL(new Blob([res.data], { type: mime }))
        const a    = document.createElement('a')
        a.href     = url
        a.download = `${request.title.replace(/\s+/g, '_')}.${ext}`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      let msg
      if (!err.response) {
        msg = 'Cannot reach server. Make sure the backend is running on port 8000.'
      } else if (err.response.data instanceof Blob) {
        // axios parses error responses as blobs when responseType='blob'
        try {
          const text   = await err.response.data.text()
          const parsed = JSON.parse(text)
          msg = parsed.detail || `Server error ${err.response.status}`
        } catch {
          msg = `Server error ${err.response.status}`
        }
      } else {
        msg = err.response?.data?.detail || `Error ${err.response?.status}`
      }
      setError(msg)
    } finally {
      setExecuting(false)
    }
  }

  const badges = agentBadges(request)
  const isPendingApproval = request.status === 'pending_approval'

  return (
    <>
      <div
        className="request-card"
        style={{
          border: isPendingApproval ? '1px solid var(--indigo-border)' : '1px solid var(--border)',
          borderLeft: isPendingApproval ? '4px solid var(--accent-indigo)' : '1px solid var(--border)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text)', fontSize: '15px', fontWeight: 600 }}>
                {request.title}
              </span>
              {isPendingApproval && (
                <span style={{
                  fontSize: '11px', fontWeight: 600,
                  color: 'var(--accent-indigo)', background: 'var(--indigo-bg)',
                  border: '1px solid var(--indigo-border)', borderRadius: '4px',
                  padding: '2px 7px',
                }}>
                  Pending Approval
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--text-dim)', fontSize: '13px' }}>{request.department}</span>
              {!isPendingApproval && (
                <>
                  <span style={{ color: 'var(--border-strong)' }}>·</span>
                  <StatusBadge status={request.status} />
                </>
              )}
              <span style={{ color: 'var(--border-strong)' }}>·</span>
              <span style={{ color: 'var(--text-dim)', fontSize: '13px' }}>Deadline: {request.deadline}</span>
              {isManager && request.submitted_by_name && (
                <>
                  <span style={{ color: 'var(--border-strong)' }}>·</span>
                  <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>
                    By {request.submitted_by_name}
                  </span>
                </>
              )}
            </div>
          </div>
          <div style={{ flexShrink: 0 }}>
            <PriorityBadge score={request.priority_score} />
          </div>
        </div>

        {request.description && (
          <p style={{ color: 'var(--text-dim)', fontSize: '13px', marginTop: '10px', lineHeight: 1.55 }}>
            {request.description}
          </p>
        )}

        {/* Agent badges */}
        <div className="agent-badges">
          {badges.map(b => (
            <span key={b.name} className={`agent-badge ${b.done ? 'done' : 'pending'}`}>
              {b.done ? (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: 'middle', marginRight: '3px' }}>
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              ) : (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: 'middle', marginRight: '3px' }}>
                  <circle cx="12" cy="12" r="9"/>
                </svg>
              )}
              {b.name}
            </span>
          ))}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '8px', marginTop: '14px', flexWrap: 'wrap' }}>
          {/* Manager: approve/reject pending requests */}
          {isManager && isPendingApproval && (
            <>
              <button
                onClick={handleApprove}
                disabled={approving}
                className="btn-primary"
                style={{ padding: '6px 14px', fontSize: '13px' }}
              >
                {approving ? '...' : 'Approve'}
              </button>
              <button
                onClick={handleReject}
                disabled={approving}
                className="btn-danger"
                style={{ padding: '6px 14px', fontSize: '13px' }}
              >
                {approving ? '...' : 'Reject'}
              </button>
            </>
          )}

          {/* Manager: update status/priority on non-pending requests */}
          {isManager && !isPendingApproval && (
            <button
              onClick={() => { setShowUpdate(!showUpdate); setNewStatus(request.status); setNewScore(request.priority_score) }}
              className="btn-secondary"
              style={{ padding: '6px 14px', fontSize: '13px' }}
            >
              {showUpdate ? 'Cancel' : 'Update'}
            </button>
          )}

          {/* Execute: label and action depend on the requested format */}
          {['open', 'in_progress', 'overdue', 'completed'].includes(request.status) && (
            <button
              onClick={handleExecute}
              disabled={executing}
              className="btn-primary"
              style={{ padding: '6px 14px', fontSize: '13px' }}
            >
              {executing ? 'Processing...' : (
                request.format === 'Excel'     ? 'Download Excel' :
                request.format === 'PDF'       ? 'Download PDF'   :
                                                 'View Dashboard'
              )}
            </button>
          )}
        </div>

        {error && (
          <div style={{ color: 'var(--danger)', fontSize: '13px', marginTop: '8px' }}>{error}</div>
        )}

        {/* Manager inline update form */}
        {isManager && showUpdate && !isPendingApproval && (
          <div style={{
            marginTop: '14px', padding: '16px',
            backgroundColor: 'var(--surface-2)', borderRadius: '8px',
            border: '1px solid var(--border)',
            display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px',
            alignItems: 'end',
          }}>
            <div>
              <label className="label">Status</label>
              <select value={newStatus} onChange={e => setNewStatus(e.target.value)} className="input-sm">
                {STATUS_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Priority Score</label>
              <input
                type="number" min="1" max="10" step="0.5"
                value={newScore} onChange={e => setNewScore(e.target.value)}
                className="input-sm"
              />
            </div>
            <div>
              <label className="label">Reason</label>
              <input
                type="text" value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Optional"
                className="input-sm"
              />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <button onClick={handleSave} className="btn-primary" style={{ padding: '8px 22px', fontSize: '13px' }}>
                Save
              </button>
            </div>
          </div>
        )}
      </div>

      {chartResult && (
        <ExecutionModal result={chartResult} onClose={() => setChartResult(null)} />
      )}
    </>
  )
}
