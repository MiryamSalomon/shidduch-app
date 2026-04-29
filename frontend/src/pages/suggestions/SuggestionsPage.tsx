import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { listSuggestions } from '../../api/suggestions'
import {
  SuggestionStatusBadge,
  SuggestionSourceBadge,
} from '../../components/Badge'
import Pagination from '../../components/Pagination'
import type { Suggestion, SuggestionStatus, SuggestionSource } from '../../types'

const PAGE_SIZE = 20

interface Filters {
  status: SuggestionStatus | ''
  source: SuggestionSource | ''
}

const EMPTY_FILTERS: Filters = { status: '', source: '' }

function shortId(id: string) {
  return id.slice(0, 8) + '…'
}

function scoreBar(score: number | null) {
  if (score == null) return <span className="text-gray-300 text-xs">—</span>
  return (
    <span className="text-xs font-mono text-gray-700">
      {score.toFixed(score < 2 ? 2 : 1)}
    </span>
  )
}

export default function SuggestionsPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const candidateId = searchParams.get('candidate_id') ?? undefined

  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<Suggestion[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const setFilter = <K extends keyof Filters>(key: K, value: Filters[K]) => {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS)
    setPage(1)
  }

  const hasFilters = Object.values(filters).some((v) => v !== '')

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)

    listSuggestions({
      status: filters.status || undefined,
      source: filters.source || undefined,
      candidate_id: candidateId,
      page,
      page_size: PAGE_SIZE,
    })
      .then((res) => {
        if (cancelled) return
        setItems(res.items)
        setTotal(res.total)
        setTotalPages(res.total_pages)
      })
      .catch(() => {
        if (!cancelled) setError(t('suggestions.error_load'))
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => { cancelled = true }
  }, [filters, page, candidateId])

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{t('suggestions.title')}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {candidateId
              ? t('suggestions.total_filtered', { count: total })
              : t('suggestions.total', { count: total })
            }
          </p>
          {candidateId && (
            <button
              onClick={() => navigate(`/match-run?candidate=${candidateId}`)}
              className="mt-1 text-xs text-blue-600 hover:text-blue-800 transition-colors"
            >
              {t('suggestions.rerun_ai')}
            </button>
          )}
        </div>
        <button
          onClick={() => navigate('/suggestions/new')}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg
                     hover:bg-blue-700 transition-colors"
        >
          {t('suggestions.new')}
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4">
        <div className="flex gap-3 flex-wrap">
          <select
            value={filters.status}
            onChange={(e) => setFilter('status', e.target.value as SuggestionStatus | '')}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{t('suggestions.all_statuses')}</option>
            <option value="proposed">{t('badges.suggestion_status.proposed')}</option>
            <option value="reviewing">{t('badges.suggestion_status.reviewing')}</option>
            <option value="contacted">{t('badges.suggestion_status.contacted')}</option>
            <option value="met">{t('badges.suggestion_status.met')}</option>
            <option value="declined">{t('badges.suggestion_status.declined')}</option>
            <option value="engaged">{t('badges.suggestion_status.engaged')}</option>
          </select>

          <select
            value={filters.source}
            onChange={(e) => setFilter('source', e.target.value as SuggestionSource | '')}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{t('suggestions.all_sources')}</option>
            <option value="ai">{t('suggestions.source_ai')}</option>
            <option value="manual">{t('suggestions.source_manual')}</option>
          </select>
        </div>

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="mt-3 text-xs text-blue-600 hover:text-blue-800 transition-colors"
          >
            {t('suggestions.clear_filters')}
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {error ? (
          <div className="p-6 text-center text-sm text-red-600">{error}</div>
        ) : isLoading ? (
          <div className="p-8 text-center">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          </div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">
            {hasFilters
              ? t('suggestions.no_results_filtered')
              : t('suggestions.no_results_empty')}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('suggestions.col_pair')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('suggestions.col_source')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('suggestions.col_status')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('suggestions.col_cosine')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('suggestions.col_gpt')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('suggestions.col_created')}</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {items.map((s) => (
                    <tr key={s.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-gray-500">
                        <span
                          className="text-blue-600 hover:underline cursor-pointer"
                          onClick={() => navigate(`/candidates/${s.candidate_male_id}`)}
                          title={s.candidate_male_id}
                        >
                          {shortId(s.candidate_male_id)}
                        </span>
                        <span className="text-gray-300 mx-1">×</span>
                        <span
                          className="text-pink-600 hover:underline cursor-pointer"
                          onClick={() => navigate(`/candidates/${s.candidate_female_id}`)}
                          title={s.candidate_female_id}
                        >
                          {shortId(s.candidate_female_id)}
                        </span>
                      </td>
                      <td className="px-4 py-3"><SuggestionSourceBadge source={s.source} /></td>
                      <td className="px-4 py-3"><SuggestionStatusBadge status={s.status} /></td>
                      <td className="px-4 py-3">{scoreBar(s.ai_score)}</td>
                      <td className="px-4 py-3">{scoreBar(s.rerank_score)}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {new Date(s.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => navigate(`/suggestions/${s.id}`)}
                          className="text-blue-600 hover:text-blue-800 text-xs font-medium transition-colors"
                        >
                          View {t('common.forward_arrow')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              page={page}
              totalPages={totalPages}
              total={total}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          </>
        )}
      </div>
    </div>
  )
}
