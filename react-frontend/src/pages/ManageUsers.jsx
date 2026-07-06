import { useState, useEffect, useCallback } from 'react'
import { listUsers, inviteUser, updateUser } from '../api/client'
import { useAuth } from '../context/AuthContext'

const DEPARTMENTS = ['Finance', 'HR', 'Operations', 'Marketing', 'Sales', 'Security', 'Procurement', 'Other']
const ROLES = ['employee', 'manager']

const STATUS_STYLE = {
  invited:   { color: 'var(--warning)', bg: 'var(--warning-bg)', border: 'var(--warning-border)' },
  active:    { color: 'var(--success)', bg: 'var(--success-bg)', border: 'var(--success-border)' },
  suspended: { color: 'var(--danger)',  bg: 'var(--danger-bg)',  border: 'var(--danger-border)' },
}

const th = { padding: '8px 10px', color: 'var(--text-dim)', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.4px' }
const td = { padding: '10px', borderBottom: '1px solid var(--border)', verticalAlign: 'middle' }

function StatusPill({ status }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.active
  return (
    <span style={{
      display: 'inline-block', fontSize: '11px', fontWeight: 600,
      color: s.color, background: s.bg, border: `1px solid ${s.border}`,
      borderRadius: '4px', padding: '2px 8px', textTransform: 'capitalize',
    }}>
      {status}
    </span>
  )
}

function InviteForm({ defaultDepartment, onInvited }) {
  const [form, setForm] = useState({ name: '', email: '', role: 'employee', department: defaultDepartment })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [successMsg, setSuccessMsg] = useState(null)

  function set(field, value) {
    setForm(prev => ({ ...prev, [field]: value }))
    setError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setSuccessMsg(null)
    try {
      await inviteUser(form)
      setSuccessMsg(`Invite sent to ${form.email}.`)
      setForm({ name: '', email: '', role: 'employee', department: defaultDepartment })
      onInvited()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send invite.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card" style={{ marginBottom: '24px' }}>
      <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)', marginBottom: '16px' }}>
        Invite a New User
      </div>
      {successMsg && <div className="alert-success">{successMsg}</div>}
      {error && <div className="alert-error">{error}</div>}
      <form
        onSubmit={handleSubmit}
        style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.4fr 0.8fr 1fr auto', gap: '12px', alignItems: 'end' }}
      >
        <div>
          <label className="label">Full Name</label>
          <input className="form-input" value={form.name} onChange={e => set('name', e.target.value)} required />
        </div>
        <div>
          <label className="label">Email</label>
          <input
            type="email" className="form-input" value={form.email}
            onChange={e => set('email', e.target.value)} required
          />
        </div>
        <div>
          <label className="label">Role</label>
          <select className="form-select" value={form.role} onChange={e => set('role', e.target.value)}>
            {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Department</label>
          <select className="form-select" value={form.department} onChange={e => set('department', e.target.value)}>
            {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <button type="submit" disabled={submitting} className="btn-primary" style={{ padding: '10px 20px' }}>
          {submitting ? 'Sending...' : 'Send Invite'}
        </button>
      </form>
    </div>
  )
}

function UserRow({ u, isSelf, onChange }) {
  const [editing, setEditing]       = useState(false)
  const [role, setRole]             = useState(u.role)
  const [department, setDepartment] = useState(u.department)
  const [saving, setSaving]         = useState(false)
  const [error, setError]           = useState(null)

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      await updateUser(u.id, { role, department })
      setEditing(false)
      onChange()
    } catch (err) {
      setError(err.response?.data?.detail || 'Update failed.')
      setSaving(false)
    }
  }

  async function handleToggleStatus() {
    setSaving(true)
    setError(null)
    try {
      await updateUser(u.id, { status: u.status === 'suspended' ? 'active' : 'suspended' })
      onChange()
    } catch (err) {
      setError(err.response?.data?.detail || 'Update failed.')
      setSaving(false)
    }
  }

  return (
    <tr>
      <td style={td}>
        {u.name}
        {isSelf && <span style={{ color: 'var(--text-faint)', fontSize: '12px' }}> (you)</span>}
      </td>
      <td style={td}>{u.email}</td>
      <td style={td}>
        {editing ? (
          <select className="input-sm" value={role} onChange={e => setRole(e.target.value)}>
            {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        ) : <span style={{ textTransform: 'capitalize' }}>{u.role}</span>}
      </td>
      <td style={td}>
        {editing ? (
          <select className="input-sm" value={department} onChange={e => setDepartment(e.target.value)}>
            {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        ) : u.department}
      </td>
      <td style={td}><StatusPill status={u.status} /></td>
      <td style={td}>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {editing ? (
            <>
              <button
                onClick={handleSave} disabled={saving}
                className="btn-primary" style={{ padding: '5px 12px', fontSize: '12px' }}
              >
                {saving ? '...' : 'Save'}
              </button>
              <button
                onClick={() => { setEditing(false); setRole(u.role); setDepartment(u.department) }}
                className="btn-secondary" style={{ padding: '5px 12px', fontSize: '12px' }}
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setEditing(true)}
              className="btn-secondary" style={{ padding: '5px 12px', fontSize: '12px' }}
            >
              Edit
            </button>
          )}
          {!isSelf && u.status !== 'invited' && (
            <button
              onClick={handleToggleStatus}
              disabled={saving}
              className={u.status === 'suspended' ? 'btn-primary' : 'btn-danger'}
              style={{ padding: '5px 12px', fontSize: '12px' }}
            >
              {u.status === 'suspended' ? 'Reactivate' : 'Deactivate'}
            </button>
          )}
        </div>
        {error && <div style={{ color: 'var(--danger)', fontSize: '12px', marginTop: '4px' }}>{error}</div>}
      </td>
    </tr>
  )
}

export default function ManageUsers() {
  const { user: currentUser } = useAuth()
  const [users, setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await listUsers()
      setUsers(res.data || [])
    } catch {
      setError('Could not load users.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="page">
      <p className="page-subtitle">Invite, manage, and deactivate user accounts</p>

      <InviteForm defaultDepartment={currentUser?.department || 'Finance'} onInvited={load} />

      <div className="card">
        <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)', marginBottom: '16px' }}>
          All Users
        </div>
        {error && <div className="alert-error">{error}</div>}
        {loading ? (
          <div style={{ color: 'var(--text-dim)', fontSize: '13px' }}>Loading users…</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13.5px' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                  <th style={th}>Name</th>
                  <th style={th}>Email</th>
                  <th style={th}>Role</th>
                  <th style={th}>Department</th>
                  <th style={th}>Status</th>
                  <th style={th}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <UserRow key={u.id} u={u} isSelf={u.id === currentUser?.id} onChange={load} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
