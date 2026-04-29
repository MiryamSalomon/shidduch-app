import { api } from './client'
import type { Suggestion } from '../types'

export interface MatchRunRequest {
  candidate_id: string
  top_n?: number
  min_score?: number
}

export interface MatchRunResponse {
  candidate_id: string
  total: number
  suggestions: Suggestion[]
}

export async function runMatch(input: MatchRunRequest): Promise<MatchRunResponse> {
  const { data } = await api.post<MatchRunResponse>('/match-run', input)
  return data
}
