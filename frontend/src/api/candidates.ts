import { api } from './client'
import type { Candidate, CandidateSummary, PaginatedResponse } from '../types'

// ─── Input types ──────────────────────────────────────────────────────────────

export interface JobInput {
  title: string
  employer: string | null
  description: string | null
}

export interface ContactPhoneInput {
  number: string
  name: string
  relation: string | null
}

export interface SiblingInput {
  relation: 'brother' | 'sister'
  age: number | null
  institution: string | null
  marital_status: 'single' | 'married' | null
  spouse_lastname: string | null
  support_location: string | null
  spouse_study: string | null
  spouse_occupation: string | null
}

export interface CandidateInput {
  first_name: string
  last_name: string
  gender: 'male' | 'female'
  date_of_birth: string
  city: string
  community: string
  education: {
    current_institution: string
    current_study: string | null
    previous_institutions: string[]
    is_primary_study: boolean | null
    study_type: string | null
    profession: string | null
    jobs: JobInput[]
  }
  family: {
    father_profession: string
    mother_profession: string
    siblings: SiblingInput[]
    father_name: string | null
    father_is_cohen: boolean | null
    father_origin: string | null
    father_occupation_details: string | null
    father_youth_study: string | null
    father_phone: string | null
    mother_name: string | null
    mother_origin: string | null
    mother_youth_study: string | null
    mother_parents_names: string | null
    mother_phone: string | null
    family_style: string | null
    parents_marital_status: string | null
    family_openness: string | null
    address: string | null
    family_notes: string | null
    contact_phones: ContactPhoneInput[]
  }
  character_traits: string
  preferences: string
  status?: string
  notes?: string | null
  personal_status?: string | null
  sub_sector?: string | null
  halakha_viewpoint?: string | null
  languages?: string[]
  residence?: string | null
  financial_info?: string | null
  phone_type?: string | null
  openness?: string | null
  clothing_style?: string | null
  kova_suit_type?: string | null
  has_headshot?: boolean | null
  has_license?: boolean | null
  is_cohen?: boolean | null
  height?: number | null
  hair_color?: string | null
  hobbies_aspirations?: string | null
}

export interface ListCandidatesParams {
  gender?: string
  status?: string
  community?: string
  age_min?: number
  age_max?: number
  search?: string
  page?: number
  page_size?: number
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function listCandidates(
  params: ListCandidatesParams = {},
): Promise<PaginatedResponse<CandidateSummary>> {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== undefined),
  )
  const { data } = await api.get<PaginatedResponse<CandidateSummary>>('/candidates', { params: clean })
  return data
}

export async function getCandidate(id: string): Promise<Candidate> {
  const { data } = await api.get<Candidate>(`/candidates/${id}`)
  return data
}

export async function createCandidate(input: CandidateInput): Promise<Candidate> {
  const { data } = await api.post<Candidate>('/candidates', input)
  return data
}

export async function updateCandidate(id: string, input: Partial<CandidateInput>): Promise<Candidate> {
  const { data } = await api.patch<Candidate>(`/candidates/${id}`, input)
  return data
}

export async function deleteCandidate(id: string): Promise<void> {
  await api.delete(`/candidates/${id}`)
}

export async function triggerEmbed(id: string, force = false): Promise<Candidate> {
  const { data } = await api.post<Candidate>(
    `/candidates/${id}/embed`,
    null,
    { params: { force } },
  )
  return data
}
