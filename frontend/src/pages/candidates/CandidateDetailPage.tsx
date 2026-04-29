import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getCandidate, deleteCandidate, updateCandidate, triggerEmbed } from '../../api/candidates'
import { CandidateStatusBadge, GenderBadge } from '../../components/Badge'
import ConfirmDialog from '../../components/ConfirmDialog'
import type { Candidate, ContactPhone, Job, Sibling } from '../../types'

// ─── Layout helpers ───────────────────────────────────────────────────────────

function Card({ title, children, accent }: {
  title: string
  children: React.ReactNode
  accent?: string
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
      <div className={`px-5 py-3 border-b border-gray-100 ${accent ?? 'bg-gray-50'}`}>
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

function Field({ label, value, wide }: { label: string; value?: React.ReactNode; wide?: boolean }) {
  if (value == null || value === '' || value === false) return null
  return (
    <div className={wide ? 'col-span-2' : ''}>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">{label}</p>
      <p className="text-sm text-gray-900 leading-snug">{value}</p>
    </div>
  )
}

function BoolField({ label, value }: { label: string; value: boolean | null | undefined }) {
  const { t } = useTranslation()
  if (value == null) return null
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">{label}</p>
      <p className={`text-sm font-medium ${value ? 'text-green-700' : 'text-gray-400'}`}>
        {value ? t('common.yes') : t('common.no')}
      </p>
    </div>
  )
}

function Divider() {
  return <hr className="border-gray-100 my-4" />
}

// ─── Section sub-components ───────────────────────────────────────────────────

function JobsDisplay({ jobs }: { jobs: Job[] }) {
  const { t } = useTranslation()
  if (!jobs.length) return null
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
        {t('candidates.jobs')}
      </p>
      <div className="space-y-2">
        {jobs.map((job, i) => (
          <div key={i} className="bg-gray-50 rounded-lg px-3 py-2 text-sm">
            <span className="font-medium text-gray-900">{job.title}</span>
            {job.employer && <span className="text-gray-500"> · {job.employer}</span>}
            {job.description && <p className="text-gray-500 text-xs mt-0.5">{job.description}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}

function SiblingsTable({ siblings }: { siblings: Sibling[] }) {
  const { t } = useTranslation()
  if (!siblings.length) return <p className="text-sm text-gray-400">{t('candidates.no_siblings')}</p>

  const hasSpouseData = siblings.some(s => s.marital_status === 'married' && (s.spouse_lastname || s.support_location || s.spouse_study || s.spouse_occupation))

  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left text-[10px] font-semibold text-gray-400 uppercase pb-2 px-1">{t('candidates.siblings_col_relation')}</th>
            <th className="text-left text-[10px] font-semibold text-gray-400 uppercase pb-2 px-1">{t('candidates.siblings_col_age')}</th>
            <th className="text-left text-[10px] font-semibold text-gray-400 uppercase pb-2 px-1">{t('candidates.siblings_col_institution')}</th>
            <th className="text-left text-[10px] font-semibold text-gray-400 uppercase pb-2 px-1">{t('candidates.siblings_col_status')}</th>
            {hasSpouseData && <>
              <th className="text-left text-[10px] font-semibold text-gray-400 uppercase pb-2 px-1">{t('candidates.siblings_col_spouse')}</th>
              <th className="text-left text-[10px] font-semibold text-gray-400 uppercase pb-2 px-1">{t('candidates.siblings_col_support')}</th>
            </>}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {siblings.map((s, i) => (
            <tr key={i}>
              <td className="py-2 px-1 text-gray-900">{t(`common.sibling_relation.${s.relation}`)}</td>
              <td className="py-2 px-1 text-gray-600">{s.age ?? '—'}</td>
              <td className="py-2 px-1 text-gray-600 max-w-[160px] truncate">{s.institution ?? '—'}</td>
              <td className="py-2 px-1">
                {s.marital_status
                  ? <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${s.marital_status === 'married' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {t(`common.marital_status.${s.marital_status}`)}
                    </span>
                  : <span className="text-gray-300">—</span>}
              </td>
              {hasSpouseData && <>
                <td className="py-2 px-1 text-gray-600 text-xs">
                  {s.spouse_lastname && <div>{s.spouse_lastname}</div>}
                  {s.spouse_study && <div className="text-gray-400">{s.spouse_study}</div>}
                  {s.spouse_occupation && <div className="text-gray-400">{s.spouse_occupation}</div>}
                </td>
                <td className="py-2 px-1 text-gray-600 text-xs">{s.support_location ?? '—'}</td>
              </>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ContactPhonesDisplay({ phones }: { phones: ContactPhone[] }) {
  if (!phones.length) return null
  return (
    <div className="space-y-2">
      {phones.map((p, i) => (
        <div key={i} className="flex items-center gap-3 py-1.5 border-b border-gray-50 last:border-0">
          <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-xs font-bold shrink-0">
            {p.name.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900">{p.name}</p>
            {p.relation && <p className="text-xs text-gray-400">{p.relation}</p>}
          </div>
          <a
            href={`tel:${p.number}`}
            className="text-sm font-mono text-blue-600 hover:text-blue-800 transition-colors"
          >
            {p.number}
          </a>
        </div>
      ))}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type ConfirmKind = 'archive' | 'restore' | 'delete'

export default function CandidateDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()

  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<ConfirmKind | null>(null)
  const [isActing, setIsActing] = useState(false)
  const [isEmbedding, setIsEmbedding] = useState(false)
  const [embedError, setEmbedError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setIsLoading(true)
    getCandidate(id)
      .then(setCandidate)
      .catch(() => setError(t('candidates.error_load_single')))
      .finally(() => setIsLoading(false))
  }, [id])

  const handleArchiveToggle = async () => {
    if (!id || !candidate) return
    setIsActing(true)
    try {
      const updated = await updateCandidate(id, {
        status: candidate.status === 'archived' ? 'active' : 'archived',
      })
      setCandidate(updated)
    } finally {
      setIsActing(false)
      setConfirm(null)
    }
  }

  const handleDelete = async () => {
    if (!id) return
    setIsActing(true)
    try {
      await deleteCandidate(id)
      navigate('/candidates', { replace: true })
    } catch {
      setIsActing(false)
      setConfirm(null)
    }
  }

  const handleEmbed = async () => {
    if (!id) return
    setIsEmbedding(true)
    setEmbedError(null)
    try {
      const updated = await triggerEmbed(id, true)
      setCandidate(updated)
    } catch {
      setEmbedError(t('candidates.embed_error'))
    } finally {
      setIsEmbedding(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (error || !candidate) {
    return <div className="p-6 text-center text-sm text-red-600">{error ?? t('candidates.not_found')}</div>
  }

  const isArchived = candidate.status === 'archived'
  const fullName = `${candidate.first_name} ${candidate.last_name}`
  const { education, family } = candidate

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">

      {/* ── Top header ── */}
      <div>
        <button
          onClick={() => navigate('/candidates')}
          className="text-xs text-gray-400 hover:text-gray-600 mb-3 transition-colors block"
        >
          {t('common.back_arrow')} {t('candidates.back')}
        </button>

        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{fullName}</h1>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <GenderBadge gender={candidate.gender} />
              <CandidateStatusBadge status={candidate.status} />
              {candidate.personal_status && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700">
                  {t(`badges.personal_status.${candidate.personal_status}`)}
                </span>
              )}
              {candidate.is_cohen && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-50 text-yellow-700">
                  {t('candidates.is_cohen')}
                </span>
              )}
              {candidate.has_embeddings
                ? <span className="text-green-600 text-xs font-medium">{t('candidates.ai_ready_label')}</span>
                : <span className="text-gray-400 text-xs">{t('candidates.ai_pending_label')}</span>
              }
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap justify-end">
            <button onClick={() => navigate(`/match-run?candidate=${id}`)}
              className="px-3 py-1.5 text-xs font-medium text-indigo-700 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors">
              {t('candidates.run_match')}
            </button>
            <button onClick={() => navigate(`/suggestions?candidate_id=${id}`)}
              className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              {t('candidates.suggestions_btn')}
            </button>
            <button onClick={handleEmbed} disabled={isEmbedding}
              className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors">
              {isEmbedding ? t('candidates.embed_generating') : t('candidates.embed')}
            </button>
            <button onClick={() => navigate(`/candidates/${id}/edit`)}
              className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              {t('common.edit')}
            </button>
            <button onClick={() => setConfirm(isArchived ? 'restore' : 'archive')}
              className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              {isArchived ? t('common.restore') : t('common.archive')}
            </button>
            <button onClick={() => setConfirm('delete')}
              className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors">
              {t('common.delete')}
            </button>
          </div>
        </div>
        {embedError && <p className="mt-2 text-xs text-red-600">{embedError}</p>}
      </div>

      {/* ── 1. Personal Profile ── */}
      <Card title={t('candidates.section_personal')} accent="bg-blue-50">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-4">
          <Field label={t('candidates.age')} value={candidate.age} />
          <Field label={t('candidates.date_of_birth')} value={candidate.date_of_birth} />
          <Field label={t('candidates.city')} value={candidate.city} />
          <Field label={t('candidates.residence')} value={candidate.residence} />
          <Field label={t('candidates.community')} value={t(`badges.community.${candidate.community}`)} />
          <Field label={t('candidates.sub_sector')} value={candidate.sub_sector} />
          <Field label={t('candidates.halakha_viewpoint')} value={candidate.halakha_viewpoint} />
          <Field label={t('candidates.height')} value={candidate.height ? t('candidates.height_cm', { value: candidate.height }) : undefined} />
          <Field label={t('candidates.hair_color')} value={candidate.hair_color} />
          <Field label={t('candidates.clothing_style')} value={candidate.clothing_style} />
          {candidate.gender === 'male' && (
            <Field label={t('candidates.kova_suit_type')} value={candidate.kova_suit_type} />
          )}
          <Field label={t('candidates.openness')} value={candidate.openness} />
          <Field label={t('candidates.phone_type')} value={candidate.phone_type ? t(`badges.phone_type.${candidate.phone_type}`) : undefined} />
          <Field label={t('candidates.financial_info')} value={candidate.financial_info} />
        </div>

        {candidate.languages.length > 0 && (
          <>
            <Divider />
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                {t('candidates.languages')}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {candidate.languages.map((lang, i) => (
                  <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
                    {lang}
                  </span>
                ))}
              </div>
            </div>
          </>
        )}

        <Divider />
        <div className="grid grid-cols-3 md:grid-cols-5 gap-x-6 gap-y-3">
          <BoolField label={t('candidates.has_license')} value={candidate.has_license} />
          <BoolField label={t('candidates.has_headshot')} value={candidate.has_headshot} />
          {candidate.gender === 'male' && (
            <BoolField label={t('candidates.is_cohen')} value={candidate.is_cohen} />
          )}
        </div>
      </Card>

      {/* ── 2. Education & Career ── */}
      <Card title={t('candidates.section_education')} accent="bg-purple-50">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4">
          <Field label={t('candidates.current_institution')} value={education.current_institution} />
          <Field label={t('candidates.study_type')} value={education.study_type} />
          <Field label={t('candidates.current_study')} value={education.current_study} />
          <BoolField label={t('candidates.is_primary_study')} value={education.is_primary_study} />
          <Field label={t('candidates.profession')} value={education.profession} />
        </div>

        {education.previous_institutions.length > 0 && (
          <>
            <Divider />
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                {t('candidates.previous_institutions')}
              </p>
              <ul className="space-y-0.5">
                {education.previous_institutions.map((inst, i) => (
                  <li key={i} className="text-sm text-gray-700 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-300 shrink-0" />
                    {inst}
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}

        {education.jobs.length > 0 && (
          <>
            <Divider />
            <JobsDisplay jobs={education.jobs} />
          </>
        )}
      </Card>

      {/* ── 3. Character & Preferences ── */}
      <Card title={t('candidates.section_character')} accent="bg-green-50">
        <div className="space-y-5">
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
              {t('candidates.character_traits')}
            </p>
            <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
              {candidate.character_traits || <span className="text-gray-300">—</span>}
            </p>
          </div>

          {candidate.hobbies_aspirations && (
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                {t('candidates.hobbies_aspirations')}
              </p>
              <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                {candidate.hobbies_aspirations}
              </p>
            </div>
          )}

          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
              {t('candidates.preferences')}
            </p>
            <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
              {candidate.preferences || <span className="text-gray-300">—</span>}
            </p>
          </div>
        </div>
      </Card>

      {/* ── 4. Family ── */}
      <Card title={t('candidates.section_family')} accent="bg-amber-50">
        {/* Family meta */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-4 mb-4">
          <Field label={t('candidates.family_style')} value={family.family_style} />
          <Field label={t('candidates.parents_marital_status')} value={family.parents_marital_status ? t(`badges.parents_marital_status.${family.parents_marital_status}`) : undefined} />
          <Field label={t('candidates.family_openness')} value={family.family_openness} />
          <Field label={t('candidates.address')} value={family.address} wide />
        </div>

        {/* Father */}
        <div className="bg-amber-50/60 rounded-xl p-4 mb-3">
          <h3 className="text-xs font-bold text-amber-700 mb-3">{t('candidates.section_father')}</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3">
            <Field label={t('candidates.father_name')} value={family.father_name} />
            <Field label={t('candidates.fathers_profession')} value={family.father_profession || undefined} />
            <Field label={t('candidates.father_occupation_details')} value={family.father_occupation_details} />
            <Field label={t('candidates.father_origin')} value={family.father_origin} />
            <Field label={t('candidates.father_youth_study')} value={family.father_youth_study} />
            <Field label={t('candidates.father_phone')} value={family.father_phone} />
            <BoolField label={t('candidates.father_is_cohen')} value={family.father_is_cohen} />
          </div>
        </div>

        {/* Mother */}
        <div className="bg-pink-50/60 rounded-xl p-4 mb-3">
          <h3 className="text-xs font-bold text-pink-700 mb-3">{t('candidates.section_mother')}</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3">
            <Field label={t('candidates.mother_name')} value={family.mother_name} />
            <Field label={t('candidates.mothers_profession')} value={family.mother_profession || undefined} />
            <Field label={t('candidates.mother_origin')} value={family.mother_origin} />
            <Field label={t('candidates.mother_youth_study')} value={family.mother_youth_study} />
            <Field label={t('candidates.mother_parents_names')} value={family.mother_parents_names} />
            <Field label={t('candidates.mother_phone')} value={family.mother_phone} />
          </div>
        </div>

        {/* Siblings */}
        <div className="mb-3">
          <h3 className="text-xs font-bold text-gray-500 mb-2">
            {t('candidates.section_siblings')} ·{' '}
            <span className="font-normal text-gray-400">
              {t('candidates.sibling_brothers', { count: family.num_brothers })},{' '}
              {t('candidates.sibling_sisters', { count: family.num_sisters })}
            </span>
          </h3>
          <SiblingsTable siblings={family.siblings} />
        </div>

        {/* Family notes */}
        {family.family_notes && (
          <>
            <Divider />
            <Field label={t('candidates.family_notes')} value={family.family_notes} />
          </>
        )}
      </Card>

      {/* ── 5. Contact Numbers ── */}
      {family.contact_phones.length > 0 && (
        <Card title={t('candidates.section_contacts')} accent="bg-teal-50">
          <ContactPhonesDisplay phones={family.contact_phones} />
        </Card>
      )}

      {/* ── 6. Notes ── */}
      {candidate.notes && (
        <Card title={t('candidates.section_notes')}>
          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{candidate.notes}</p>
        </Card>
      )}

      {/* ── Meta ── */}
      <p className="text-xs text-gray-400 text-right">
        Created {new Date(candidate.created_at).toLocaleDateString()} ·{' '}
        Updated {new Date(candidate.updated_at).toLocaleDateString()}
      </p>

      {/* ── Confirm dialogs ── */}
      {confirm === 'archive' && (
        <ConfirmDialog
          title={t('candidates.confirm_archive_title')}
          message={t('candidates.confirm_archive_msg', { name: fullName })}
          confirmLabel={t('common.archive')}
          onConfirm={handleArchiveToggle}
          onCancel={() => setConfirm(null)}
          isLoading={isActing}
        />
      )}
      {confirm === 'restore' && (
        <ConfirmDialog
          title={t('candidates.confirm_restore_title')}
          message={t('candidates.confirm_restore_msg', { name: fullName })}
          confirmLabel={t('common.restore')}
          onConfirm={handleArchiveToggle}
          onCancel={() => setConfirm(null)}
          isLoading={isActing}
        />
      )}
      {confirm === 'delete' && (
        <ConfirmDialog
          title={t('candidates.confirm_delete_title')}
          message={t('candidates.confirm_delete_msg', { name: fullName })}
          confirmLabel={t('common.delete')}
          onConfirm={handleDelete}
          onCancel={() => setConfirm(null)}
          isLoading={isActing}
        />
      )}
    </div>
  )
}
