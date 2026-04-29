import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { runMatch } from '../api/matchRun'
import { listCandidates } from '../api/candidates'
import { SuggestionStatusBadge } from '../components/Badge'
import type { Suggestion, CandidateSummary } from '../types'

// ─── Candidate picker ─────────────────────────────────────────────────────────

function CandidatePicker({
  onChange,
}: {
  onChange: (id: string, name: string) => void
}) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<CandidateSummary[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!query || query.length < 2) { setResults([]); return }
    const timer = setTimeout(() => {
      listCandidates({ search: query, page_size: 8 }).then((r) => setResults(r.items))
    }, 250)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const select = (c: CandidateSummary) => {
    const name = `${c.first_name} ${c.last_name}`
    setQuery(name)
    setOpen(false)
    onChange(c.id, name)
  }

  return (
    <div ref={ref} className="relative">
      <input
        type="text"
        value={query}
        placeholder={t('matchRun.search_placeholder')}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); if (!e.target.value) onChange('', '') }}
        onFocus={() => setOpen(true)}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                   focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      {open && results.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg
                       shadow-lg overflow-hidden">
          {results.map((c) => (
            <li
              key={c.id}
              onMouseDown={() => select(c)}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 flex items-center justify-between"
            >
              <span className="font-medium">{c.first_name} {c.last_name}</span>
              <span className="text-xs text-gray-400">
                {c.gender === 'male' ? 'M' : 'F'} · age {c.age} · {c.city}
                {!c.has_embeddings && ' · ⚠ no embeddings'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ─── Result row ───────────────────────────────────────────────────────────────

function ResultRow({
  rank,
  suggestion,
  isInputMale,
}: {
  rank: number
  suggestion: Suggestion
  isInputMale: boolean
}) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const otherId = isInputMale ? suggestion.candidate_female_id : suggestion.candidate_male_id

  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3 text-gray-400 font-mono text-xs">#{rank}</td>
      <td className="px-4 py-3 font-mono text-xs text-gray-500">
        <button
          onClick={() => navigate(`/candidates/${otherId}`)}
          className="hover:text-blue-600 hover:underline"
          title={otherId}
        >
          {otherId.slice(0, 12)}…
        </button>
      </td>
      <td className="px-4 py-3">
        {suggestion.rerank_score != null
          ? <span className="font-mono text-sm text-gray-800">{suggestion.rerank_score.toFixed(1)}</span>
          : <span className="text-gray-300">—</span>
        }
      </td>
      <td className="px-4 py-3">
        {suggestion.ai_score != null
          ? <span className="font-mono text-xs text-gray-500">{suggestion.ai_score.toFixed(3)}</span>
          : <span className="text-gray-300">—</span>
        }
      </td>
      <td className="px-4 py-3 max-w-[280px]">
        <p className="text-xs text-gray-600 line-clamp-2 leading-relaxed">
          {suggestion.rerank_explanation_en ?? '—'}
        </p>
      </td>
      <td className="px-4 py-3"><SuggestionStatusBadge status={suggestion.status} /></td>
      <td className="px-4 py-3">
        <button
          onClick={() => navigate(`/suggestions/${suggestion.id}`)}
          className="text-blue-600 hover:text-blue-800 text-xs font-medium transition-colors"
        >
          View {t('common.forward_arrow')}
        </button>
      </td>
    </tr>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MatchRunPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [candidateId, setCandidateId] = useState(searchParams.get('candidate') ?? '')
  const [isInputMale, setIsInputMale] = useState(true)
  const [topN, setTopN] = useState(20)
  const [minScore, setMinScore] = useState(0.3)

  const [isRunning, setIsRunning] = useState(false)
  const [results, setResults] = useState<Suggestion[] | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState<number | null>(null)

  const handleRun = async () => {
    if (!candidateId) return
    setIsRunning(true)
    setRunError(null)
    setResults(null)
    setElapsed(null)
    const start = Date.now()
    try {
      const res = await runMatch({ candidate_id: candidateId, top_n: topN, min_score: minScore })
      setResults(res.suggestions)
      setElapsed(Math.round((Date.now() - start) / 100) / 10)
      if (res.suggestions.length > 0) {
        setIsInputMale(res.suggestions[0].candidate_male_id === candidateId)
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        t('matchRun.error_run')
      setRunError(msg)
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">{t('matchRun.title')}</h1>
        <p className="text-sm text-gray-500 mt-0.5">{t('matchRun.subtitle')}</p>
      </div>

      {/* Config panel */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="md:col-span-1">
            <label className="block text-xs font-medium text-gray-500 mb-1">
              {t('matchRun.candidate_label')} <span className="text-red-500">*</span>
            </label>
            <CandidatePicker
              onChange={(id) => setCandidateId(id)}
            />
            {candidateId && (
              <p className="mt-1 text-xs text-gray-400 font-mono">{candidateId}</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              {t('matchRun.top_n_label', { value: topN })}
            </label>
            <input
              type="range"
              min={1} max={50}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>1</span><span>50</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              {t('matchRun.min_cosine_label', { value: minScore.toFixed(2) })}
            </label>
            <input
              type="range"
              min={0} max={100}
              value={Math.round(minScore * 100)}
              onChange={(e) => setMinScore(Number(e.target.value) / 100)}
              className="w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>0.00</span><span>1.00</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={handleRun}
            disabled={!candidateId || isRunning}
            className="px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg
                       hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isRunning ? (
              <span className="flex items-center gap-2">
                <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                {t('matchRun.running')}
              </span>
            ) : t('matchRun.run_btn')}
          </button>
          {elapsed != null && (
            <span className="text-xs text-gray-400">{elapsed}s</span>
          )}
        </div>

        {runError && (
          <p className="mt-3 text-sm text-red-600">{runError}</p>
        )}
      </div>

      {/* Results */}
      {results != null && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <p className="text-sm font-medium text-gray-700">
              {t('matchRun.suggestions_count', { count: results.length })}
            </p>
            <button
              onClick={() => navigate(`/suggestions?candidate_id=${candidateId}`)}
              className="text-xs text-blue-600 hover:text-blue-800 transition-colors"
            >
              {t('matchRun.view_all')}
            </button>
          </div>

          {results.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400">
              {t('matchRun.no_results')}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 text-left font-medium text-gray-500 w-10">{t('matchRun.col_rank')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('matchRun.col_candidate')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('matchRun.col_gpt')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('matchRun.col_cosine')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('matchRun.col_explanation')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('matchRun.col_status')}</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {results.map((s, i) => (
                    <ResultRow
                      key={s.id}
                      rank={i + 1}
                      suggestion={s}
                      isInputMale={isInputMale}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
