import { api } from './client'
import type { Matchmaker, MatchmakerRole, PaginatedResponse } from '../types'

export interface CreateMatchmakerInput {
  username: string
  password: string
  display_name: string
  email?: string | null
  role?: MatchmakerRole
}

export interface UpdateMatchmakerInput {
  display_name?: string
  email?: string | null
  role?: MatchmakerRole
  password?: string
  is_active?: boolean
}

export async function listMatchmakers(
  page = 1,
  page_size = 20,
): Promise<PaginatedResponse<Matchmaker>> {
  const { data } = await api.get<PaginatedResponse<Matchmaker>>('/matchmakers', {
    params: { page, page_size },
  })
  return data
}

export async function createMatchmaker(input: CreateMatchmakerInput): Promise<Matchmaker> {
  const { data } = await api.post<Matchmaker>('/matchmakers', input)
  return data
}

export async function updateMatchmaker(
  id: string,
  input: UpdateMatchmakerInput,
): Promise<Matchmaker> {
  const { data } = await api.patch<Matchmaker>(`/matchmakers/${id}`, input)
  return data
}

export async function deactivateMatchmaker(id: string): Promise<void> {
  await api.delete(`/matchmakers/${id}`)
}
