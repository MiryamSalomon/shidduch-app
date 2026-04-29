import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { listCandidates } from '../../api/candidates'
import { CandidateStatusBadge, CommunityBadge, GenderBadge, communityKeys } from '../../components/Badge'
import Pagination from '../../components/Pagination'
import type { CandidateSummary, CandidateStatus, Community, Gender } from '../../types'

const PAGE_SIZE = 20

interface Filters {
  search: string
  gender: Gender | ''
  status: CandidateStatus | ''
  community: Community | ''
  age_min: string
  age_max: string
}

const EMPTY_FILTERS: Filters = {
  search: '', gender: '', status: '', community: '', age_min: '', age_max: '',
}

export default function CandidatesPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<CandidateSummary[]>([])
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

    listCandidates({
      search:    filters.search    || undefined,
      gender:    filters.gender    || undefined,
      status:    filters.status    || undefined,
      community: filters.community || undefined,
      age_min:   filters.age_min ? Number(filters.age_min) : undefined,
      age_max:   filters.age_max ? Number(filters.age_max) : undefined,
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
        if (!cancelled) setError(t('candidates.error_load'))
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => { cancelled = true }
  }, [filters, page])

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{t('candidates.title')}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t('candidates.total', { count: total })}</p>
        </div>
        <button
          onClick={() => navigate('/candidates/new')}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg
                     hover:bg-blue-700 transition-colors"
        >
          {t('candidates.add')}
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* Search */}
          <div className="lg:col-span-2">
            <input
              type="text"
              placeholder={t('candidates.search_placeholder')}
              value={filters.search}
              onChange={(e) => setFilter('search', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Gender */}
          <select
            value={filters.gender}
            onChange={(e) => setFilter('gender', e.target.value as Gender | '')}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{t('candidates.all_genders')}</option>
            <option value="male">{t('badges.gender.male')}</option>
            <option value="female">{t('badges.gender.female')}</option>
          </select>

          {/* Status */}
          <select
            value={filters.status}
            onChange={(e) => setFilter('status', e.target.value as CandidateStatus | '')}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{t('candidates.all_statuses')}</option>
            <option value="active">{t('badges.candidate_status.active')}</option>
            <option value="paused">{t('badges.candidate_status.paused')}</option>
            <option value="engaged">{t('badges.candidate_status.engaged')}</option>
            <option value="married">{t('badges.candidate_status.married')}</option>
            <option value="archived">{t('badges.candidate_status.archived')}</option>
          </select>

          {/* Community */}
          <select
            value={filters.community}
            onChange={(e) => setFilter('community', e.target.value as Community | '')}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{t('candidates.all_communities')}</option>
            {communityKeys.map((key) => (
              <option key={key} value={key}>{t(`badges.community.${key}`)}</option>
            ))}
          </select>

          {/* Age range */}
          <div className="flex gap-1 items-center">
            <input
              type="number"
              placeholder={t('candidates.age_min_placeholder')}
              min={0} max={120}
              value={filters.age_min}
              onChange={(e) => setFilter('age_min', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span className="text-gray-400 text-sm">–</span>
            <input
              type="number"
              placeholder={t('candidates.age_max_placeholder')}
              min={0} max={120}
              value={filters.age_max}
              onChange={(e) => setFilter('age_max', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="mt-3 text-xs text-blue-600 hover:text-blue-800 transition-colors"
          >
            {t('candidates.clear_filters')}
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
            {hasFilters ? t('candidates.no_results_filtered') : t('candidates.no_results_empty')}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('candidates.col_name')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('candidates.col_gender')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('candidates.col_age')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('candidates.col_city')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('candidates.col_community')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('candidates.col_institution')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('candidates.col_status')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('candidates.col_ai')}</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {items.map((c) => (
                    <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {c.first_name} {c.last_name}
                      </td>
                      <td className="px-4 py-3"><GenderBadge gender={c.gender} /></td>
                      <td className="px-4 py-3 text-gray-600">{c.age}</td>
                      <td className="px-4 py-3 text-gray-600">{c.city}</td>
                      <td className="px-4 py-3"><CommunityBadge community={c.community} /></td>
                      <td className="px-4 py-3 text-gray-600 max-w-[160px] truncate">
                        {c.current_institution}
                      </td>
                      <td className="px-4 py-3"><CandidateStatusBadge status={c.status} /></td>
                      <td className="px-4 py-3">
                        {c.has_embeddings
                          ? <span className="text-green-600 text-xs font-medium">{t('candidates.ai_ready')}</span>
                          : <span className="text-gray-400 text-xs">{t('candidates.ai_pending')}</span>
                        }
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => navigate(`/candidates/${c.id}`)}
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
