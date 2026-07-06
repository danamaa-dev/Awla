import { useState } from 'react'
import { Link } from 'react-router-dom'
import { forgotPassword } from '../api/client'
import AwlaLogo from '../components/AwlaLogo'

export default function ForgotPassword() {
  const [email, setEmail]     = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent]       = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    try {
      await forgotPassword(email)
    } finally {
      // Shown whether or not the account exists -- the API itself never
      // reveals that, so the UI can't either.
      setLoading(false)
      setSent(true)
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
            Reset your password
          </div>
        </div>

        {sent ? (
          <div className="alert-success" style={{ marginBottom: 0 }}>
            If an account exists for that email, a password reset link is on its way.
            Check your inbox.
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '24px' }}>
              <label className="label">Email</label>
              <input
                type="email"
                className="input"
                placeholder="you@awla.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
              style={{ width: '100%', padding: '12px', fontSize: '15px' }}
            >
              {loading ? 'Sending...' : 'Send Reset Link'}
            </button>
          </form>
        )}

        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <Link to="/login" style={{ fontSize: '13px', color: 'var(--text-dim)' }}>Back to sign in</Link>
        </div>
      </div>
    </div>
  )
}
