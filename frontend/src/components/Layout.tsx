import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import type { ReactNode } from 'react'

export default function Layout({ children }: { children: ReactNode }) {
  const { isAuthenticated, user, logout } = useAuth()

  return (
    <div className="min-h-screen">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="flex items-center gap-2">
              <span className="text-2xl font-bold text-brand-600">BubbaRoo</span>
              <span className="text-sm text-gray-500">Events</span>
            </Link>
            <nav className="flex items-center gap-4">
              <Link to="/" className="text-gray-600 hover:text-gray-900">
                Discover
              </Link>
              {isAuthenticated && (
                <>
                  <Link to="/for-you" className="text-gray-600 hover:text-gray-900">
                    For You
                  </Link>
                  <Link to="/trip-planner" className="text-gray-600 hover:text-gray-900">
                    Trip Planner
                  </Link>
                  <Link to="/settings" className="text-gray-600 hover:text-gray-900">
                    Settings
                  </Link>
                </>
              )}
              {isAuthenticated ? (
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-500">{user?.display_name}</span>
                  <button
                    onClick={logout}
                    className="text-sm text-gray-500 hover:text-gray-700"
                  >
                    Sign out
                  </button>
                </div>
              ) : (
                <Link
                  to="/login"
                  className="bg-brand-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-brand-700"
                >
                  Sign in
                </Link>
              )}
            </nav>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
