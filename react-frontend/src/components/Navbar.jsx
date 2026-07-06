import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import AwlaLogo from './AwlaLogo'

export default function Navbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()

  const isActive = (path) => location.pathname === path

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      {/* Left: logo mark + brand name */}
      <Link to="/" className="navbar-brand">
        <AwlaLogo size={34} showText={false} />
        <span className="navbar-brand-text">awla</span>
      </Link>

      {/* Center: nav links */}
      <div className="navbar-center">
        <Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`}>
          Dashboard
        </Link>
        {user?.role === 'manager' && (
          <>
            <Link to="/report" className={`nav-link ${isActive('/report') ? 'active' : ''}`}>
              Meeting Report
            </Link>
            <Link to="/users" className={`nav-link ${isActive('/users') ? 'active' : ''}`}>
              Users
            </Link>
          </>
        )}
      </div>

      {/* Right: user info + actions */}
      <div className="navbar-right">
        {user && (
          <div className="navbar-user">
            <span className="user-name">{user.name}</span>
            <span className={`role-badge role-${user.role}`}>{user.role}</span>
          </div>
        )}
        <button
          onClick={() => navigate('/new')}
          className="btn-primary"
          style={{ padding: '7px 16px', fontSize: '13px' }}
        >
          New Request
        </button>
        <button onClick={handleLogout} className="btn-logout">
          Sign Out
        </button>
      </div>
    </nav>
  )
}
