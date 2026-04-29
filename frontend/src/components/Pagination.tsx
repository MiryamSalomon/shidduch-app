import { useTranslation } from 'react-i18next'

interface Props {
  page: number
  totalPages: number
  total: number
  pageSize: number
  onPageChange: (page: number) => void
}

export default function Pagination({ page, totalPages, total, pageSize, onPageChange }: Props) {
  const { t } = useTranslation()
  const start = Math.min((page - 1) * pageSize + 1, total)
  const end = Math.min(page * pageSize, total)

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-white">
      <p className="text-sm text-gray-500">
        {total === 0
          ? t('pagination.no_results')
          : t('pagination.showing', { start, end, total })
        }
      </p>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg
                     hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors"
        >
          {t('pagination.prev')}
        </button>
        <span className="text-sm text-gray-600 min-w-[4rem] text-center">
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg
                     hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors"
        >
          {t('pagination.next')}
        </button>
      </div>
    </div>
  )
}
