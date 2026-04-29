import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import axios from 'axios'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import LanguageSwitcher from '../components/LanguageSwitcher'

const schema = z.object({
  username: z.string().min(3).max(50),
  display_name: z.string().min(1).max(100),
  email: z.string().email().optional().or(z.literal('')),
  password: z.string().min(8).max(128),
})

type FormData = z.infer<typeof schema>

function errorMessage(err: unknown, t: (key: string) => string): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status
    if (status === 409) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') return detail
      return t('auth.error_conflict')
    }
    if (status === 429) return t('auth.error_429')
    if (status === 422) return t('auth.error_validation')
  }
  return t('auth.error_generic')
}

export default function RegisterPage() {
  const { register: registerUser } = useAuth()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: FormData) => {
    setServerError(null)
    try {
      await registerUser({
        username: data.username,
        display_name: data.display_name,
        password: data.password,
        email: data.email && data.email.length > 0 ? data.email : null,
      })
      navigate('/candidates', { replace: true })
    } catch (err) {
      setServerError(errorMessage(err, t))
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-10 relative">
      {/* Language switcher — top right corner */}
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>

      <div className="w-full max-w-sm">

        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">{t('auth.register_title')}</h1>
          <p className="mt-2 text-sm text-gray-500">{t('auth.register_subtitle')}</p>
        </div>

        {/* Card */}
        <div className="bg-white shadow-sm border border-gray-200 rounded-xl p-8">
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">

            {/* Username */}
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
                {t('auth.username')}
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                autoFocus
                {...register('username')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           placeholder-gray-400
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                           disabled:bg-gray-50"
                placeholder={t('auth.username_placeholder')}
                disabled={isSubmitting}
              />
              {errors.username && (
                <p className="mt-1 text-xs text-red-600">{t('auth.username_min')}</p>
              )}
            </div>

            {/* Display name */}
            <div>
              <label htmlFor="display_name" className="block text-sm font-medium text-gray-700 mb-1">
                {t('auth.display_name')}
              </label>
              <input
                id="display_name"
                type="text"
                autoComplete="name"
                {...register('display_name')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           placeholder-gray-400
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                           disabled:bg-gray-50"
                placeholder={t('auth.display_name_placeholder')}
                disabled={isSubmitting}
              />
              {errors.display_name && (
                <p className="mt-1 text-xs text-red-600">{t('auth.display_name_required')}</p>
              )}
            </div>

            {/* Email (optional) */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                {t('auth.email_optional')}
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                {...register('email')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           placeholder-gray-400
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                           disabled:bg-gray-50"
                placeholder={t('auth.email_placeholder')}
                disabled={isSubmitting}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-600">{t('auth.email_invalid')}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                {t('auth.password')}
              </label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                {...register('password')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           placeholder-gray-400
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                           disabled:bg-gray-50"
                placeholder={t('auth.password_placeholder')}
                disabled={isSubmitting}
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{t('auth.password_min')}</p>
              )}
            </div>

            {/* Server error */}
            {serverError && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                <p className="text-sm text-red-700">{serverError}</p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium
                         rounded-lg py-2.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                         disabled:opacity-50 disabled:cursor-not-allowed
                         transition-colors duration-150"
            >
              {isSubmitting ? t('auth.registering') : t('auth.register_submit')}
            </button>

          </form>
        </div>

        {/* Login link */}
        <p className="mt-6 text-center text-sm text-gray-600">
          {t('auth.have_account')}{' '}
          <Link
            to="/login"
            className="font-medium text-blue-600 hover:text-blue-700 hover:underline"
          >
            {t('auth.go_login')}
          </Link>
        </p>

      </div>
    </div>
  )
}
