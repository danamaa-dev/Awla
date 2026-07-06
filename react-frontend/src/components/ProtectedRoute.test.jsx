import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'
import * as AuthContext from '../context/AuthContext'

function renderWithRouter(ui, initialEntries = ['/report']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/" element={<div>Dashboard Page</div>} />
        <Route path="/report" element={ui} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  it('redirects to /login when there is no authenticated user', () => {
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({ user: null, loading: false })
    renderWithRouter(<ProtectedRoute><div>Secret</div></ProtectedRoute>)
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByText('Secret')).not.toBeInTheDocument()
  })

  it('shows a loading state instead of redirecting while the session is still being verified', () => {
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({ user: null, loading: true })
    const { container } = renderWithRouter(<ProtectedRoute><div>Secret</div></ProtectedRoute>)
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
    expect(container.querySelector('.spinner')).toBeInTheDocument()
  })

  it('renders the protected content for an authenticated employee', () => {
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: { id: 1, role: 'employee' },
      loading: false,
    })
    renderWithRouter(<ProtectedRoute><div>Secret</div></ProtectedRoute>)
    expect(screen.getByText('Secret')).toBeInTheDocument()
  })

  it('redirects a non-manager away from a managerOnly route', () => {
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: { id: 1, role: 'employee' },
      loading: false,
    })
    renderWithRouter(<ProtectedRoute managerOnly><div>Manager Only</div></ProtectedRoute>)
    expect(screen.getByText('Dashboard Page')).toBeInTheDocument()
    expect(screen.queryByText('Manager Only')).not.toBeInTheDocument()
  })

  it('allows a manager through a managerOnly route', () => {
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: { id: 4, role: 'manager' },
      loading: false,
    })
    renderWithRouter(<ProtectedRoute managerOnly><div>Manager Only</div></ProtectedRoute>)
    expect(screen.getByText('Manager Only')).toBeInTheDocument()
  })
})
