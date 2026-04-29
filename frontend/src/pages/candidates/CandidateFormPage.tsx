import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useForm, useFieldArray } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { getCandidate, createCandidate, updateCandidate } from '../../api/candidates'
import { communityKeys } from '../../components/Badge'
import type { Community, CandidateStatus } from '../../types'

// ─── Types ────────────────────────────────────────────────────────────────────

type BoolStr = '' | 'true' | 'false'

type SiblingRow = {
  relation: 'brother' | 'sister'
  age: string
  institution: string
  marital_status: '' | 'single' | 'married'
  spouse_lastname: string
  support_location: string
  spouse_study: string
  spouse_occupation: string
}

type JobRow = { title: string; employer: string; description: string }
type StrItem = { value: string }
type ContactRow = { number: string; name: string; relation: string }

type FormValues = {
  first_name: string
  last_name: string
  gender: 'male' | 'female'
  date_of_birth: string
  city: string
  community: Community
  status: CandidateStatus
  personal_status: string
  sub_sector: string
  halakha_viewpoint: string
  languages: StrItem[]
  residence: string
  financial_info: string
  phone_type: string
  openness: string
  clothing_style: string
  kova_suit_type: string
  has_headshot: BoolStr
  has_license: BoolStr
  is_cohen: BoolStr
  height: string
  hair_color: string
  current_institution: string
  current_study: string
  is_primary_study: BoolStr
  study_type: string
  profession: string
  prev_inst: StrItem[]
  jobs: JobRow[]
  character_traits: string
  preferences: string
  hobbies_aspirations: string
  father_profession: string
  mother_profession: string
  family_style: string
  parents_marital_status: string
  family_openness: string
  address: string
  family_notes: string
  father_name: string
  father_is_cohen: BoolStr
  father_origin: string
  father_occupation_details: string
  father_youth_study: string
  father_phone: string
  mother_name: string
  mother_origin: string
  mother_youth_study: string
  mother_parents_names: string
  mother_phone: string
  siblings: SiblingRow[]
  contact_phones: ContactRow[]
  notes: string
}

const EMPTY: FormValues = {
  first_name: '', last_name: '', gender: 'male',
  date_of_birth: '', city: '', community: 'litvish', status: 'active',
  personal_status: '', sub_sector: '', halakha_viewpoint: '',
  languages: [], residence: '', financial_info: '', phone_type: '',
  openness: '', clothing_style: '', kova_suit_type: '',
  has_headshot: '', has_license: '', is_cohen: '', height: '', hair_color: '',
  current_institution: '', current_study: '',
  is_primary_study: '', study_type: '', profession: '',
  prev_inst: [], jobs: [],
  character_traits: '', preferences: '', hobbies_aspirations: '',
  father_profession: '', mother_profession: '',
  family_style: '', parents_marital_status: '', family_openness: '', address: '', family_notes: '',
  father_name: '', father_is_cohen: '', father_origin: '', father_occupation_details: '',
  father_youth_study: '', father_phone: '',
  mother_name: '', mother_origin: '', mother_youth_study: '', mother_parents_names: '', mother_phone: '',
  siblings: [], contact_phones: [], notes: '',
}

function parseBool(s: BoolStr): boolean | null {
  if (s === 'true') return true
  if (s === 'false') return false
  return null
}

// ─── UI helpers ───────────────────────────────────────────────────────────────

const inputCls =
  'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white'

const selectCls =
  'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white'

const textareaCls =
  'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none'

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs font-medium text-gray-500 mb-1">
      {children}{required && <span className="text-red-500 ms-0.5">*</span>}
    </label>
  )
}

function ErrorMsg({ msg }: { msg?: string }) {
  return msg ? <p className="mt-1 text-xs text-red-600">{msg}</p> : null
}

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">{title}</h2>
      {children}
    </div>
  )
}

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5 pt-4 border-t border-gray-100">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  )
}

