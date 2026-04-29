import { api } from './client'
import type { Matchmaker } from '../types'

export interface LoginResponse {
  access_token: string
  token_type: string
  matchmaker: Matchmaker
}

export interface RegisterPayload {
  username: string
  display_name: string
  password: string
  email?: string | null
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/login', { username, password })
  return data
}

export async function register(payload: RegisterPayload): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/register', payload)
  return data
}

export async function getMe(): Promise<Matchmaker> {
  const { data } = await api.get<Matchmaker>('/auth/me')
  return data
}
