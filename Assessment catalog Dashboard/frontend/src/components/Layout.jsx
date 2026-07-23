import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { LibraryBig, LogOut, RefreshCw } from 'lucide-react'
import api from '../api/client'
import GlobalFilters from './GlobalFilters'

const NAV = [
  { path: '/catalog', label: 'Assessment Catalog', icon: LibraryBig },
]

export default function Layout() {
  const [syncing, setSyncing] = useState(false)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: info, refetch } = useQuery({
    queryKey: ['catalog-info'],
    queryFn: () => api.get('/catalog/info').then((r) => r.data),
    refetchInterval: (q) => (q.state.data?.fetching ? 5_000 : false),
  })

  const handleSyncNow = async () => {
    setSyncing(true)
    try {
      await api.post('/catalog/sync', {}, { timeout: 300_000 })
      qc.invalidateQueries()
      refetch()
    } catch (e) {
      alert(e?.response?.data?.detail || 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    navigate('/login', { replace: true })
  }

  const username = localStorage.getItem('auth_user') || 'Admin'
  const busy = syncing || info?.fetching

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-white border-r border-gray-100 flex flex-col">
        <div className="h-14 flex items-center px-3 border-b border-gray-100">
          <img src="/logoimocha.png" alt="iMocha" className="h-11 ml-1" />
        </div>

        <div className="px-3 pt-4 pb-1">
          <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Assessment Catalog</p>
        </div>

        <nav className="flex-1 py-2 px-2 space-y-0.5 overflow-y-auto">
          {NAV.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-2.5 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${isActive ? 'bg-orange-50 text-orange-600' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'}`
              }
            >
              <Icon size={18} className="shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-2 border-t border-gray-100 space-y-1.5">
          <button
            onClick={handleSyncNow}
            disabled={busy}
            className="w-full flex items-center gap-2 px-2.5 py-2.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors disabled:opacity-60"
          >
            <RefreshCw size={16} className={`shrink-0 ${busy ? 'animate-spin' : ''}`} />
            {busy ? 'Syncing…' : 'Sync Now'}
          </button>
          {info?.loaded && (
            <p className="text-xs text-gray-400 px-1 truncate">
              {info.rows?.toLocaleString()} assessments · auto 30 min
            </p>
          )}
          {info?.last_synced && (
            <p className="text-xs text-gray-400 px-1 truncate" title="Last synced">
              Last: {new Date(info.last_synced).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
            </p>
          )}

          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-gray-400 hover:bg-gray-50 hover:text-gray-600 text-sm font-medium transition-colors"
          >
            <LogOut size={15} className="shrink-0" />
            <span className="flex-1 text-left truncate">Sign out · {username}</span>
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="min-h-[56px] bg-white border-b border-gray-100 flex items-center px-5 py-2 shrink-0 z-20 relative">
          <GlobalFilters />
        </header>

        <main className="flex-1 overflow-auto p-6">
          {!info?.loaded ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-20 h-20 bg-orange-100 rounded-full flex items-center justify-center mb-4">
                <RefreshCw size={32} className={`text-orange-500 ${info?.fetching ? 'animate-spin' : ''}`} />
              </div>
              <h2 className="text-xl font-semibold text-gray-700 mb-2">
                {info?.fetching ? 'Loading catalog…' : 'No data loaded'}
              </h2>
              <p className="text-gray-400 mb-6 max-w-sm text-sm">
                {info?.fetching
                  ? 'Fetching assessments from MSSQL — this can take a minute.'
                  : 'Catalog data is queried live from MSSQL. Click below to load it.'}
              </p>
              {info?.last_error && (
                <p className="text-red-500 text-xs mb-4 max-w-md break-words">{info.last_error}</p>
              )}
              <button
                onClick={handleSyncNow}
                disabled={busy}
                className="flex items-center gap-2 px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors disabled:opacity-60"
              >
                <RefreshCw size={16} className={busy ? 'animate-spin' : ''} />
                {busy ? 'Syncing…' : 'Sync Now'}
              </button>
            </div>
          ) : (
            <Outlet />
          )}
        </main>
      </div>
    </div>
  )
}
