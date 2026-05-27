import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  LayoutDashboard, TrendingUp, BarChart2, BookOpen,
  Building2, Tag, Upload, Menu, ChevronLeft,
  Trash2, AlertTriangle, Flag, LogOut,
} from 'lucide-react'
import api from '../api/client'
import UploadModal from './UploadModal'
import GlobalFilters from './GlobalFilters'

const NAV = [
  { path: '/overview',            label: 'Overview',            icon: LayoutDashboard },
  { path: '/trends',              label: 'Monthly Trends',      icon: TrendingUp },
  { path: '/usage',               label: 'Usage Insights',      icon: BarChart2 },
  { path: '/qb',                  label: 'QB Analytics',        icon: BookOpen },
  { path: '/company',             label: 'Companies',           icon: Building2 },
  { path: '/category',            label: 'Categories',          icon: Tag },
  { path: '/reported-questions',  label: 'Reported Questions',  icon: Flag },
]

export default function Layout() {
  const [uploadOpen, setUploadOpen] = useState(false)
  const [clearConfirm, setClearConfirm] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: info, refetch } = useQuery({
    queryKey: ['data-info'],
    queryFn: () => api.get('/data/info').then((r) => r.data),
  })

  const handleClear = async () => {
    setClearing(true)
    try {
      await api.delete('/data')
      qc.invalidateQueries()
      refetch()
      navigate('/overview')
    } finally {
      setClearing(false)
      setClearConfirm(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    navigate('/login', { replace: true })
  }

  const username = localStorage.getItem('auth_user') || 'Admin'

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${collapsed ? 'w-14' : 'w-56'} shrink-0 bg-white border-r border-gray-100 flex flex-col transition-all duration-200`}
      >
        {/* Logo row */}
        <div className="h-14 flex items-center justify-between px-3 border-b border-gray-100">
          {!collapsed && (
            <img src="/logoimocha.png" alt="iMocha" className="h-9 ml-1" />
          )}
          {collapsed && (
            <img src="/favicon.png" alt="iMocha" className="h-9 w-9 mx-auto" />
          )}
          {!collapsed && (
            <button
              onClick={() => setCollapsed(true)}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <ChevronLeft size={18} />
            </button>
          )}
          {collapsed && (
            <button
              onClick={() => setCollapsed(false)}
              className="absolute left-2 mt-14 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors hidden"
            />
          )}
        </div>

        {collapsed && (
          <button
            onClick={() => setCollapsed(false)}
            className="flex justify-center py-2 text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <Menu size={18} />
          </button>
        )}

        {/* Nav links */}
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {NAV.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `flex items-center gap-3 px-2.5 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${isActive
                  ? 'bg-orange-50 text-orange-600'
                  : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
                }`
              }
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && label}
            </NavLink>
          ))}
        </nav>

        {/* Upload + Clear + Logout */}
        <div className="p-2 border-t border-gray-100 space-y-1.5">
          <button
            onClick={() => setUploadOpen(true)}
            title={collapsed ? (info?.loaded ? 'Add More Data' : 'Upload Data') : undefined}
            className={`w-full flex items-center gap-2 px-2.5 py-2.5 rounded-lg bg-orange-500 hover:bg-orange-600
              text-white text-sm font-medium transition-colors ${collapsed ? 'justify-center' : ''}`}
          >
            <Upload size={16} className="shrink-0" />
            {!collapsed && (info?.loaded ? 'Add More Data' : 'Upload Data')}
          </button>

          {info?.loaded && (
            <button
              onClick={() => setClearConfirm(true)}
              title={collapsed ? 'Clear All Data' : undefined}
              className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-red-500 hover:bg-red-50
                text-sm font-medium transition-colors ${collapsed ? 'justify-center' : ''}`}
            >
              <Trash2 size={15} className="shrink-0" />
              {!collapsed && 'Clear All Data'}
            </button>
          )}

          {!collapsed && info?.loaded && (
            <p className="text-xs text-gray-400 px-1 truncate" title={info.filename}>
              {info.filename} · {info.rows?.toLocaleString()} rows
            </p>
          )}

          <button
            onClick={handleLogout}
            title={collapsed ? 'Sign Out' : undefined}
            className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-gray-400 hover:bg-gray-50
              hover:text-gray-600 text-sm font-medium transition-colors ${collapsed ? 'justify-center' : ''}`}
          >
            <LogOut size={15} className="shrink-0" />
            {!collapsed && (
              <span className="flex-1 text-left truncate">Sign out · {username}</span>
            )}
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
                <Upload size={32} className="text-orange-500" />
              </div>
              <h2 className="text-xl font-semibold text-gray-700 mb-2">No data loaded</h2>
              <p className="text-gray-400 mb-6 max-w-sm text-sm">
                Upload a CSV or Excel file with your iMocha usage data to start exploring the analytics.
              </p>
              <button
                onClick={() => setUploadOpen(true)}
                className="px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors"
              >
                Upload Data File
              </button>
            </div>
          ) : (
            <Outlet />
          )}
        </main>
      </div>

      {uploadOpen && (
        <UploadModal
          onClose={() => setUploadOpen(false)}
          onSuccess={() => { refetch(); setUploadOpen(false) }}
        />
      )}

      {clearConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center shrink-0">
                <AlertTriangle size={20} className="text-red-500" />
              </div>
              <h2 className="font-semibold text-gray-800">Clear All Data?</h2>
            </div>
            <p className="text-sm text-gray-500 mb-5">
              This will permanently delete all uploaded data from the server. This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setClearConfirm(false)} disabled={clearing}
                className="flex-1 px-4 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors">
                Cancel
              </button>
              <button onClick={handleClear} disabled={clearing}
                className="flex-1 px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-medium transition-colors disabled:opacity-60">
                {clearing ? 'Clearing…' : 'Yes, Clear All'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
