import axios from 'axios'

const TOKEN_KEY = 'shidduch_token'

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach stored JWT to every outgoing request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401: clear the token and redirect to login.
// This covers expired tokens and revoked sessions without any per-route
// handling — every API call is protected automatically.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && window.location.pathname !== '/login') {
      localStorage.removeItem(TOKEN_KEY)
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export const setToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token)
}

export const clearToken = (): void => {
  localStorage.removeItem(TOKEN_KEY)
}

export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY)
}
