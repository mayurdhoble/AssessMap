import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard, TrendingUp, BarChart2, BookOpen,
  Building2, Tag, Upload, Menu, ChevronLeft,
} from 'lucide-react'
import api from '../api/client'
import UploadModal from './UploadModal'
import GlobalFilters from './GlobalFilters'

const NAV = [
  { path: '/overview',  label: 'Overview',        icon: LayoutDashboard },
  { path: '/trends',    label: 'Monthly Trends',  icon: TrendingUp },
  { path: '/usage',     label: 'Usage Insights',  icon: BarChart2 },
  { path: '/qb',        label: 'QB Analytics',    icon: BookOpen },
  { path: '/company',   label: 'Companies',       icon: Building2 },
  { path: '/category',  label: 'Categories',      icon: Tag },
]

export default function Layout() {
  const [uploadOpen, setUploadOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()

  const { data: info, refetch } = useQuery({
    queryKey: ['data-info'],
    queryFn: () => api.get('/data/info').then((r) => r.data),
  })

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${collapsed ? 'w-14' : 'w-56'} shrink-0 bg-white border-r border-gray-100 flex flex-col transition-all duration-200`}
      >
        {/* Logo row */}
        <div className="h-14 flex items-center justify-between px-3 border-b border-gray-100">
          {!collapsed && (
            <span className="font-bold text-gray-800 text-sm truncate">iMocha Analytics</span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="ml-auto p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            {collapsed ? <Menu size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

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

        {/* Upload button + file info */}
        <div className="p-2 border-t border-gray-100">
          <button
            onClick={() => setUploadOpen(true)}
            title={collapsed ? 'Upload Data' : undefined}
            className={`w-full flex items-center gap-2 px-2.5 py-2.5 rounded-lg bg-orange-500 hover:bg-orange-600
              text-white text-sm font-medium transition-colors ${collapsed ? 'justify-center' : ''}`}
          >
            <Upload size={16} className="shrink-0" />
            {!collapsed && 'Upload Data'}
          </button>
          {!collapsed && info?.loaded && (
            <p className="text-xs text-gray-400 mt-2 px-1 truncate" title={info.filename}>
              {info.filename} · {info.rows?.toLocaleString()} rows
            </p>
          )}
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top filter bar — min-height so it expands when filters wrap */}
        <header className="min-h-[56px] bg-white border-b border-gray-100 flex items-center px-5 py-2 shrink-0 z-20 relative">
          <GlobalFilters />
        </header>

        {/* Page content */}
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
    </div>
  )
}
