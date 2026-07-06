import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRequests } from '../api/client'
import { useAuth } from '../context/AuthContext'
import RequestCard from '../components/RequestCard'
import RequestCardSkeleton from '../components/RequestCardSkeleton'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'

const STATUS_FILTERS = ['All', 'Pending Approval', 'Open', 'In Progress', 'Overdue', 'Completed']
const STATUS_MAP = {
  'All':             null,
  'Pending Approval':'pending_approval',
  'Open':            'open',
  'In Progress':     'in_progress',
  'Overdue':         'overdue',
  'Completed':       'completed',
}
const STATUS_LABELS = {
  pending_approval: 'Pending Approval',
  open:             'Open',
  in_progress:      'In Progress',
  overdue:          'Overdue',
  completed:        'Completed',
  rejected:         'Rejected',
}

const tooltipStyle = {
  contentStyle: { backgroundColor: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px' },
  labelStyle:   { color: 'var(--text)' },
  itemStyle:    { color: 'var(--text-dim)' },
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isManager = user?.role === 'manager'

  const [requests, setRequests]         = useState([])
  const [search, setSearch]             = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState(null)
  const [page, setPage]                 = useState(1)
  const PAGE_SIZE = 20

  const load = useCallback(async ({ signal } = {}) => {
    setLoading(true)
    setError(null)
    try {
      const res = await getRequests({ signal })
      setRequests(res.data || [])
    } catch (err) {
      // A request aborted by the cleanup function below (e.g. the user
      // navigated away before it resolved) isn't a real failure -- only
      // show an error for genuine fetch failures.
      if (err.code !== 'ERR_CANCELED') {
        setError('Could not load requests. Is the backend running?')
      }
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    load({ signal: controller.signal })
    return () => controller.abort()
  }, [load])

  useEffect(() => { setPage(1) }, [search, statusFilter])

  const filtered = requests.filter(r => {
    const targetStatus = STATUS_MAP[statusFilter]
    const matchStatus  = !targetStatus || r.status === targetStatus
    const q            = search.toLowerCase()
    const matchSearch  = !q
      || r.title?.toLowerCase().includes(q)
      || r.department?.toLowerCase().includes(q)
      || r.submitted_by_name?.toLowerCase().includes(q)
    return matchStatus && matchSearch
  })

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pagedRequests = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const total             = requests.length
  const pendingCount      = requests.filter(r => r.status === 'open' || r.status === 'in_progress').length
  const pendingApprovalCount = requests.filter(r => r.status === 'pending_approval').length
  const overdueCount      = requests.filter(r => r.status === 'overdue').length
  const completedCount    = requests.filter(r => r.status === 'completed').length

  const deptMap = {}
  requests.forEach(r => {
    if (r.status !== 'pending_approval') {
      deptMap[r.department] = (deptMap[r.department] || 0) + 1
    }
  })
  const deptData = Object.entries(deptMap).map(([name, count]) => ({ name, count }))

  const statusMap = {}
  requests.forEach(r => {
    const label = STATUS_LABELS[r.status] || r.status
    statusMap[label] = (statusMap[label] || 0) + 1
  })
  const statusData = Object.entries(statusMap).map(([name, count]) => ({ name, count }))

  // Show "Pending Approval" filter only to managers
  const filters = isManager
    ? STATUS_FILTERS
    : STATUS_FILTERS.filter(f => f !== 'Pending Approval')

  return (
    <div className="page">
      <p className="page-subtitle">
        {isManager
          ? `Showing all requests from all employees`
          : 'Showing your submitted requests'}
      </p>

      {/* Stat cards */}
      <div className="stat-row">
        <div className="stat-card total">
          <div className="stat-label">Total Requests</div>
          <div className="stat-value total">{total}</div>
        </div>
        {isManager && pendingApprovalCount > 0 && (
          <div className="stat-card" style={{ borderLeftColor: 'var(--accent-indigo)' }}>
            <div className="stat-label">Pending Approval</div>
            <div className="stat-value" style={{ color: 'var(--accent-indigo)' }}>{pendingApprovalCount}</div>
          </div>
        )}
        <div className="stat-card pending">
          <div className="stat-label">In Progress</div>
          <div className="stat-value pending">{pendingCount}</div>
        </div>
        <div className="stat-card overdue">
          <div className="stat-label">Overdue</div>
          <div className="stat-value overdue">{overdueCount}</div>
        </div>
        <div className="stat-card completed">
          <div className="stat-label">Completed</div>
          <div className="stat-value completed">{completedCount}</div>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      {/* Search + filters */}
      <div className="stack stack-3" style={{ marginBottom: '20px' }}>
        <div>
          <label htmlFor="request-search" className="sr-only">Search requests</label>
          <input
            id="request-search"
            type="text"
            placeholder={isManager ? 'Search by title, department, or submitter...' : 'Search by title or department...'}
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input"
          />
        </div>

        <div className="filter-tabs" role="tablist" aria-label="Filter by status">
          {filters.map(f => (
            <button
              key={f}
              role="tab"
              aria-selected={statusFilter === f}
              onClick={() => setStatusFilter(f)}
              className={`filter-tab ${statusFilter === f ? 'active' : ''}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div style={{ color: 'var(--text-dim)', fontSize: '12px', marginBottom: '12px' }} aria-live="polite">
        {loading ? 'Loading requests…' : `${filtered.length} request${filtered.length !== 1 ? 's' : ''}`}
      </div>

      {/* Request list */}
      {loading ? (
        <div aria-hidden="true">
          <RequestCardSkeleton />
          <RequestCardSkeleton />
          <RequestCardSkeleton />
        </div>
      ) : filtered.length === 0 && requests.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
              <rect x="9" y="3" width="6" height="4" rx="1"/>
              <line x1="9" y1="12" x2="15" y2="12"/>
              <line x1="9" y1="16" x2="12" y2="16"/>
            </svg>
          </div>
          <div className="empty-state-title">No requests yet</div>
          <div className="empty-state-text">
            Click "New Request" to submit your first data request.
          </div>
          <button
            className="btn-primary"
            style={{ marginTop: '16px' }}
            onClick={() => navigate('/new')}
          >
            New Request
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div style={{
          backgroundColor: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: '10px', padding: '40px',
          textAlign: 'center', color: 'var(--text-dim)', fontSize: '14px',
        }}>
          No requests match your filters.
        </div>
      ) : (
        <>
          {pagedRequests.map(req => (
            <RequestCard key={req.id} request={req} onUpdate={load} />
          ))}

          {pageCount > 1 && (
            <nav
              aria-label="Requests pagination"
              style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px', margin: '20px 0' }}
            >
              <button
                type="button"
                className="filter-tab"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                aria-label="Previous page"
              >
                Previous
              </button>
              <span style={{ fontSize: '13px', color: 'var(--text-dim)' }}>
                Page {page} of {pageCount}
              </span>
              <button
                type="button"
                className="filter-tab"
                onClick={() => setPage(p => Math.min(pageCount, p + 1))}
                disabled={page === pageCount}
                aria-label="Next page"
              >
                Next
              </button>
            </nav>
          )}
        </>
      )}

      {/* Charts — only show when there's enough data */}
      {requests.filter(r => r.status !== 'pending_approval').length >= 2 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '40px' }}>
          <div className="card">
            <div style={{ color: 'var(--text)', fontSize: '14px', fontWeight: 600, marginBottom: '18px' }}>
              Requests by Department
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={deptData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="name" tick={{ fill: '#6B7280', fontSize: 11 }} />
                <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} allowDecimals={false} />
                <Tooltip {...tooltipStyle} />
                <Bar dataKey="count" fill="#4F46E5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <div style={{ color: 'var(--text)', fontSize: '14px', fontWeight: 600, marginBottom: '18px' }}>
              Requests by Status
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={statusData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="name" tick={{ fill: '#6B7280', fontSize: 11 }} />
                <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} allowDecimals={false} />
                <Tooltip {...tooltipStyle} />
                <Bar dataKey="count" fill="#059669" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
