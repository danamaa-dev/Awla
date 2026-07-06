import { useState, useEffect } from 'react'
import { getRequests, generateReport, updateStatus } from '../api/client'

const STATUS_OPTIONS = [
  { value: 'open',        label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'overdue',     label: 'Overdue' },
  { value: 'completed',   label: 'Completed' },
  { value: 'rejected',    label: 'Rejected' },
]

function Section({ title, titleColor, children }) {
  return (
    <div style={{
      backgroundColor: '#FFFFFF', border: '1px solid #E5E7EB',
      borderRadius: '10px', padding: '20px 24px', marginBottom: '14px',
    }}>
      <div style={{ fontSize: '13px', fontWeight: 700, color: titleColor || '#111827', marginBottom: '14px' }}>
        {title}
      </div>
      {children}
    </div>
  )
}

export default function MeetingReport() {
  const [requests, setRequests]           = useState([])
  const [report, setReport]               = useState(null)
  const [loading, setLoading]             = useState(false)
  const [fetching, setFetching]           = useState(true)
  const [error, setError]                 = useState(null)
  const [localStatuses, setLocalStatuses] = useState({})
  const [savingId, setSavingId]           = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setFetching(true)
      try {
        const res = await getRequests()
        if (cancelled) return
        const reqs = (res.data || []).filter(r =>
          !['pending_clarification', 'pending_approval'].includes(r.status)
        )
        setRequests(reqs)
        const s = {}
        reqs.forEach(r => { s[r.id] = r.status })
        setLocalStatuses(s)
      } catch {
        if (!cancelled) setError('Could not load requests. Is the backend running?')
      } finally {
        if (!cancelled) setFetching(false)
      }
    }
    load()

    return () => { cancelled = true }
  }, [])

  async function handleGenerate() {
    setLoading(true)
    setError(null)
    try {
      const res = await generateReport()
      setReport({ ...res.data, generated_at: new Date().toISOString() })
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate report.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveStatus(id) {
    setSavingId(id)
    try {
      await updateStatus(id, localStatuses[id])
      setRequests(prev => prev.map(r => r.id === id ? { ...r, status: localStatuses[id] } : r))
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update status.')
    } finally {
      setSavingId(null)
    }
  }

  const total     = requests.length
  const pending   = requests.filter(r => r.status === 'open' || r.status === 'in_progress').length
  const overdue   = requests.filter(r => r.status === 'overdue').length
  const completed = requests.filter(r => r.status === 'completed').length
  const active    = requests.filter(r => ['open', 'in_progress', 'overdue'].includes(r.status))

  return (
    <div className="page" style={{ maxWidth: '1000px' }}>
      <p className="page-subtitle">AI-generated meeting summary and action items for all requests</p>

      {/* Stat summary */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '28px' }}>
        <div className="stat-card total">
          <div className="stat-label">Total Requests</div>
          <div className="stat-value total">{total}</div>
        </div>
        <div className="stat-card pending">
          <div className="stat-label">In Progress</div>
          <div className="stat-value pending">{pending}</div>
        </div>
        <div className="stat-card overdue">
          <div className="stat-label">Overdue</div>
          <div className="stat-value overdue">{overdue}</div>
        </div>
        <div className="stat-card completed">
          <div className="stat-label">Completed</div>
          <div className="stat-value completed">{completed}</div>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
        <button
          onClick={handleGenerate}
          disabled={loading || fetching || requests.length === 0}
          className="btn-primary"
          style={{ padding: '11px 24px' }}
        >
          {loading ? 'Generating...' : 'Generate Meeting Report'}
        </button>

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div className="spinner" style={{ width: '20px', height: '20px', borderWidth: '2px' }} />
            <span style={{ fontSize: '13px', color: '#6B7280' }}>Report Agent is working...</span>
          </div>
        )}
      </div>

      {/* Placeholder when no report */}
      {!report && !loading && (
        <div className="report-placeholder">
          <div className="report-placeholder-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="20" x2="18" y2="10"/>
              <line x1="12" y1="20" x2="12" y2="4"/>
              <line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
          </div>
          <p className="report-placeholder-title">No report generated yet</p>
          <p className="report-placeholder-text">
            Click "Generate Meeting Report" to get an AI-powered summary of all current requests,
            overdue items, and recommended actions for your meeting.
          </p>
        </div>
      )}

      {/* Report content */}
      {report && (
        <>
          {report.generated_at && (
            <div style={{ color: '#9CA3AF', fontSize: '12px', marginBottom: '18px' }}>
              Generated: {new Date(report.generated_at).toLocaleString()}
            </div>
          )}

          {report.summary && typeof report.summary === 'object' && (
            <Section title="Overview">
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {[
                  { label: 'Total',       value: report.summary.total,       color: '#111827' },
                  { label: 'Open',        value: report.summary.open,        color: '#4F46E5' },
                  { label: 'In Progress', value: report.summary.in_progress, color: '#D97706' },
                  { label: 'Overdue',     value: report.summary.overdue,     color: '#DC2626' },
                  { label: 'Completed',   value: report.summary.completed,   color: '#059669' },
                  { label: 'Rejected',    value: report.summary.rejected,    color: '#6B7280' },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{
                    flex: '1 1 100px', minWidth: '90px',
                    backgroundColor: '#F9FAFB', border: '1px solid #E5E7EB',
                    borderRadius: '8px', padding: '12px 16px', textAlign: 'center',
                  }}>
                    <div style={{ fontSize: '22px', fontWeight: 700, color }}>{value ?? 0}</div>
                    <div style={{ fontSize: '11px', color: '#6B7280', marginTop: '2px' }}>{label}</div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {report.overdue_items?.length > 0 && (
            <Section title={`Overdue Items (${report.overdue_items.length})`} titleColor="#DC2626">
              {report.overdue_items.map((item, i) => (
                <div key={i} style={{
                  padding: '12px 14px', backgroundColor: '#FEF2F2',
                  borderRadius: '8px', marginBottom: i < report.overdue_items.length - 1 ? '8px' : 0,
                  borderLeft: '3px solid #DC2626',
                }}>
                  <div style={{ color: '#111827', fontSize: '14px', fontWeight: 500, marginBottom: '4px' }}>
                    {item.title} — {item.days_overdue} days overdue
                  </div>
                  <div style={{ color: '#6B7280', fontSize: '13px', marginBottom: '2px' }}>Reason: {item.reason}</div>
                  <div style={{ color: '#6B7280', fontSize: '13px' }}>Action: {item.action}</div>
                </div>
              ))}
            </Section>
          )}

          {report.top_priority_items?.length > 0 && (
            <Section title="Top Priority Items">
              {report.top_priority_items.map((item, i) => (
                <div key={i} style={{
                  padding: '8px 0',
                  borderBottom: i < report.top_priority_items.length - 1 ? '1px solid #E5E7EB' : 'none',
                  fontSize: '13px', display: 'flex', gap: '8px', alignItems: 'baseline',
                }}>
                  <span style={{ color: '#111827', fontWeight: 600 }}>{item.title}</span>
                  <span style={{ color: '#6B7280' }}>Score: {item.score}</span>
                  <span style={{ color: '#D1D5DB' }}>·</span>
                  <span style={{ color: '#6B7280' }}>{item.discussion_point}</span>
                </div>
              ))}
            </Section>
          )}

          {report.recommendations?.length > 0 && (
            <Section title="AI Recommendations">
              {report.recommendations.map((rec, i) => (
                <div key={i} style={{
                  color: '#374151', fontSize: '13px',
                  paddingLeft: '12px', borderLeft: '3px solid #4F46E5',
                  marginBottom: '8px', lineHeight: 1.55,
                }}>{rec}</div>
              ))}
            </Section>
          )}

          {report.workload_insight && (
            <div style={{
              backgroundColor: '#EEF2FF', border: '1px solid #C7D2FE',
              borderRadius: '10px', padding: '20px 24px', marginBottom: '14px',
            }}>
              <div style={{ color: '#4F46E5', fontSize: '13px', fontWeight: 700, marginBottom: '10px' }}>
                Workload Insight
              </div>
              <p style={{ color: '#374151', fontSize: '14px', lineHeight: 1.7, margin: 0 }}>
                {report.workload_insight}
              </p>
            </div>
          )}

          {/* Post-meeting status updates */}
          <Section title="Update Statuses After Meeting">
            {active.length === 0 ? (
              <div style={{ color: '#6B7280', fontSize: '14px' }}>No active requests to update.</div>
            ) : (
              active.map((req, i) => (
                <div key={req.id} style={{
                  display: 'flex', alignItems: 'center', gap: '14px',
                  padding: '10px 0',
                  borderBottom: i < active.length - 1 ? '1px solid #E5E7EB' : 'none',
                }}>
                  <div style={{ flex: 1 }}>
                    <span style={{ color: '#111827', fontSize: '14px', fontWeight: 500 }}>{req.title}</span>
                    <span style={{ color: '#6B7280', fontSize: '12px', marginLeft: '8px' }}>{req.department}</span>
                  </div>
                  <label htmlFor={`status-${req.id}`} className="sr-only">Status for {req.title}</label>
                  <select
                    id={`status-${req.id}`}
                    value={localStatuses[req.id] || req.status}
                    onChange={e => setLocalStatuses(prev => ({ ...prev, [req.id]: e.target.value }))}
                    className="input-sm"
                    style={{ width: '150px' }}
                  >
                    {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  <button
                    onClick={() => handleSaveStatus(req.id)}
                    disabled={savingId === req.id}
                    className="btn-primary"
                    style={{ padding: '7px 16px', fontSize: '13px', whiteSpace: 'nowrap' }}
                  >
                    {savingId === req.id ? 'Saving...' : 'Save'}
                  </button>
                </div>
              ))
            )}
          </Section>
        </>
      )}
    </div>
  )
}
