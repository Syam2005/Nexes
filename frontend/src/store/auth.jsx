import { createContext, useContext, useState, useEffect } from 'react'
import api from '../utils/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('nexus_token')
    if (!token) {
      setLoading(false)
      return
    }
    api.get('/me')
      .then(r => {
        setUser(r.data)
        document.documentElement.setAttribute('data-theme', r.data?.theme || 'dark')
      })
      .catch(() => localStorage.removeItem('nexus_token'))
      .finally(() => setLoading(false))
  }, [])

  const login = (token, userData) => {
    localStorage.setItem('nexus_token', token)
    setUser(userData)
    document.documentElement.setAttribute('data-theme', userData?.theme || 'dark')
  }

  const logout = () => {
    localStorage.removeItem('nexus_token')
    setUser(null)
  }

  const refreshUser = async () => {
    const r = await api.get('/me')
    setUser(r.data)
    document.documentElement.setAttribute('data-theme', r.data?.theme || 'dark')
    return r.data
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)