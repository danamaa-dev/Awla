import { createContext, useContext, useState, useEffect } from 'react'
import { getMe, logout as apiLogout } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  // The session itself now lives in an httpOnly cookie the browser sends
  // automatically -- so on mount we ask the API who (if anyone) that
  // cookie belongs to, rather than trusting a locally-cached user object
  // that could be stale or forged. The cached copy is only used to avoid
  // a blank flash while that request is in flight.
  useEffect(() => {
    let cancelled = false

    try {
      const saved = localStorage.getItem('awla_user')
      if (saved) setUser(JSON.parse(saved))
    } catch {
      localStorage.removeItem('awla_user')
    }

    getMe()
      .then((res) => {
        if (cancelled) return
        setUser(res.data)
        localStorage.setItem('awla_user', JSON.stringify(res.data))
      })
      .catch(() => {
        if (cancelled) return
        setUser(null)
        localStorage.removeItem('awla_user')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [])

  function login(userData) {
    localStorage.setItem('awla_user', JSON.stringify(userData))
    setUser(userData)
  }

  async function logout() {
    try {
      await apiLogout()
    } catch {
      // even if the network call fails, still clear local state below
    }
    localStorage.removeItem('awla_user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
