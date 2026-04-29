import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import {
  listMatchmakers,
  createMatchmaker,
  updateMatchmaker,
  deactivateMatchmaker,
} from '../../api/matchmakers'
import ConfirmDialog from '../../components/ConfirmDialog'
import Pagination from '../../components/Pagination'
import { useAuth } from '../../auth/AuthContext'
import type { Matchmaker, MatchmakerRole } from '../../types'

const PAGE_SIZE = 20

// ─── Role badge ───────────────────────────────────────────────────────────────

function RoleBadge({ role }: { role: MatchmakerRole }) {
  return role === 'admin'
    ? <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">Admin</span>
    : <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">Matchmaker</span>
}

// ─── Modal ────────────────────────────────────────────────────────────────────

type CreateForm = {
  username: string
  password: string
  display_name: string
  email: string
  role: MatchmakerRole
}

type EditForm = {
  display_name: string
  email: string
  role: MatchmakerRole
  password: string
}

const inputCls =
  'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'
const selectCls =
  'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white'

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs font-medium text-gray-500 mb-1">
      {children}{required && <span className="text-red-500 ml-0.5">*</span>}
    </label>
  )
}

function ModalBackdrop({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-40 bg-black/30"
      onClick={onClose}
    />
  )
}

function CreateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (m: Matchmaker) => void
}) {
  const { t } = useTranslation()
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<CreateForm>({
    defaultValues: { username: '', password: '', display_name: '', email: '', role: 'matchmaker' },
  })
  const [serverError, setServerError] = useState<string | null>(null)

  const onSubmit = async (values: CreateForm) => {
    setServerError(null)
    try {
      const created = await createMatchmaker({
        username: values.username,
        password: values.password,
        display_name: values.display_name,
        email: values.email || null,
        role: values.role,
      })
      onCreated(created)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setServerError(detail ?? t('admin.error_create'))
    }
  }

  return (
    <>
      <ModalBackdrop onClose={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
        <div className="relative bg-white rounded-xl shadow-lg p-6 w-full max-w-md">
          <h3 className="text-base font-semibold text-gray-900 mb-5">{t('admin.create_title')}</h3>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label required>{t('admin.field_username')}</Label>
                <input {...register('username', { required: t('common.required') })} className={inputCls} />
                {errors.username && <p className="mt-1 text-xs text-red-600">{errors.username.message}</p>}
              </div>
              <div>
                <Label required>{t('admin.field_password')}</Label>
                <input
                  type="password"
                  {...register('password', {
                    required: t('common.required'),
                    minLength: { value: 8, message: t('admin.min_password') },
                  })}
                  className={inputCls}
                />
                {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
              </div>
            </div>
            <div>
              <Label required>{t('admin.field_display_name')}</Label>
              <input {...register('display_name', { required: t('common.required') })} className={inputCls} />
              {errors.display_name && <p className="mt-1 text-xs text-red-600">{errors.display_name.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{t('admin.field_email')}</Label>
                <input type="email" {...register('email')} className={inputCls} />
              </div>
              <div>
                <Label>{t('admin.field_role')}</Label>
                <select {...register('role')} className={selectCls}>
                  <option value="matchmaker">{t('admin.role_matchmaker')}</option>
                  <option value="admin">{t('admin.role_admin')}</option>
                </select>
              </div>
            </div>

            {serverError && <p className="text-sm text-red-600">{serverError}</p>}

            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
                {t('common.cancel')}
              </button>
              <button type="submit" disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {isSubmitting ? t('admin.creating') : t('common.create')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}

function EditModal({
  matchmaker,
  onClose,
  onUpdated,
}: {
  matchmaker: Matchmaker
  onClose: () => void
  onUpdated: (m: Matchmaker) => void
}) {
  const { t } = useTranslation()
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<EditForm>({
    defaultValues: {
      display_name: matchmaker.display_name,
      email: matchmaker.email ?? '',
      role: matchmaker.role,
      password: '',
    },
  })
  const [serverError, setServerError] = useState<string | null>(null)

  const onSubmit = async (values: EditForm) => {
    setServerError(null)
    const payload: Record<string, unknown> = {
      display_name: values.display_name,
      email: values.email || null,
      role: values.role,
    }
    if (values.password) payload.password = values.password

    try {
      const updated = await updateMatchmaker(matchmaker.id, payload)
      onUpdated(updated)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setServerError(detail ?? t('admin.error_update'))
    }
  }

  return (
    <>
      <ModalBackdrop onClose={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
        <div className="relative bg-white rounded-xl shadow-lg p-6 w-full max-w-md">
          <h3 className="text-base font-semibold text-gray-900 mb-1">{t('admin.edit_title')}</h3>
          <p className="text-sm text-gray-400 mb-5 font-mono">{matchmaker.username}</p>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <Label required>{t('admin.field_display_name')}</Label>
              <input {...register('display_name', { required: t('common.required') })} className={inputCls} />
              {errors.display_name && <p className="mt-1 text-xs text-red-600">{errors.display_name.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{t('admin.field_email')}</Label>
                <input type="email" {...register('email')} className={inputCls} />
              </div>
              <div>
                <Label>{t('admin.field_role')}</Label>
                <select {...register('role')} className={selectCls}>
                  <option value="matchmaker">{t('admin.role_matchmaker')}</option>
                  <option value="admin">{t('admin.role_admin')}</option>
                </select>
              </div>
            </div>
            <div>
              <Label>{t('admin.field_new_password')}</Label>
              <input
                type="password"
                placeholder={t('admin.field_password_placeholder')}
                {...register('password', { minLength: { value: 8, message: t('admin.min_password') } })}
                className={inputCls}
              />
              {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
            </div>

            {serverError && <p className="text-sm text-red-600">{serverError}</p>}

            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
                {t('common.cancel')}
              </button>
              <button type="submit" disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {isSubmitting ? t('admin.saving') : t('common.save_changes')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MatchmakersPage() {
  const { user } = useAuth()
  const { t } = useTranslation()

  const [items, setItems] = useState<Matchmaker[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState<Matchmaker | null>(null)
  const [deactivateTarget, setDeactivateTarget] = useState<Matchmaker | null>(null)
  const [isActing, setIsActing] = useState(false)

  const load = (p = page) => {
    setIsLoading(true)
    setError(null)
    listMatchmakers(p, PAGE_SIZE)
      .then((res) => {
        setItems(res.items)
        setTotal(res.total)
        setTotalPages(res.total_pages)
      })
      .catch(() => setError(t('admin.error_load')))
      .finally(() => setIsLoading(false))
  }

  useEffect(() => { load(page) }, [page]) // eslint-disable-line

  const handleDeactivate = async () => {
    if (!deactivateTarget) return
    setIsActing(true)
    try {
      await deactivateMatchmaker(deactivateTarget.id)
      setItems((prev) =>
        prev.map((m) => m.id === deactivateTarget.id ? { ...m, is_active: false } : m),
      )
    } finally {
      setIsActing(false)
      setDeactivateTarget(null)
    }
  }

  const handleReactivate = async (m: Matchmaker) => {
    try {
      const updated = await updateMatchmaker(m.id, { is_active: true })
      setItems((prev) => prev.map((item) => item.id === updated.id ? updated : item))
    } catch {
      // Silently ignore — page refresh will show true state
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{t('admin.title')}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t('admin.total', { count: total })}</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg
                     hover:bg-blue-700 transition-colors"
        >
          {t('admin.new_btn')}
        </button>
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
          <div className="p-8 text-center text-sm text-gray-400">{t('admin.no_results')}</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('admin.col_username')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('admin.col_display_name')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('admin.col_email')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('admin.col_role')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('admin.col_status')}</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">{t('admin.col_last_login')}</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {items.map((m) => {
                    const isSelf = m.id === user?.id
                    return (
                      <tr key={m.id} className={`transition-colors ${m.is_active ? 'hover:bg-gray-50' : 'bg-gray-50 opacity-60'}`}>
                        <td className="px-4 py-3 font-mono text-xs text-gray-700">
                          {m.username}
                          {isSelf && <span className="ml-2 text-blue-500 text-xs font-sans">{t('admin.you')}</span>}
                        </td>
                        <td className="px-4 py-3 font-medium text-gray-900">{m.display_name}</td>
                        <td className="px-4 py-3 text-gray-500">{m.email ?? '—'}</td>
                        <td className="px-4 py-3"><RoleBadge role={m.role} /></td>
                        <td className="px-4 py-3">
                          {m.is_active
                            ? <span className="text-xs text-green-600 font-medium">{t('admin.status_active')}</span>
                            : <span className="text-xs text-gray-400">{t('admin.status_inactive')}</span>
                          }
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-400">
                          {m.last_login_at
                            ? new Date(m.last_login_at).toLocaleDateString()
                            : t('admin.last_login_never')
                          }
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2 justify-end">
                            <button
                              onClick={() => setEditTarget(m)}
                              className="text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
                            >
                              {t('common.edit')}
                            </button>
                            {!isSelf && (
                              m.is_active ? (
                                <button
                                  onClick={() => setDeactivateTarget(m)}
                                  className="text-xs text-red-500 hover:text-red-700 font-medium transition-colors"
                                >
                                  {t('admin.deactivate')}
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleReactivate(m)}
                                  className="text-xs text-green-600 hover:text-green-800 font-medium transition-colors"
                                >
                                  {t('admin.reactivate')}
                                </button>
                              )
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
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

      {/* Modals */}
      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreated={(m) => {
            setShowCreate(false)
            setItems((prev) => [m, ...prev])
            setTotal((tt) => tt + 1)
          }}
        />
      )}
      {editTarget && (
        <EditModal
          matchmaker={editTarget}
          onClose={() => setEditTarget(null)}
          onUpdated={(updated) => {
            setEditTarget(null)
            setItems((prev) => prev.map((m) => m.id === updated.id ? updated : m))
          }}
        />
      )}
      {deactivateTarget && (
        <ConfirmDialog
          title={t('admin.confirm_deactivate_title')}
          message={t('admin.confirm_deactivate_msg', {
            name: deactivateTarget.display_name,
            username: deactivateTarget.username,
          })}
          confirmLabel={t('admin.deactivate')}
          onConfirm={handleDeactivate}
          onCancel={() => setDeactivateTarget(null)}
          isLoading={isActing}
        />
      )}
    </div>
  )
}
