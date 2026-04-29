import { api } from './client'
import type { Suggestion, SuggestionStatus, PaginatedResponse } from '../types'

export interface ListSuggestionsParams {
  status?: string
  source?: string
  candidate_id?: string
  created_by?: string
  page?: number
  page_size?: number
}

export interface CreateSuggestionInput {
  candidate_male_id: string
  candidate_female_id: string
  note?: string | null
}

export interface UpdateSuggestionStatusInput {
  status: SuggestionStatus
  note?: string | null
}

export async function listSuggestions(
  params: ListSuggestionsParams = {},
): Promise<PaginatedResponse<Suggestion>> {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== undefined),
  )
  const { data } = await api.get<PaginatedResponse<Suggestion>>('/suggestions', { params: clean })
  return data
}

export async function getSuggestion(id: string): Promise<Suggestion> {
  const { data } = await api.get<Suggestion>(`/suggestions/${id}`)
  return data
}

export async function createSuggestion(input: CreateSuggestionInput): Promise<Suggestion> {
  const { data } = await api.post<Suggestion>('/suggestions', input)
  return data
}

export async function updateSuggestionStatus(
  id: string,
  input: UpdateSuggestionStatusInput,
): Promise<Suggestion> {
  const { data } = await api.patch<Suggestion>(`/suggestions/${id}`, input)
  return data
}

export async function deleteSuggestion(id: string): Promise<void> {
  await api.delete(`/suggestions/${id}`)
}
