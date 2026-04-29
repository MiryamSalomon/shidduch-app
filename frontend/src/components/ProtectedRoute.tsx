import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-gray-400 text-sm">Loading…</div>
      </div>
    )
  }

  if (!user) {
    // Pass the attempted URL so we can redirect back after login.
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}
