import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getSuggestion, updateSuggestionStatus, deleteSuggestion } from '../../api/suggestions'
import { getCandidate } from '../../api/candidates'
import {
  SuggestionStatusBadge,
  SuggestionSourceBadge,
  GenderBadge,
} from '../../components/Badge'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useAuth } from '../../auth/AuthContext'
import type { Suggestion, Candidate, SuggestionStatus } from '../../types'

const STATUS_OPTIONS: SuggestionStatus[] = [
  'proposed', 'reviewing', 'contacted', 'met', 'declined', 'engaged',
]

// ─── Sub-components ───────────────────────────────────────────────────────────

function CandidateCard({ candidate }: { candidate: Candidate }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  return (
    <div
      onClick={() => navigate(`/candidates/${candidate.id}`)}
      className="flex-1 border border-gray-200 rounded-xl p-4 cursor-pointer hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-center gap-2 mb-2">
        <p className="font-semibold text-gray-900">
          {candidate.first_name} {candidate.last_name}
        </p>
        <GenderBadge gender={candidate.gender} />
      </div>
      <div className="space-y-0.5 text-xs text-gray-500">
        <p>Age {candidate.age} · {candidate.city}</p>
        <p>{t(`badges.community.${candidate.community}`)}</p>
        <p>{candidate.education.current_institution}</p>
      </div>
    </div>
  )
}

function ScoreRow({ label, value }: { label: string; value: number | null }) {
  if (value == null) return null
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-gray-400 w-24">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all"
          style={{ width: `${Math.min(100, value <= 1 ? value * 100 : value * 10)}%` }}
        />
      </div>
      <span className="text-xs font-mono text-gray-700 w-10 text-right">
        {value.toFixed(value <= 1 ? 2 : 1)}
      </span>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SuggestionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { t } = useTranslation()

  const [suggestion, setSuggestion] = useState<Suggestion | null>(null)
  const [male, setMale] = useState<Candidate | null>(null)
  const [female, setFemale] = useState<Candidate | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [newStatus, setNewStatus] = useState<SuggestionStatus>('proposed')
  const [note, setNote] = useState('')
  const [isUpdating, setIsUpdating] = useState(false)
  const [updateError, setUpdateError] = useState<string | null>(null)

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    if (!id) return
    setIsLoading(true)

    getSuggestion(id)
      .then(async (s) => {
        setSuggestion(s)
        setNewStatus(s.status)
        const [m, f] = await Promise.all([
          getCandidate(s.candidate_male_id),
          getCandidate(s.candidate_female_id),
        ])
        setMale(m)
        setFemale(f)
      })
      .catch(() => setError(t('suggestions.error_load_single')))
      .finally(() => setIsLoading(false))
  }, [id])

  const handleStatusUpdate = async () => {
    if (!id || !suggestion) return
    if (newStatus === suggestion.status && !note.trim()) return
    setIsUpdating(true)
    setUpdateError(null)
    try {
      const updated = await updateSuggestionStatus(id, {
        status: newStatus,
        note: note.trim() || null,
      })
      setSuggestion(updated)
      setNote('')
    } catch {
      setUpdateError(t('suggestions.error_update'))
    } finally {
      setIsUpdating(false)
    }
  }

  const handleDelete = async () => {
    if (!id) return
    setIsDeleting(true)
    try {
      await deleteSuggestion(id)
      navigate('/suggestions', { replace: true })
    } catch {
      setIsDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (error || !suggestion) {
    return <div className="p-6 text-center text-sm text-red-600">{error ?? t('suggestions.not_found')}</div>
  }

  const hasAiData = suggestion.ai_score != null || suggestion.rerank_score != null

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/suggestions')}
          className="text-xs text-gray-400 hover:text-gray-600 mb-3 block transition-colors"
        >
          {t('common.back_arrow')} {t('suggestions.back')}
        </button>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-gray-900">{t('suggestions.title_detail')}</h1>
            <SuggestionSourceBadge source={suggestion.source} />
            <SuggestionStatusBadge status={suggestion.status} />
          </div>
          {user?.role === 'admin' && (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200
                         rounded-lg hover:bg-red-50 transition-colors"
            >
              {t('common.delete')}
            </button>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {/* Candidate pair */}
        <div className="flex gap-3">
          {male && <CandidateCard candidate={male} />}
          <div className="flex items-center text-gray-300 text-xl font-light self-center">×</div>
          {female && <CandidateCard candidate={female} />}
        </div>

        {/* AI Scores */}
        {hasAiData && (
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
              {t('suggestions.ai_scores')}
            </h2>
            <div className="space-y-3">
              <ScoreRow label={t('suggestions.cosine_match')} value={suggestion.ai_score} />
              <ScoreRow label={t('suggestions.gpt_score')} value={suggestion.rerank_score} />
            </div>

            {suggestion.rerank_explanation_en && (
              <div className="mt-4 space-y-3">
                <div>
                  <p className="text-xs text-gray-400 mb-1">{t('suggestions.explanation')}</p>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {suggestion.rerank_explanation_en}
                  </p>
                </div>
                {suggestion.rerank_explanation_he && (
                  <div>
                    <p className="text-xs text-gray-400 mb-1">הסבר</p>
                    <p className="text-sm text-gray-700 leading-relaxed text-right" dir="rtl">
                      {suggestion.rerank_explanation_he}
                    </p>
                  </div>
                )}
              </div>
            )}

            {suggestion.model_versions && (
              <p className="mt-3 text-xs text-gray-300 font-mono">
                {suggestion.model_versions.embedding} · {suggestion.model_versions.rerank}
              </p>
            )}
          </div>
        )}

        {/* Status update */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
            {t('suggestions.update_status')}
          </h2>
          <div className="space-y-3">
            <select
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value as SuggestionStatus)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>{t(`badges.suggestion_status.${s}`)}</option>
              ))}
            </select>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('suggestions.note_placeholder')}
              rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {updateError && <p className="text-xs text-red-600">{updateError}</p>}
            <button
              onClick={handleStatusUpdate}
              disabled={isUpdating || (newStatus === suggestion.status && !note.trim())}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg
                         hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isUpdating ? t('suggestions.saving') : t('suggestions.save_update')}
            </button>
          </div>
        </div>

        {/* History timeline */}
        {suggestion.history.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
              {t('suggestions.history')}
            </h2>
            <ol className="relative border-l border-gray-100 space-y-4 ml-2">
              {[...suggestion.history].reverse().map((entry, i) => (
                <li key={i} className="ml-4">
                  <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-gray-300" />
                  <div className="flex items-center gap-2 mb-0.5">
                    <SuggestionStatusBadge status={entry.status} />
                    <span className="text-xs text-gray-400">
                      {new Date(entry.at).toLocaleString()}
                    </span>
                  </div>
                  {entry.note && (
                    <p className="text-sm text-gray-600 mt-1">{entry.note}</p>
                  )}
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Meta */}
        <p className="text-xs text-gray-400 text-right">
          Created {new Date(suggestion.created_at).toLocaleDateString()} ·{' '}
          Updated {new Date(suggestion.updated_at).toLocaleDateString()}
        </p>
      </div>

      {showDeleteConfirm && (
        <ConfirmDialog
          title={t('suggestions.confirm_delete_title')}
          message={t('suggestions.confirm_delete_msg')}
          confirmLabel={t('common.delete')}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
          isLoading={isDeleting}
        />
      )}
    </div>
  )
}
