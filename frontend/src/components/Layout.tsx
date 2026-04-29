import { NavLink, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import LanguageSwitcher from './LanguageSwitcher'

function SidebarLink({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          isActive
            ? 'bg-blue-50 text-blue-700'
            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const { t } = useTranslation()

  const NAV = [
    { to: '/candidates', label: t('nav.candidates') },
    { to: '/suggestions', label: t('nav.suggestions') },
    { to: '/match-run', label: t('nav.match_run') },
  ]

  const ADMIN_NAV = [
    { to: '/admin/matchmakers', label: t('nav.matchmakers') },
  ]

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        {/* Brand */}
        <div className="px-5 py-4 border-b border-gray-100">
          <p className="text-base font-bold text-gray-900">{t('nav.brand')}</p>
          <p className="text-xs text-gray-400 mt-0.5">{t('nav.matchmaking_system')}</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map((link) => (
            <SidebarLink key={link.to} {...link} />
          ))}

          {user?.role === 'admin' && (
            <>
              <div className="pt-4 pb-1 px-3">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  {t('nav.admin_section')}
                </p>
              </div>
              {ADMIN_NAV.map((link) => (
                <SidebarLink key={link.to} {...link} />
              ))}
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="px-4 py-3 border-t border-gray-100">
          <p className="text-sm font-medium text-gray-800 truncate">{user?.display_name}</p>
          <div className="flex items-center justify-between mt-0.5">
            <p className="text-xs text-gray-400 capitalize">{user?.role}</p>
            <div className="flex items-center gap-2">
              <LanguageSwitcher />
              <button
                onClick={logout}
                className="text-xs text-gray-400 hover:text-gray-700 transition-colors"
              >
                {t('nav.sign_out')}
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Page content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
