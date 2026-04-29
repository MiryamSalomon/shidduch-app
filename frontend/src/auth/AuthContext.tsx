import React, { createContext, useContext, useEffect, useState } from 'react'
import { login as apiLogin, register as apiRegister, getMe, type RegisterPayload } from '../api/auth'
import { setToken, clearToken, getToken } from '../api/client'
import type { Matchmaker } from '../types'

interface AuthContextValue {
  user: Matchmaker | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Matchmaker | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // On mount: if a token is stored, fetch the current user to hydrate state.
  // If the token is expired or invalid, the 401 interceptor clears it and the
  // user lands on the login page.
  useEffect(() => {
    if (!getToken()) {
      setIsLoading(false)
      return
    }
    getMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setIsLoading(false))
  }, [])

  const login = async (username: string, password: string): Promise<void> => {
    const response = await apiLogin(username, password)
    setToken(response.access_token)
    setUser(response.matchmaker)
  }

  const register = async (payload: RegisterPayload): Promise<void> => {
    const response = await apiRegister(payload)
    setToken(response.access_token)
    setUser(response.matchmaker)
  }

  const logout = (): void => {
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
