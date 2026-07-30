import { useState, useRef, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LayoutDashboard, TrendingUp, BarChart2, BookOpen,
  Building2, Tag, Upload, Menu, ChevronLeft,
  Flag, LogOut, Bell,
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
  const [collapsed, setCollapsed] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const notifRef = useRef(null)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: info, refetch } = useQuery({
    queryKey: ['data-info'],
    queryFn: () => api.get('/data/info').then((r) => r.data),
  })

  const { data: notifData } = useQuery({
    queryKey: ['rq-notifications'],
    queryFn: () => api.get('/v1/reported-questions/notifications').then((r) => r.data),
    refetchInterval: 15000,
  })

  const markRead = useMutation({
    mutationFn: (nid) => api.put(`/v1/reported-questions/notifications/${nid}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rq-notifications'] }),
  })

  const markAllRead = useMutation({
    mutationFn: () => api.put('/v1/reported-questions/notifications/read-all'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rq-notifications'] }),
  })

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    navigate('/login', { replace: true })
  }

  const username = localStorage.getItem('auth_user') || 'Admin'
  const unreadCount = notifData?.unread ?? 0

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${collapsed ? 'w-14' : 'w-56'} shrink-0 bg-white border-r border-gray-100 flex flex-col transition-all duration-200`}
      >
        {/* Logo row */}
        <div className="h-14 flex items-center justify-between px-3 border-b border-gray-100">
          {!collapsed && (
            <img src="/logoimocha.png" alt="iMocha" className="h-11 ml-1" />
          )}
          {collapsed && (
            <img src="/favicon.png" alt="iMocha" className="h-11 w-11 mx-auto" />
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

        {/* Upload / Sync + Clear + Logout */}
        <div className="p-2 border-t border-gray-100 space-y-1.5">
          {info?.sync_mode ? (
            /* ── MSSQL sync mode ── */
            <>
              {!collapsed && info?.loaded && (
                <p className="text-xs text-gray-400 px-1 truncate">
                  {info.rows?.toLocaleString()} rows · midnight sync
                </p>
              )}
              {!collapsed && info?.uploaded_at && (
                <p className="text-xs text-gray-400 px-1 truncate" title="Last synced">
                  Last: {new Date(info.uploaded_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
                </p>
              )}
            </>
          ) : (
            /* ── Manual upload mode ── */
            <>
              <button
                onClick={() => setUploadOpen(true)}
                title={collapsed ? (info?.loaded ? 'Add More Data' : 'Upload Data') : undefined}
                className={`w-full flex items-center gap-2 px-2.5 py-2.5 rounded-lg bg-orange-500 hover:bg-orange-600
                  text-white text-sm font-medium transition-colors ${collapsed ? 'justify-center' : ''}`}
              >
                <Upload size={16} className="shrink-0" />
                {!collapsed && (info?.loaded ? 'Add More Data' : 'Upload Data')}
              </button>
              {!collapsed && info?.loaded && (
                <p className="text-xs text-gray-400 px-1 truncate" title={info.filename}>
                  {info.filename} · {info.rows?.toLocaleString()} rows
                </p>
              )}
            </>
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
        <header className="min-h-[56px] bg-white border-b border-gray-100 flex items-center px-5 py-2 shrink-0 z-20 relative gap-3">
          <div className="flex-1">
            <GlobalFilters />
          </div>

          {/* Notification bell */}
          <div className="relative shrink-0" ref={notifRef}>
            <button
              onClick={() => setNotifOpen((o) => !o)}
              className="relative p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              title="Notifications"
            >
              <Bell size={18} />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-0.5 bg-orange-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>

            {notifOpen && (
              <div className="absolute right-0 top-full mt-2 w-80 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                  <span className="text-sm font-semibold text-gray-800">Notifications</span>
                  {unreadCount > 0 && (
                    <button
                      onClick={() => markAllRead.mutate()}
                      className="text-xs text-orange-600 hover:text-orange-700 font-medium"
                    >
                      Mark all read
                    </button>
                  )}
                </div>
                <div className="max-h-80 overflow-y-auto divide-y divide-gray-50">
                  {(notifData?.items || []).length === 0 && (
                    <p className="text-sm text-gray-400 text-center py-6">No notifications</p>
                  )}
                  {(notifData?.items || []).map((n) => (
                    <div
                      key={n.id}
                      onClick={() => { if (!n.is_read) markRead.mutate(n.id) }}
                      className={`px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${!n.is_read ? 'bg-orange-50/40' : ''}`}
                    >
                      <div className="flex items-start gap-2">
                        {!n.is_read && (
                          <span className="mt-1.5 w-2 h-2 rounded-full bg-orange-500 shrink-0" />
                        )}
                        <div className={`flex-1 min-w-0 ${n.is_read ? 'pl-4' : ''}`}>
                          <p className="text-xs text-gray-700 leading-relaxed line-clamp-2">{n.preview}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-gray-400">from {n.from_user}</span>
                            {n.question_issue_id && (
                              <span className="text-[10px] bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded font-medium">Q#{n.question_issue_id}</span>
                            )}
                            <span className="text-[10px] text-gray-400 ml-auto">
                              {new Date(n.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">
          {!info?.loaded ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-20 h-20 bg-orange-100 rounded-full flex items-center justify-center mb-4">
                <Upload size={32} className="text-orange-500" />
              </div>
              <h2 className="text-xl font-semibold text-gray-700 mb-2">No data loaded</h2>
              {info?.sync_mode ? (
                <>
                  <p className="text-gray-400 mb-6 max-w-sm text-sm">
                    Data syncs automatically from MSSQL every midnight.<br />
                    It will be available shortly after the first deployment.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-gray-400 mb-6 max-w-sm text-sm">
                    Upload a CSV or Excel file with your iMocha usage data to start exploring the analytics.
                  </p>
                  <button
                    onClick={() => setUploadOpen(true)}
                    className="px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors"
                  >
                    Upload Data File
                  </button>
                </>
              )}
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
