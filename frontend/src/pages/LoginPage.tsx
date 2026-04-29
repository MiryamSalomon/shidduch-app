import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import axios from 'axios'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import LanguageSwitcher from '../components/LanguageSwitcher'

const schema = z.object({
  username: z.string().min(1, 'required'),
  password: z.string().min(1, 'required'),
})

type FormData = z.infer<typeof schema>

function errorMessage(err: unknown, t: (key: string) => string): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status
    if (status === 401) return t('auth.error_401')
    if (status === 423) return t('auth.error_423')
    if (status === 429) return t('auth.error_429')
  }
  return t('auth.error_generic')
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  const [serverError, setServerError] = useState<string | null>(null)

  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/candidates'

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: FormData) => {
    setServerError(null)
    try {
      await login(data.username, data.password)
      navigate(from, { replace: true })
    } catch (err) {
      setServerError(errorMessage(err, t))
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 relative">
      {/* Language switcher — top right corner */}
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>

      <div className="w-full max-w-sm">

        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">{t('auth.title')}</h1>
          <p className="mt-2 text-sm text-gray-500">{t('auth.subtitle')}</p>
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
                <p className="mt-1 text-xs text-red-600">{t('auth.username_required')}</p>
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
                autoComplete="current-password"
                {...register('password')}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           placeholder-gray-400
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                           disabled:bg-gray-50"
                placeholder={t('auth.password_placeholder')}
                disabled={isSubmitting}
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{t('auth.password_required')}</p>
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
              {isSubmitting ? t('auth.submitting') : t('auth.submit')}
            </button>

          </form>
        </div>

        {/* Register link */}
        <p className="mt-6 text-center text-sm text-gray-600">
          {t('auth.no_account')}{' '}
          <Link
            to="/register"
            className="font-medium text-blue-600 hover:text-blue-700 hover:underline"
          >
            {t('auth.go_register')}
          </Link>
        </p>

      </div>
    </div>
  )
}
