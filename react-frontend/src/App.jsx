import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import Navbar from './components/Navbar'

const Login          = lazy(() => import('./pages/Login'))
const Dashboard      = lazy(() => import('./pages/Dashboard'))
const NewRequest     = lazy(() => import('./pages/NewRequest'))
const MeetingReport  = lazy(() => import('./pages/MeetingReport'))
const ManageUsers    = lazy(() => import('./pages/ManageUsers'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))
const ResetPassword  = lazy(() => import('./pages/ResetPassword'))
const AcceptInvite   = lazy(() => import('./pages/AcceptInvite'))

function FullPageSpinner() {
  return (
    <div style={{
      minHeight: '100vh', backgroundColor: 'var(--bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div className="spinner" />
    </div>
  )
}

function AppShell() {
  const { user, loading } = useAuth()

  if (loading) {
    return <FullPageSpinner />
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--bg)' }}>
      {user && <Navbar />}
      <Suspense fallback={<FullPageSpinner />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/accept-invite" element={<AcceptInvite />} />
          <Route path="/" element={
            <ProtectedRoute><Dashboard /></ProtectedRoute>
          } />
          <Route path="/new" element={
            <ProtectedRoute><NewRequest /></ProtectedRoute>
          } />
          <Route path="/report" element={
            <ProtectedRoute managerOnly><MeetingReport /></ProtectedRoute>
          } />
          <Route path="/users" element={
            <ProtectedRoute managerOnly><ManageUsers /></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </AuthProvider>
  )
}
