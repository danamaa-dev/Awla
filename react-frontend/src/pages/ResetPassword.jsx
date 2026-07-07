import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { resetPassword } from '../api/client'
import AwlaLogo from '../components/AwlaLogo'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [password, setPassword]   = useState('')
  const [confirm, setConfirm]     = useState('')
  const [error, setError]         = useState(null)
  const [loading, setLoading]     = useState(false)
  const [done, setDone]           = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    try {
      await resetPassword(token, password)
      setDone(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'This reset link is invalid or has expired.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', backgroundColor: 'var(--bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <div style={{
        backgroundColor: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: '16px', padding: '44px 40px', width: '100%', maxWidth: '420px',
        boxShadow: 'var(--shadow-lg)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px' }}>
            <AwlaLogo size={80} />
          </div>
          <div style={{ fontSize: '14px', color: 'var(--text-dim)', marginTop: '4px' }}>
            Set a new password
          </div>
        </div>

        {!token ? (
          <div className="alert-error" style={{ marginBottom: 0 }}>
            This link is missing its reset token. Request a new one from the
            forgot-password page.
          </div>
        ) : done ? (
          <div className="alert-success" style={{ marginBottom: 0 }}>
            Your password has been reset. You can now sign in with it.
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && <div className="alert-error">{error}</div>}
            <div style={{ marginBottom: '18px' }}>
              <label className="label">New Password</label>
              <input
                type="password" className="input" placeholder="At least 8 characters"
                value={password} onChange={e => setPassword(e.target.value)}
                required autoComplete="new-password"
              />
            </div>
            <div style={{ marginBottom: '24px' }}>
              <label className="label">Confirm Password</label>
              <input
                type="password" className="input"
                value={confirm} onChange={e => setConfirm(e.target.value)}
                required autoComplete="new-password"
              />
            </div>
            <button
              type="submit" disabled={loading}
              className="btn-primary" style={{ width: '100%', padding: '12px', fontSize: '15px' }}
            >
              {loading ? 'Resetting...' : 'Reset Password'}
            </button>
          </form>
        )}

        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <Link to="/login" className="text-link">Back to sign in</Link>
        </div>
      </div>
    </div>
  )
}
