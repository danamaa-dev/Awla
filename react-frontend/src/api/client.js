import axios from 'axios'

// Configurable per environment instead of a hardcoded localhost URL
// (audit finding H15). Vite exposes any VITE_-prefixed variable from
// react-frontend/.env at build time.
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_URL,
  timeout: 60000,
  // The session token now lives in an httpOnly cookie the browser
  // attaches automatically -- withCredentials makes axios actually send
  // (and accept) that cookie cross-origin. Nothing reads or writes the
  // token from JS anymore, so an XSS bug can no longer exfiltrate it the
  // way it could when it lived in localStorage (audit finding H14).
  withCredentials: true,
})

// Redirect to /login on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('awla_user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// Auth — OAuth2 password flow requires application/x-www-form-urlencoded
export const login = (email, password) => {
  const params = new URLSearchParams()
  params.append('username', email)
  params.append('password', password)
  return api.post('/api/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
}
export const logout = () => api.post('/api/auth/logout')
export const getMe = () => api.get('/api/auth/me')
export const acceptInvite   = (token, password) => api.post('/api/auth/accept-invite', { token, password })
export const forgotPassword = (email)           => api.post('/api/auth/forgot-password', { email })
export const resetPassword  = (token, password) => api.post('/api/auth/reset-password', { token, password })

// User management (manager-only)
export const listUsers  = ()               => api.get('/api/users')
export const inviteUser = (data)           => api.post('/api/users/invite', data)
export const updateUser = (id, data)       => api.patch(`/api/users/${id}`, data)

// Requests
export const submitRequest       = (data)          => api.post('/api/requests', data)
export const submitClarification = (id, data)      => api.post(`/api/requests/${id}/clarification`, data)
export const getRequests         = (config)        => api.get('/api/requests', config)
export const getRequest          = (id)            => api.get(`/api/requests/${id}`)
export const approveRequest      = (id)            => api.patch(`/api/requests/${id}/approve`)
export const rejectRequest       = (id)            => api.patch(`/api/requests/${id}/reject`)
export const updateStatus        = (id, status)    => api.patch(`/api/requests/${id}/status`, { status })
export const updatePriority      = (id, score, reason) => api.patch(`/api/requests/${id}/priority`, { score, reason })

// Reports
export const generateReport = () => api.post('/api/reports/meeting')

// Execution — returns JSON for Dashboard, file blob for Excel/PDF
export const getCharts      = (id) => api.get(`/api/requests/${id}/charts`)
export const executeRequest = (id, format) =>
  api.get(`/api/requests/${id}/execute`, {
    responseType: format === 'Dashboard' ? 'json' : 'blob',
  })

export default api
