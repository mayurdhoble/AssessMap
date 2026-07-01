import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import {
  PieChart, Pie, Cell, Legend, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { Download, CheckCircle, Clock, AlertCircle, BarChart2, RefreshCw, X, ExternalLink, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import KPICard from '../components/KPICard'
import api from '../api/client'

const RADIAN = Math.PI / 180
const renderPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.05) return null
  const r = innerRadius + (outerRadius - innerRadius) * 0.55
  const x = cx + r * Math.cos(-midAngle * RADIAN)
  const y = cy + r * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

const EMPTY = {
  dateFrom: '', dateTo: '', problemType: '', skill: '',
  candidateEmail: '', recruiterEmail: '', questionId: '', status: 'all',
}

const toParams = (f) => {
  const p = {}
  if (f.dateFrom) p.date_from = f.dateFrom
  if (f.dateTo) p.date_to = f.dateTo
  if (f.problemType) p.problem_type = f.problemType
  if (f.skill) p.skill = f.skill
  if (f.candidateEmail) p.candidate_email = f.candidateEmail
  if (f.recruiterEmail) p.recruiter_email = f.recruiterEmail
  if (f.questionId) p.question_id = f.questionId
  if (f.status !== 'all') p.status = f.status
  return p
}

export default function ReportedQuestions() {
  const qc = useQueryClient()
  const [draft, setDraft] = useState(EMPTY)
  const [applied, setApplied] = useState(EMPTY)
  const [page, setPage] = useState(1)
  const [limit, setLimit] = useState(50)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [detail, setDetail] = useState(null)

  const set = (key) => (e) => setDraft((p) => ({ ...p, [key]: e.target.value }))

  const interval = autoRefresh ? 10_000 : false

  const { data: syncStatus } = useQuery({
    queryKey: ['rq-sync-status'],
    queryFn: () => api.get('/v1/reported-questions/sync-status').then((r) => r.data),
    refetchInterval: interval,
  })

  const syncNow = useMutation({
    mutationFn: () => api.post('/v1/reported-questions/sync'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rq-list'] })
      qc.invalidateQueries({ queryKey: ['rq-analytics'] })
      qc.invalidateQueries({ queryKey: ['rq-sync-status'] })
    },
  })

  const { data: options } = useQuery({
    queryKey: ['rq-options'],
    queryFn: () => api.get('/v1/reported-questions/filter-options').then((r) => r.data),
    refetchInterval: interval,
  })

  const { data: stats } = useQuery({
    queryKey: ['rq-analytics', applied],
    queryFn: () => api.get('/v1/reported-questions/analytics', { params: toParams(applied) }).then((r) => r.data),
    refetchInterval: interval,
  })

  const { data: list, isLoading } = useQuery({
    queryKey: ['rq-list', applied, page, limit],
    queryFn: () => api.get('/v1/reported-questions', { params: { ...toParams(applied), page, limit } }).then((r) => r.data),
    refetchInterval: interval,
  })

  const toggle = useMutation({
    mutationFn: ({ id, resolved }) => api.patch(`/v1/reported-questions/${id}/status`, { resolved }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rq-list'] })
      qc.invalidateQueries({ queryKey: ['rq-analytics'] })
    },
  })

  const handleExport = async () => {
    const res = await api.get('/v1/reported-questions/export', {
      params: toParams(applied),
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `reported_questions_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  const applyFilters = () => { setApplied(draft); setPage(1) }
  const clearFilters = () => { setDraft(EMPTY); setApplied(EMPTY); setPage(1) }
  const changeLimit = (val) => { setLimit(Number(val)); setPage(1) }

  const pieData = stats
    ? [{ name: 'Resolved', value: stats.resolved }, { name: 'Pending', value: stats.pending }]
    : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-gray-800">Reported Questions</h1>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Sync Now — only in MSSQL mode */}
          {syncStatus?.sync_mode && (
            <div className="flex flex-col items-end gap-0.5">
              <button
                onClick={() => syncNow.mutate()}
                disabled={syncNow.isPending}
                className="flex items-center gap-2 px-3 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-60"
              >
                <RefreshCw size={14} className={syncNow.isPending ? 'animate-spin' : ''} />
                {syncNow.isPending ? 'Syncing…' : 'Sync Now'}
              </button>
              {syncStatus?.last_synced && (
                <span className="text-xs text-gray-400">
                  Last: {new Date(syncStatus.last_synced).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          )}

          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
              autoRefresh
                ? 'bg-green-50 border-green-300 text-green-700'
                : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'
            }`}
          >
            <RefreshCw size={14} className={autoRefresh ? 'animate-spin' : ''} />
            <span>Auto Refresh</span>
            <span className={`w-8 h-4 rounded-full transition-colors relative ${autoRefresh ? 'bg-green-500' : 'bg-gray-300'}`}>
              <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-all ${autoRefresh ? 'left-4' : 'left-0.5'}`} />
            </span>
            <span className="text-xs opacity-70">{autoRefresh ? '10s' : 'Off'}</span>
          </button>

          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Download size={15} />
            Export to Excel
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KPICard title="Total Issues"      value={stats ? stats.total.toLocaleString() : '—'}            color="orange" icon={AlertCircle} />
        <KPICard title="Resolved"          value={stats ? stats.resolved.toLocaleString() : '—'}         color="green"  icon={CheckCircle} />
        <KPICard title="Pending"           value={stats ? stats.pending.toLocaleString() : '—'}          color="purple" icon={Clock} />
        <KPICard title="Resolution Rate"   value={stats ? `${stats.resolution_rate}%` : '—'}             color="blue"   icon={BarChart2} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Status Overview</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                outerRadius={80} labelLine={false} label={renderPieLabel}>
                <Cell fill="#10B981" />
                <Cell fill="#F59E0B" />
              </Pie>
              <Tooltip formatter={(v) => v.toLocaleString()} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Issues by Problem Type</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={stats?.by_problem_type?.slice(0, 6) || []} layout="vertical" margin={{ left: 4, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 9 }} width={170} />
              <Tooltip />
              <Bar dataKey="total" fill="#FF6B35" radius={[0, 4, 4, 0]} name="Total" />
              <Bar dataKey="resolved" fill="#10B981" radius={[0, 4, 4, 0]} name="Resolved" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {[
            ['From Date', 'dateFrom', 'date'],
            ['To Date', 'dateTo', 'date'],
          ].map(([label, key, type]) => (
            <div key={key}>
              <label className="text-xs text-gray-500 mb-1 block">{label}</label>
              <input type={type} value={draft[key]} onChange={set(key)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400" />
            </div>
          ))}
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Problem Type</label>
            <select value={draft.problemType} onChange={set('problemType')}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400">
              <option value="">All Types</option>
              {options?.problem_types?.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Status</label>
            <select value={draft.status} onChange={set('status')}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400">
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Skill</label>
            <select value={draft.skill} onChange={set('skill')}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400">
              <option value="">All Skills</option>
              {options?.skills?.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Candidate Email</label>
            <input type="text" value={draft.candidateEmail} onChange={set('candidateEmail')}
              placeholder="Search…"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400" />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Recruiter Email</label>
            <input type="text" value={draft.recruiterEmail} onChange={set('recruiterEmail')}
              placeholder="Search…"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400" />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Question ID</label>
            <input type="number" value={draft.questionId} onChange={set('questionId')}
              placeholder="e.g. 123456"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400" />
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={applyFilters}
            className="px-5 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium rounded-lg transition-colors">
            Apply Filters
          </button>
          <button onClick={clearFilters}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors">
            Clear
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100">
          <p className="text-sm text-gray-500">
            {list ? `${list.total.toLocaleString()} issues · Page ${list.page} of ${list.pages}` : 'Loading…'}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
                <th className="px-4 py-3 text-left font-medium">Reported On</th>
                <th className="px-4 py-3 text-left font-medium">Candidate</th>
                <th className="px-4 py-3 text-left font-medium">Recruiter</th>
                <th className="px-4 py-3 text-left font-medium">Skill</th>
                <th className="px-4 py-3 text-left font-medium">Q. ID</th>
                <th className="px-4 py-3 text-left font-medium">Problem Type</th>
                <th className="px-4 py-3 text-left font-medium">Comment</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Action</th>
                <th className="px-4 py-3 text-left font-medium">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading && (
                <tr><td colSpan={10} className="text-center py-10 text-gray-400">Loading…</td></tr>
              )}
              {!isLoading && list?.items?.length === 0 && (
                <tr><td colSpan={10} className="text-center py-10 text-gray-400">No issues found</td></tr>
              )}
              {list?.items?.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50/60 transition-colors">
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap text-xs">
                    {row.reported_on
                      ? new Date(row.reported_on).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-700 max-w-[150px] truncate text-xs" title={row.candidate_email}>
                    {row.candidate_email || '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-700 max-w-[150px] truncate text-xs" title={row.recruiter_email}>
                    {row.recruiter_email || '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-700 max-w-[110px] truncate text-xs">{row.skill || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{row.question_id || '—'}</td>
                  <td className="px-4 py-3">
                    <span className="inline-block bg-orange-50 text-orange-700 text-xs px-2 py-0.5 rounded-full max-w-[150px] truncate" title={row.problem_type}>
                      {row.problem_type || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-[160px] truncate text-xs" title={row.comment}>
                    {row.comment || '—'}
                  </td>
                  <td className="px-4 py-3">
                    {row.resolved
                      ? <span className="inline-flex items-center gap-1 bg-green-50 text-green-700 text-xs px-2 py-0.5 rounded-full">✓ Resolved</span>
                      : <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 text-xs px-2 py-0.5 rounded-full">○ Pending</span>
                    }
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggle.mutate({ id: row.id, resolved: !row.resolved })}
                      disabled={toggle.isPending}
                      className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors disabled:opacity-50 ${
                        row.resolved
                          ? 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          : 'bg-green-100 text-green-700 hover:bg-green-200'
                      }`}
                    >
                      {row.resolved ? 'Reopen' : 'Resolve'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setDetail(row)}
                      className="flex items-center gap-1 text-xs text-orange-600 hover:text-orange-700 font-medium hover:underline"
                    >
                      <ExternalLink size={12} />
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination bar */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-100 flex-wrap gap-4 bg-gray-50/50">
          {/* Left: record count + rows-per-page */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">
              {list
                ? <><span className="font-semibold text-gray-700">{((page - 1) * limit) + 1}–{Math.min(page * limit, list.total)}</span> of <span className="font-semibold text-gray-700">{list.total.toLocaleString()}</span> records</>
                : '—'}
            </span>
            <select
              value={limit}
              onChange={(e) => changeLimit(e.target.value)}
              className="border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm text-gray-600 font-medium focus:outline-none focus:ring-2 focus:ring-orange-400 bg-white cursor-pointer"
            >
              {[10, 25, 50, 100].map((n) => (
                <option key={n} value={n}>{n} rows</option>
              ))}
            </select>
          </div>

          {/* Right: navigation */}
          <div className="flex items-center gap-1.5">
            {/* First */}
            <button onClick={() => setPage(1)} disabled={page === 1}
              title="First page"
              className="p-2 rounded-lg border border-gray-300 bg-white text-gray-500 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600 disabled:opacity-35 disabled:cursor-not-allowed transition-colors">
              <ChevronsLeft size={15} />
            </button>
            {/* Prev */}
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-600 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600 disabled:opacity-35 disabled:cursor-not-allowed transition-colors">
              <ChevronLeft size={14} /> Prev
            </button>

            {/* Numbered pages */}
            {list && (() => {
              const total = list.pages
              const delta = 2
              const range = []
              for (let i = Math.max(1, page - delta); i <= Math.min(total, page + delta); i++) range.push(i)
              const pages = []
              if (range[0] > 1) { pages.push(1); if (range[0] > 2) pages.push('…') }
              range.forEach((n) => pages.push(n))
              if (range[range.length - 1] < total) { if (range[range.length - 1] < total - 1) pages.push('…'); pages.push(total) }
              return pages.map((n, i) =>
                n === '…'
                  ? <span key={`el-${i}`} className="px-1.5 text-sm text-gray-400 select-none">…</span>
                  : <button key={n} onClick={() => setPage(n)}
                      className={`min-w-[36px] px-3 py-1.5 rounded-lg border text-sm font-semibold transition-colors ${
                        n === page
                          ? 'bg-orange-500 text-white border-orange-500 shadow-sm'
                          : 'bg-white border-gray-300 text-gray-600 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600'
                      }`}
                    >{n}</button>
              )
            })()}

            {/* Next */}
            <button onClick={() => setPage((p) => Math.min(list?.pages ?? 1, p + 1))} disabled={page === list?.pages}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-600 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600 disabled:opacity-35 disabled:cursor-not-allowed transition-colors">
              Next <ChevronRight size={14} />
            </button>
            {/* Last */}
            <button onClick={() => setPage(list?.pages ?? 1)} disabled={page === list?.pages}
              title="Last page"
              className="p-2 rounded-lg border border-gray-300 bg-white text-gray-500 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600 disabled:opacity-35 disabled:cursor-not-allowed transition-colors">
              <ChevronsRight size={15} />
            </button>
          </div>
        </div>
      </div>
      {/* Detail Modal */}
      {detail && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}>
            {/* Modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 sticky top-0 bg-white rounded-t-xl">
              <div>
                <h2 className="font-semibold text-gray-800">Issue #{detail.question_issue_id}</h2>
                <p className="text-xs text-gray-400 mt-0.5">
                  Reported on {detail.reported_on ? new Date(detail.reported_on).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                </p>
              </div>
              <button onClick={() => setDetail(null)} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                <X size={18} />
              </button>
            </div>

            {/* Modal body */}
            <div className="px-6 py-5 space-y-5">
              {/* Status badge */}
              <div>
                {detail.resolved
                  ? <span className="inline-flex items-center gap-1 bg-green-50 text-green-700 text-xs px-3 py-1 rounded-full font-medium">✓ Resolved</span>
                  : <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 text-xs px-3 py-1 rounded-full font-medium">○ Pending</span>
                }
              </div>

              {/* Info grid */}
              <div className="grid grid-cols-2 gap-4">
                {[
                  ['Candidate Email', detail.candidate_email],
                  ['Recruiter Email', detail.recruiter_email],
                  ['Skill', detail.skill],
                  ['Question ID', detail.question_id],
                  ['Problem Type', detail.problem_type],
                  ['Issue Status', detail.issue_status],
                ].map(([label, value]) => (
                  <div key={label} className="bg-gray-50 rounded-lg px-4 py-3">
                    <p className="text-xs text-gray-400 mb-0.5">{label}</p>
                    <p className="text-sm text-gray-800 font-medium break-all">{value || '—'}</p>
                  </div>
                ))}
              </div>

              {/* Comment */}
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Comment from Candidate</p>
                <div className="bg-orange-50 border border-orange-100 rounded-lg px-4 py-3 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {detail.comment || 'No comment provided'}
                </div>
              </div>

              {/* Resolved by */}
              {detail.resolved && detail.resolved_by && (
                <div className="bg-green-50 border border-green-100 rounded-lg px-4 py-3 text-sm text-gray-600">
                  Resolved by <span className="font-medium text-green-700">{detail.resolved_by}</span>
                  {detail.resolved_at && (
                    <> on {new Date(detail.resolved_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
