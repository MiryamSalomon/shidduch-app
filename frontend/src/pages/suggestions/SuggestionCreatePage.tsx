import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { createSuggestion } from '../../api/suggestions'
import { listCandidates } from '../../api/candidates'
import type { CandidateSummary, Gender } from '../../types'

// ─── Candidate picker scoped to a gender ─────────────────────────────────────

function GenderedPicker({
  gender,
  value,
  onChange,
}: {
  gender: Gender
  value: CandidateSummary | null
  onChange: (c: CandidateSummary | null) => void
}) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<CandidateSummary[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!query || query.length < 2) { setResults([]); return }
    const timer = setTimeout(() => {
      listCandidates({ search: query, gender, status: 'active', page_size: 8 })
        .then((r) => setResults(r.items))
    }, 250)
    return () => clearTimeout(timer)
  }, [query, gender])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const label = gender === 'male' ? t('suggestions.male_candidate') : t('suggestions.female_candidate')
  const placeholder = gender === 'male'
    ? t('suggestions.search_male_placeholder')
    : t('suggestions.search_female_placeholder')
  const accent = gender === 'male' ? 'focus:ring-blue-500' : 'focus:ring-pink-400'

  return (
    <div ref={ref} className="relative">
      <label className="block text-xs font-medium text-gray-500 mb-1">
        {label} <span className="text-red-500">*</span>
      </label>
      <input
        type="text"
        value={value ? `${value.first_name} ${value.last_name}` : query}
        placeholder={placeholder}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
          if (!e.target.value) onChange(null)
        }}
        onFocus={() => setOpen(true)}
        className={`w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ${accent}`}
      />
      {value && (
        <div className="mt-1 px-3 py-2 bg-gray-50 rounded-lg text-xs text-gray-500">
          Age {value.age} · {value.city} · {value.current_institution}
          {!value.has_embeddings && (
            <span className="ml-2 text-yellow-600">{t('suggestions.no_embeddings_warning')}</span>
          )}
        </div>
      )}
      {open && results.length > 0 && !value && (
        <ul className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg
                       shadow-lg overflow-hidden">
          {results.map((c) => (
            <li
              key={c.id}
              onMouseDown={() => { onChange(c); setQuery(''); setOpen(false) }}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 flex items-center justify-between"
            >
              <span className="font-medium">{c.first_name} {c.last_name}</span>
              <span className="text-xs text-gray-400">age {c.age} · {c.city}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SuggestionCreatePage() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [male, setMale] = useState<CandidateSummary | null>(null)
  const [female, setFemale] = useState<CandidateSummary | null>(null)
  const [note, setNote] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = male != null && female != null && !isSubmitting

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!male || !female) return
    setIsSubmitting(true)
    setError(null)
    try {
      const created = await createSuggestion({
        candidate_male_id: male.id,
        candidate_female_id: female.id,
        note: note.trim() || null,
      })
      navigate(`/suggestions/${created.id}`)
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? t('suggestions.error_create'))
      setIsSubmitting(false)
    }
  }

  return (
    <div className="p-6 max-w-xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate('/suggestions')}
          className="text-xs text-gray-400 hover:text-gray-600 mb-2 block transition-colors"
        >
          {t('common.back_arrow')} {t('suggestions.back')}
        </button>
        <h1 className="text-xl font-bold text-gray-900">{t('suggestions.create_title')}</h1>
        <p className="text-sm text-gray-500 mt-0.5">{t('suggestions.create_subtitle')}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <GenderedPicker gender="male" value={male} onChange={setMale} />
          <GenderedPicker gender="female" value={female} onChange={setFemale} />

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              {t('suggestions.note_label')}
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('suggestions.note_placeholder_create')}
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/suggestions')}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300
                       rounded-lg hover:bg-gray-50 transition-colors"
          >
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg
                       hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? t('suggestions.creating') : t('suggestions.create_btn')}
          </button>
        </div>
      </form>
    </div>
  )
}