function AddBtn({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-xs text-blue-600 hover:text-blue-800 transition-colors"
    >
      {label}
    </button>
  )
}

function RemoveBtn({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-gray-300 hover:text-red-500 transition-colors px-1 flex-shrink-0 leading-none text-base"
      title="Remove"
    >
      ✕
    </button>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CandidateFormPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const isEdit = Boolean(id)

  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isLoadingData, setIsLoadingData] = useState(isEdit)

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ defaultValues: EMPTY })

  const gender = watch('gender')
  const isMale = gender === 'male'
  const watchedSiblings = watch('siblings')

  const { fields: siblings, append: addSibling, remove: removeSibling } =
    useFieldArray({ control, name: 'siblings' })

  const { fields: prevInst, append: addPrevInst, remove: removePrevInst } =
    useFieldArray({ control, name: 'prev_inst' })

  const { fields: jobs, append: addJob, remove: removeJob } =
    useFieldArray({ control, name: 'jobs' })

  const { fields: languages, append: addLang, remove: removeLang } =
    useFieldArray({ control, name: 'languages' })

  const { fields: contacts, append: addContact, remove: removeContact } =
    useFieldArray({ control, name: 'contact_phones' })

  useEffect(() => {
    if (!id) return
    getCandidate(id)
      .then((c) => {
        reset({
          first_name: c.first_name,
          last_name: c.last_name,
          gender: c.gender,
          date_of_birth: c.date_of_birth,
          city: c.city,
          community: c.community,
          status: c.status,
          personal_status: c.personal_status ?? '',
          sub_sector: c.sub_sector ?? '',
          halakha_viewpoint: c.halakha_viewpoint ?? '',
          languages: c.languages.map((v) => ({ value: v })),
          residence: c.residence ?? '',
          financial_info: c.financial_info ?? '',
          phone_type: c.phone_type ?? '',
          openness: c.openness ?? '',
          clothing_style: c.clothing_style ?? '',
          kova_suit_type: c.kova_suit_type ?? '',
          has_headshot: c.has_headshot == null ? '' : c.has_headshot ? 'true' : 'false',
          has_license: c.has_license == null ? '' : c.has_license ? 'true' : 'false',
          is_cohen: c.is_cohen == null ? '' : c.is_cohen ? 'true' : 'false',
          height: c.height != null ? String(c.height) : '',
          hair_color: c.hair_color ?? '',
          current_institution: c.education.current_institution,
          current_study: c.education.current_study ?? '',
          is_primary_study: c.education.is_primary_study == null ? '' : c.education.is_primary_study ? 'true' : 'false',
          study_type: c.education.study_type ?? '',
          profession: c.education.profession ?? '',
          prev_inst: c.education.previous_institutions.map((v) => ({ value: v })),
          jobs: c.education.jobs.map((j) => ({
            title: j.title,
            employer: j.employer ?? '',
            description: j.description ?? '',
          })),
          character_traits: c.character_traits,
          preferences: c.preferences,
          hobbies_aspirations: c.hobbies_aspirations ?? '',
          father_profession: c.family.father_profession,
          mother_profession: c.family.mother_profession,
          family_style: c.family.family_style ?? '',
          parents_marital_status: c.family.parents_marital_status ?? '',
          family_openness: c.family.family_openness ?? '',
          address: c.family.address ?? '',
          family_notes: c.family.family_notes ?? '',
          father_name: c.family.father_name ?? '',
          father_is_cohen: c.family.father_is_cohen == null ? '' : c.family.father_is_cohen ? 'true' : 'false',
          father_origin: c.family.father_origin ?? '',
          father_occupation_details: c.family.father_occupation_details ?? '',
          father_youth_study: c.family.father_youth_study ?? '',
          father_phone: c.family.father_phone ?? '',
          mother_name: c.family.mother_name ?? '',
          mother_origin: c.family.mother_origin ?? '',
          mother_youth_study: c.family.mother_youth_study ?? '',
          mother_parents_names: c.family.mother_parents_names ?? '',
          mother_phone: c.family.mother_phone ?? '',
          siblings: c.family.siblings.map((s) => ({
            relation: s.relation,
            age: s.age != null ? String(s.age) : '',
            institution: s.institution ?? '',
            marital_status: s.marital_status ?? '',
            spouse_lastname: s.spouse_lastname ?? '',
            support_location: s.support_location ?? '',
            spouse_study: s.spouse_study ?? '',
            spouse_occupation: s.spouse_occupation ?? '',
          })),
          contact_phones: c.family.contact_phones.map((cp) => ({
            number: cp.number,
            name: cp.name,
            relation: cp.relation ?? '',
          })),
          notes: c.notes ?? '',
        })
      })
      .catch(() => setLoadError(t('candidates.form_error_load')))
      .finally(() => setIsLoadingData(false))
  }, [id, reset, t])

  const onSubmit = async (values: FormValues) => {
    setSubmitError(null)
    const payload = {
      first_name: values.first_name,
      last_name: values.last_name,
      gender: values.gender,
      date_of_birth: values.date_of_birth,
      city: values.city,
      community: values.community,
      status: values.status,
      personal_status: values.personal_status || null,
      sub_sector: values.sub_sector || null,
      halakha_viewpoint: values.halakha_viewpoint || null,
      languages: values.languages.map((l) => l.value).filter(Boolean),
      residence: values.residence || null,
      financial_info: values.financial_info || null,
      phone_type: values.phone_type || null,
      openness: values.openness || null,
      clothing_style: values.clothing_style || null,
      kova_suit_type: values.kova_suit_type || null,
      has_headshot: parseBool(values.has_headshot),
      has_license: parseBool(values.has_license),
      is_cohen: parseBool(values.is_cohen),
      height: values.height !== '' ? Number(values.height) : null,
      hair_color: values.hair_color || null,
      hobbies_aspirations: values.hobbies_aspirations || null,
      education: {
        current_institution: values.current_institution,
        current_study: values.current_study || null,
        is_primary_study: parseBool(values.is_primary_study),
        study_type: values.study_type || null,
        profession: values.profession || null,
        previous_institutions: values.prev_inst.map((p) => p.value).filter(Boolean),
        jobs: values.jobs
          .filter((j) => j.title.trim())
          .map((j) => ({
            title: j.title,
            employer: j.employer || null,
            description: j.description || null,
          })),
      },
      family: {
        father_profession: values.father_profession,
        mother_profession: values.mother_profession,
        family_style: values.family_style || null,
        parents_marital_status: values.parents_marital_status || null,
        family_openness: values.family_openness || null,
        address: values.address || null,
        family_notes: values.family_notes || null,
        father_name: values.father_name || null,
        father_is_cohen: parseBool(values.father_is_cohen),
        father_origin: values.father_origin || null,
        father_occupation_details: values.father_occupation_details || null,
        father_youth_study: values.father_youth_study || null,
        father_phone: values.father_phone || null,
        mother_name: values.mother_name || null,
        mother_origin: values.mother_origin || null,
        mother_youth_study: values.mother_youth_study || null,
        mother_parents_names: values.mother_parents_names || null,
        mother_phone: values.mother_phone || null,
        siblings: values.siblings.map((s) => ({
          relation: s.relation,
          age: s.age !== '' ? Number(s.age) : null,
          institution: s.institution || null,
          marital_status: (s.marital_status || null) as 'single' | 'married' | null,
          spouse_lastname: s.spouse_lastname || null,
          support_location: s.support_location || null,
          spouse_study: s.spouse_study || null,
          spouse_occupation: s.spouse_occupation || null,
        })),
        contact_phones: values.contact_phones
          .filter((c) => c.number.trim())
          .map((c) => ({
            number: c.number,
            name: c.name,
            relation: c.relation || null,
          })),
      },
      character_traits: values.character_traits,
      preferences: values.preferences,
      notes: values.notes || null,
    }

    try {
      if (isEdit && id) {
        await updateCandidate(id, payload)
        navigate(`/candidates/${id}`)
      } else {
        const created = await createCandidate(payload)
        navigate(`/candidates/${created.id}`)
      }
    } catch {
      setSubmitError(t('candidates.form_error_save'))
    }
  }

  if (isLoadingData) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (loadError) {
    return <div className="p-6 text-center text-sm text-red-600">{loadError}</div>
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">

      {/* Header */}
      <div className="mb-6">
        <button
          type="button"
          onClick={() => navigate(isEdit && id ? `/candidates/${id}` : '/candidates')}
          className="text-xs text-gray-400 hover:text-gray-600 mb-2 transition-colors block"
        >
          {t('common.back_arrow')} {t('candidates.back')}
        </button>
        <h1 className="text-xl font-bold text-gray-900">
          {isEdit ? t('candidates.form_title_edit') : t('candidates.form_title_create')}
        </h1>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">

        {/* ── Personal Profile ─────────────────────────────────────────────── */}
        <FormSection title={t('candidates.section_personal')}>

          {/* Name */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <Label required>First Name</Label>
              <input {...register('first_name', { required: t('common.required') })} className={inputCls} />
              <ErrorMsg msg={errors.first_name?.message} />
            </div>
            <div>
              <Label required>Last Name</Label>
              <input {...register('last_name', { required: t('common.required') })} className={inputCls} />
              <ErrorMsg msg={errors.last_name?.message} />
            </div>
          </div>

          {/* Core identity */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <Label required>{t('candidates.form_gender')}</Label>
              <select {...register('gender')} className={selectCls}>
                <option value="male">{t('candidates.form_gender_male')}</option>
                <option value="female">{t('candidates.form_gender_female')}</option>
              </select>
            </div>
            <div>
              <Label required>{t('candidates.date_of_birth')}</Label>
              <input
                type="date"
                {...register('date_of_birth', { required: t('common.required') })}
                className={inputCls}
              />
              <ErrorMsg msg={errors.date_of_birth?.message} />
            </div>
            <div>
              <Label required>{t('candidates.city')}</Label>
              <input {...register('city', { required: t('common.required') })} className={inputCls} />
              <ErrorMsg msg={errors.city?.message} />
            </div>
            <div>
              <Label required>{t('candidates.community')}</Label>
              <select {...register('community')} className={selectCls}>
                {communityKeys.map((key) => (
                  <option key={key} value={key}>{t(`badges.community.${key}`)}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Extended personal */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <Label>{t('candidates.personal_status')}</Label>
              <select {...register('personal_status')} className={selectCls}>
                <option value="">—</option>
                <option value="single">{t('badges.personal_status.single')}</option>
                <option value="divorced">{t('badges.personal_status.divorced')}</option>
                <option value="widowed">{t('badges.personal_status.widowed')}</option>
                <option value="other">{t('badges.personal_status.other')}</option>
              </select>
            </div>
            <div>
              <Label>{t('candidates.sub_sector')}</Label>
              <input {...register('sub_sector')} className={inputCls} />
            </div>
            <div>
              <Label>{t('candidates.halakha_viewpoint')}</Label>
              <input {...register('halakha_viewpoint')} className={inputCls} />
            </div>
            <div>
              <Label>{t('candidates.phone_type')}</Label>
              <select {...register('phone_type')} className={selectCls}>
                <option value="">—</option>
                <option value="smartphone">{t('badges.phone_type.smartphone')}</option>
                <option value="kosher">{t('badges.phone_type.kosher')}</option>
                <option value="basic">{t('badges.phone_type.basic')}</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <Label>{t('candidates.residence')}</Label>
              <input {...register('residence')} className={inputCls} />
            </div>
            <div>
              <Label>{t('candidates.financial_info')}</Label>
              <input {...register('financial_info')} className={inputCls} />
            </div>
          </div>

          {/* Style / appearance */}
          <div className={`grid gap-4 mb-4 ${isMale ? 'grid-cols-3' : 'grid-cols-2'}`}>
            <div>
              <Label>{t('candidates.openness')}</Label>
              <input {...register('openness')} className={inputCls} />
            </div>
            <div>
              <Label>{t('candidates.clothing_style')}</Label>
              <input {...register('clothing_style')} className={inputCls} />
            </div>
            {isMale && (
              <div>
                <Label>{t('candidates.kova_suit_type')}</Label>
                <input {...register('kova_suit_type')} className={inputCls} />
              </div>
            )}
          </div>

          {/* Physical + flags */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <Label>{t('candidates.height')}</Label>
              <input
                type="number"
                min={100} max={250}
                {...register('height')}
                className={inputCls}
                placeholder="cm"
              />
            </div>
            <div>
              <Label>{t('candidates.hair_color')}</Label>
              <input {...register('hair_color')} className={inputCls} />
            </div>
            <div>
              <Label>{t('candidates.has_headshot')}</Label>
              <select {...register('has_headshot')} className={selectCls}>
                <option value="">—</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </div>
            <div>
              <Label>{t('candidates.has_license')}</Label>
              <select {...register('has_license')} className={selectCls}>
                <option value="">—</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </div>
          </div>

          {isMale && (
            <div className="max-w-[160px] mb-4">
              <Label>{t('candidates.is_cohen')}</Label>
              <select {...register('is_cohen')} className={selectCls}>
                <option value="">—</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </div>
          )}

          {/* Languages */}
          <div>
            <Label>{t('candidates.languages')}</Label>
            <div className="space-y-2">
              {languages.map((field, i) => (
                <div key={field.id} className="flex gap-2">
                  <input
                    {...register(`languages.${i}.value`)}
                    className={inputCls}
                    placeholder="e.g. Hebrew, English, Yiddish"
                  />
                  <RemoveBtn onClick={() => removeLang(i)} />
                </div>
              ))}
              <AddBtn onClick={() => addLang({ value: '' })} label="+ Add language" />
            </div>
          </div>

          {/* Status (edit only) */}
          {isEdit && (
            <div className="mt-4 max-w-[160px]">
              <Label>{t('candidates.form_status')}</Label>
              <select {...register('status')} className={selectCls}>
                <option value="active">{t('badges.candidate_status.active')}</option>
                <option value="paused">{t('badges.candidate_status.paused')}</option>
                <option value="engaged">{t('badges.candidate_status.engaged')}</option>
                <option value="married">{t('badges.candidate_status.married')}</option>
                <option value="archived">{t('badges.candidate_status.archived')}</option>
              </select>
            </div>
          )}
        </FormSection>

        {/* ── Education & Career ───────────────────────────────────────────── */}
        <FormSection title={t('candidates.section_education')}>

          <div className="mb-4">
            <Label required>{t('candidates.form_current_institution')}</Label>
            <input
              {...register('current_institution', { required: t('common.required') })}
              className={inputCls}
              placeholder={t('candidates.form_current_institution_placeholder')}
            />
            <ErrorMsg msg={errors.current_institution?.message} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
            <div>
              <Label>{t('candidates.form_current_study')}</Label>
              <input
                {...register('current_study')}
                className={inputCls}
                placeholder={t('candidates.form_current_study_placeholder')}
              />
            </div>
            <div>
              <Label>{t('candidates.is_primary_study')}</Label>
              <select {...register('is_primary_study')} className={selectCls}>
                <option value="">—</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </div>
            <div>
              <Label>{t('candidates.study_type')}</Label>
              <input {...register('study_type')} className={inputCls} />
            </div>
          </div>

          <div className="mb-4">
            <Label>{t('candidates.profession')}</Label>
            <input {...register('profession')} className={inputCls} />
          </div>

          {/* Previous Institutions */}
          <div className="mb-4">
            <Label>{t('candidates.form_prev_institutions')}</Label>
            <div className="space-y-2">
              {prevInst.map((field, i) => (
                <div key={field.id} className="flex gap-2">
                  <input
                    {...register(`prev_inst.${i}.value`)}
                    className={inputCls}
                    placeholder={t('candidates.form_prev_institution_placeholder')}
                  />
                  <RemoveBtn onClick={() => removePrevInst(i)} />
                </div>
              ))}
              <AddBtn onClick={() => addPrevInst({ value: '' })} label={t('candidates.form_add_institution')} />
            </div>
          </div>

          {/* Jobs */}
          <div>
            <Label>{t('candidates.jobs')}</Label>
            <div className="space-y-3">
              {jobs.map((field, i) => (
                <div key={field.id} className="border border-gray-100 rounded-lg p-3 bg-gray-50 relative">
                  <RemoveBtn onClick={() => removeJob(i)} />
                  <div className="grid grid-cols-2 gap-3 mb-2">
                    <div>
                      <Label>{t('candidates.job_title')}</Label>
                      <input {...register(`jobs.${i}.title`)} className={inputCls} />
                    </div>
                    <div>
                      <Label>{t('candidates.job_employer')}</Label>
                      <input {...register(`jobs.${i}.employer`)} className={inputCls} />
                    </div>
                  </div>
                  <div>
                    <Label>{t('candidates.job_description')}</Label>
                    <input {...register(`jobs.${i}.description`)} className={inputCls} />
                  </div>
                </div>
              ))}
              <AddBtn
                onClick={() => addJob({ title: '', employer: '', description: '' })}
                label={t('candidates.add_job')}
              />
            </div>
          </div>
        </FormSection>

        {/* ── Character & Preferences ──────────────────────────────────────── */}
        <FormSection title={t('candidates.section_character')}>
          <div className="space-y-4">
            <div>
              <Label required>{t('candidates.character_traits')}</Label>
              <textarea
                {...register('character_traits', {
                  required: t('common.required'),
                  minLength: { value: 10, message: t('candidates.form_min_length', { min: 10 }) },
                })}
                rows={4}
                placeholder={t('candidates.form_traits_placeholder')}
                className={textareaCls}
              />
              <ErrorMsg msg={errors.character_traits?.message} />
            </div>
            <div>
              <Label required>{t('candidates.preferences')}</Label>
              <textarea
                {...register('preferences', {
                  required: t('common.required'),
                  minLength: { value: 10, message: t('candidates.form_min_length', { min: 10 }) },
                })}
                rows={4}
                placeholder={t('candidates.form_prefs_placeholder')}
                className={textareaCls}
              />
              <ErrorMsg msg={errors.preferences?.message} />
            </div>
            <div>
              <Label>{t('candidates.hobbies_aspirations')}</Label>
              <textarea
                {...register('hobbies_aspirations')}
                rows={3}
                placeholder={t('candidates.form_hobbies_placeholder')}
                className={textareaCls}
              />
            </div>
          </div>
        </FormSection>

        {/* ── Family ───────────────────────────────────────────────────────── */}
        <FormSection title={t('candidates.section_family')}>

          {/* Professions */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <Label required>{t('candidates.fathers_profession')}</Label>
              <input {...register('father_profession', { required: t('common.required') })} className={inputCls} />
              <ErrorMsg msg={errors.father_profession?.message} />
            </div>
            <div>
              <Label required>{t('candidates.mothers_profession')}</Label>
              <input {...register('mother_profession', { required: t('common.required') })} className={inputCls} />
              <ErrorMsg msg={errors.mother_profession?.message} />
            </div>
          </div>

          {/* Family style */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
            <div>
              <Label>{t('candidates.family_style')}</Label>
              <input {...register('family_style')} className={inputCls} />
            </div>
            <div>
              <Label>{t('candidates.parents_marital_status')}</Label>
              <select {...register('parents_marital_status')} className={selectCls}>
                <option value="">—</option>
                <option value="married">{t('badges.parents_marital_status.married')}</option>
                <option value="divorced">{t('badges.parents_marital_status.divorced')}</option>
                <option value="widowed">{t('badges.parents_marital_status.widowed')}</option>
                <option value="separated">{t('badges.parents_marital_status.separated')}</option>
              </select>
            </div>
            <div>
              <Label>{t('candidates.family_openness')}</Label>
              <input {...register('family_openness')} className={inputCls} />
            </div>
          </div>

          <div className="mb-4">
            <Label>{t('candidates.address')}</Label>
            <input {...register('address')} className={inputCls} />
          </div>

          {/* ── Father ── */}
          <SubSection title={t('candidates.section_father')}>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-3">
              <div>
                <Label>{t('candidates.father_name')}</Label>
                <input {...register('father_name')} className={inputCls} />
              </div>
              <div>
                <Label>{t('candidates.father_origin')}</Label>
                <input {...register('father_origin')} className={inputCls} />
              </div>
              <div>
                <Label>{t('candidates.father_is_cohen')}</Label>
                <select {...register('father_is_cohen')} className={selectCls}>
                  <option value="">—</option>
                  <option value="true">{t('common.yes')}</option>
                  <option value="false">{t('common.no')}</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <Label>{t('candidates.father_occupation_details')}</Label>
                <input {...register('father_occupation_details')} className={inputCls} />
              </div>
              <div>
                <Label>{t('candidates.father_youth_study')}</Label>
                <input {...register('father_youth_study')} className={inputCls} />
              </div>
              <div>
                <Label>{t('candidates.father_phone')}</Label>
                <input type="tel" {...register('father_phone')} className={inputCls} />
              </div>
            </div>
          </SubSection>

          {/* ── Mother ── */}
          <SubSection title={t('candidates.section_mother')}>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-3">
              <div>
                <Label>{t('candidates.mother_name')}</Label>
                <input {...register('mother_name')} className={inputCls} />
              </div>
              <div>
                <Label>{t('candidates.mother_origin')}</Label>
                <input {...register('mother_origin')} className={inputCls} />
              </div>
              <div>
                <Label>{t('candidates.mother_youth_study')}</Label>
                <input {...register('mother_youth_study')} className={inputCls} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>{t('candidates.mother_parents_names')}</Label>
                <input {...register('mother_parents_names')} className={inputCls} />
              </div>
              <div>
                <Label>{t('candidates.mother_phone')}</Label>
                <input type="tel" {...register('mother_phone')} className={inputCls} />
              </div>
            </div>
          </SubSection>

          {/* ── Siblings ── */}
          <SubSection title={t('candidates.section_siblings')}>
            <div className="space-y-3">
              {siblings.map((field, i) => {
                const isMarried = watchedSiblings?.[i]?.marital_status === 'married'
                return (
                  <div key={field.id} className="border border-gray-100 rounded-lg p-3 bg-gray-50">
                    {/* Main row */}
                    <div className="grid grid-cols-4 gap-2 items-end mb-2">
                      <div>
                        <Label>{t('candidates.siblings_col_relation')}</Label>
                        <select {...register(`siblings.${i}.relation`)} className={selectCls}>
                          <option value="brother">{t('candidates.form_sibling_brother')}</option>
                          <option value="sister">{t('candidates.form_sibling_sister')}</option>
                        </select>
                      </div>
                      <div>
                        <Label>{t('candidates.siblings_col_age')}</Label>
                        <input
                          type="number" min={0} max={120}
                          {...register(`siblings.${i}.age`)}
                          className={inputCls}
                        />
                      </div>
                      <div>
                        <Label>{t('candidates.siblings_col_institution')}</Label>
                        <input {...register(`siblings.${i}.institution`)} className={inputCls} />
                      </div>
                      <div className="flex gap-1 items-end">
                        <div className="flex-1">
                          <Label>{t('candidates.siblings_col_status')}</Label>
                          <select {...register(`siblings.${i}.marital_status`)} className={selectCls}>
                            <option value="">{t('candidates.form_marital_none')}</option>
                            <option value="single">{t('candidates.form_marital_single')}</option>
                            <option value="married">{t('candidates.form_marital_married')}</option>
                          </select>
                        </div>
                        <RemoveBtn onClick={() => removeSibling(i)} />
                      </div>
                    </div>
                    {/* Spouse fields — shown when married */}
                    {isMarried && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2 border-t border-gray-200">
                        <div>
                          <Label>{t('candidates.sibling_spouse_lastname')}</Label>
                          <input {...register(`siblings.${i}.spouse_lastname`)} className={inputCls} />
                        </div>
                        <div>
                          <Label>{t('candidates.sibling_support_location')}</Label>
                          <input {...register(`siblings.${i}.support_location`)} className={inputCls} />
                        </div>
                        <div>
                          <Label>{t('candidates.sibling_spouse_study')}</Label>
                          <input {...register(`siblings.${i}.spouse_study`)} className={inputCls} />
                        </div>
                        <div>
                          <Label>{t('candidates.sibling_spouse_occupation')}</Label>
                          <input {...register(`siblings.${i}.spouse_occupation`)} className={inputCls} />
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
              <AddBtn
                onClick={() => addSibling({
                  relation: 'brother', age: '', institution: '', marital_status: '',
                  spouse_lastname: '', support_location: '', spouse_study: '', spouse_occupation: '',
                })}
                label={t('candidates.form_add_sibling')}
              />
            </div>
          </SubSection>

          {/* Family notes */}
          <div className="mt-4">
            <Label>{t('candidates.family_notes')}</Label>
            <textarea {...register('family_notes')} rows={2} className={textareaCls} />
          </div>
        </FormSection>

        {/* ── Contact Numbers ──────────────────────────────────────────────── */}
        <FormSection title={t('candidates.section_contacts')}>
          <div className="space-y-3">
            {contacts.map((field, i) => (
              <div key={field.id} className="grid grid-cols-3 gap-3 items-end">
                <div>
                  <Label>{t('candidates.contact_number')}</Label>
                  <input type="tel" {...register(`contact_phones.${i}.number`)} className={inputCls} />
                </div>
                <div>
                  <Label>{t('candidates.contact_name')}</Label>
                  <input {...register(`contact_phones.${i}.name`)} className={inputCls} />
                </div>
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <Label>{t('candidates.contact_relation')}</Label>
                    <input {...register(`contact_phones.${i}.relation`)} className={inputCls} />
                  </div>
                  <RemoveBtn onClick={() => removeContact(i)} />
                </div>
              </div>
            ))}
            <AddBtn
              onClick={() => addContact({ number: '', name: '', relation: '' })}
              label={t('candidates.add_contact')}
            />
          </div>
        </FormSection>

        {/* ── Notes ────────────────────────────────────────────────────────── */}
        <FormSection title={t('candidates.section_notes')}>
          <textarea
            {...register('notes')}
            rows={3}
            placeholder={t('candidates.form_notes_placeholder')}
            className={textareaCls}
          />
        </FormSection>

        {/* Submit row */}
        <div className="flex items-center justify-between pt-2">
          {submitError ? (
            <p className="text-sm text-red-600">{submitError}</p>
          ) : <div />}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => navigate(isEdit && id ? `/candidates/${id}` : '/candidates')}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300
                         rounded-lg hover:bg-gray-50 transition-colors"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg
                         hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isSubmitting
                ? t('candidates.form_submitting')
                : isEdit
                  ? t('candidates.form_submit_edit')
                  : t('candidates.form_submit_create')}
            </button>
          </div>
        </div>

      </form>
    </div>
  )
}
