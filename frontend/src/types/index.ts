// ─── Enums ────────────────────────────────────────────────────────────────────

export type MatchmakerRole = 'admin' | 'matchmaker'
export type Gender = 'male' | 'female'
export type CandidateStatus = 'active' | 'paused' | 'engaged' | 'married' | 'archived'
export type Community = 'litvish' | 'chassidish' | 'dati-leumi' | 'sephardi' | 'mixed'
export type SuggestionStatus = 'proposed' | 'reviewing' | 'contacted' | 'met' | 'declined' | 'engaged'
export type SuggestionSource = 'ai' | 'manual'
export type PersonalStatus = 'single' | 'divorced' | 'widowed' | 'other'
export type PhoneType = 'smartphone' | 'kosher' | 'basic'
export type ParentsMaritalStatus = 'married' | 'divorced' | 'widowed' | 'separated'

// ─── Matchmaker ───────────────────────────────────────────────────────────────

export interface Matchmaker {
  id: string
  username: string
  display_name: string
  email: string | null
  role: MatchmakerRole
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

// ─── Candidate ────────────────────────────────────────────────────────────────

export interface Job {
  title: string
  employer: string | null
  description: string | null
}

export interface ContactPhone {
  number: string
  name: string
  relation: string | null
}

export interface Sibling {
  relation: 'brother' | 'sister'
  age: number | null
  institution: string | null
  marital_status: 'single' | 'married' | null
  spouse_lastname: string | null
  support_location: string | null
  spouse_study: string | null
  spouse_occupation: string | null
}

export interface Education {
  current_institution: string
  current_study: string | null
  previous_institutions: string[]
  is_primary_study: boolean | null
  study_type: string | null
  profession: string | null
  jobs: Job[]
}

export interface Family {
  father_profession: string
  mother_profession: string
  siblings: Sibling[]
  num_brothers: number
  num_sisters: number
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
  parents_marital_status: ParentsMaritalStatus | null
  family_openness: string | null
  address: string | null
  family_notes: string | null
  contact_phones: ContactPhone[]
}

export interface Candidate {
  id: string
  first_name: string
  last_name: string
  gender: Gender
  date_of_birth: string
  age: number
  city: string
  community: Community
  education: Education
  family: Family
  character_traits: string
  preferences: string
  status: CandidateStatus
  notes: string | null
  has_embeddings: boolean
  embedding_model: string
  created_at: string
  updated_at: string
  // Extended personal fields
  personal_status: PersonalStatus | null
  sub_sector: string | null
  halakha_viewpoint: string | null
  languages: string[]
  residence: string | null
  financial_info: string | null
  phone_type: PhoneType | null
  openness: string | null
  clothing_style: string | null
  kova_suit_type: string | null
  has_headshot: boolean | null
  has_license: boolean | null
  is_cohen: boolean | null
  height: number | null
  hair_color: string | null
  hobbies_aspirations: string | null
}

export interface CandidateSummary {
  id: string
  first_name: string
  last_name: string
  gender: Gender
  age: number
  city: string
  community: Community
  current_institution: string
  status: CandidateStatus
  has_embeddings: boolean
}

// ─── Suggestion ───────────────────────────────────────────────────────────────

export interface HistoryEntry {
  status: SuggestionStatus
  at: string
  by: string
  note: string | null
}

export interface ModelVersions {
  embedding: string
  rerank: string
}

export interface Suggestion {
  id: string
  candidate_male_id: string
  candidate_female_id: string
  pair_key: string
  source: SuggestionSource
  status: SuggestionStatus
  ai_score: number | null
  rerank_score: number | null
  rerank_explanation_he: string | null
  rerank_explanation_en: string | null
  model_versions: ModelVersions
  history: HistoryEntry[]
  created_by: string | null
  created_at: string
  updated_at: string
}

// ─── Shared ───────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
