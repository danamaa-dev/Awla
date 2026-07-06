import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function ProtectedRoute({ children, managerOnly = false }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', backgroundColor: '#F4F6F9',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div className="spinner" />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />
  if (managerOnly && user.role !== 'manager') return <Navigate to="/" replace />

  return children
}
