import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import {
  PieChart, Pie, Cell, Legend, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import {
  Download, CheckCircle, Clock, AlertCircle, BarChart2, X, ExternalLink,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, UserCheck,
  MessageSquare, Send,
} from 'lucide-react'
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
  const [detail, setDetail] = useState(null)
  const [remarkDraft, setRemarkDraft] = useState('')
  const [noteContent, setNoteContent] = useState('')
  const [mentionAnchor, setMentionAnchor] = useState(null) // { start, query }
  const noteInputRef = useRef(null)
  const currentUser = localStorage.getItem('auth_user') || ''

  const openDetail = (row) => {
    setDetail(row)
    setRemarkDraft(row.remark || '')
  }

  const set = (key) => (e) => setDraft((p) => ({ ...p, [key]: e.target.value }))

  // ── Mutations ─────────────────────────────────────────────────────────────

  const markResolved = useMutation({
    mutationFn: (qid) => api.post(`/v1/reported-questions/${qid}/mark`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rq-list'] }),
  })

  const unmarkResolved = useMutation({
    mutationFn: (qid) => api.delete(`/v1/reported-questions/${qid}/mark`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rq-list'] }),
  })

  const setIssueFound = useMutation({
    mutationFn: ({ qid, value }) => api.put(`/v1/reported-questions/${qid}/issue-found`, { value }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rq-list'] }),
  })

  const saveRemark = useMutation({
    mutationFn: ({ qid, remark }) => api.put(`/v1/reported-questions/${qid}/remark`, { remark }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['rq-list'] })
      setDetail((prev) => prev ? { ...prev, remark: vars.remark, remarked_by: currentUser } : prev)
    },
  })

  const postNote = useMutation({
    mutationFn: (body) => api.post('/v1/reported-questions/notes', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rq-notes'] })
      setNoteContent('')
      setMentionAnchor(null)
    },
  })

  // ── Queries ───────────────────────────────────────────────────────────────

  const { data: options } = useQuery({
    queryKey: ['rq-options'],
    queryFn: () => api.get('/v1/reported-questions/filter-options').then((r) => r.data),
  })

  const { data: stats } = useQuery({
    queryKey: ['rq-analytics', applied],
    queryFn: () => api.get('/v1/reported-questions/analytics', { params: toParams(applied) }).then((r) => r.data),
  })

  const { data: list, isLoading } = useQuery({
    queryKey: ['rq-list', applied, page, limit],
    queryFn: () => api.get('/v1/reported-questions', { params: { ...toParams(applied), page, limit } }).then((r) => r.data),
  })

  const { data: notesData } = useQuery({
    queryKey: ['rq-notes'],
    queryFn: () => api.get('/v1/reported-questions/notes').then((r) => r.data),
    refetchInterval: 30000,
  })

  const { data: usersData } = useQuery({
    queryKey: ['rq-users'],
    queryFn: () => api.get('/auth/users').then((r) => r.data),
  })

  // ── @mention handler ──────────────────────────────────────────────────────

  const handleNoteInput = (e) => {
    const val = e.target.value
    setNoteContent(val)
    const cursorPos = e.target.selectionStart
    const before = val.slice(0, cursorPos)
    const match = before.match(/@(\w*)$/)
    if (match) {
      setMentionAnchor({ start: match.index, query: match[1] })
    } else {
      setMentionAnchor(null)
    }
  }

  const insertMention = (username) => {
    if (mentionAnchor === null) return
    const before = noteContent.slice(0, mentionAnchor.start)
    const after = noteContent.slice(mentionAnchor.start + 1 + mentionAnchor.query.length)
    setNoteContent(`${before}@${username} ${after}`)
    setMentionAnchor(null)
    noteInputRef.current?.focus()
  }

  const submitNote = () => {
    const content = noteContent.trim()
    if (!content) return
    postNote.mutate({ content, question_issue_id: null })
  }

  const filteredMentions = mentionAnchor !== null
    ? (usersData?.users || []).filter((u) =>
        u.toLowerCase().startsWith(mentionAnchor.query.toLowerCase()) && u !== currentUser
      )
    : []

  // ── Misc handlers ─────────────────────────────────────────────────────────

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
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Download size={15} />
            Export My Resolved
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KPICard title="Total Issues"      value={stats ? stats.total.toLocaleString() : '—'}        color="orange" icon={AlertCircle} />
        <KPICard title="Resolved"          value={stats ? stats.resolved.toLocaleString() : '—'}     color="green"  icon={CheckCircle} />
        <KPICard title="Pending"           value={stats ? stats.pending.toLocaleString() : '—'}      color="purple" icon={Clock} />
        <KPICard title="Resolution Rate"   value={stats ? `${stats.resolution_rate}%` : '—'}         color="blue"   icon={BarChart2} />
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
                <th className="px-4 py-3 text-left font-medium">Q. Type</th>
                <th className="px-4 py-3 text-left font-medium">Problem Type</th>
                <th className="px-4 py-3 text-left font-medium">Comment</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Issue Found</th>
                <th className="px-4 py-3 text-left font-medium">Resolved By</th>
                <th className="px-4 py-3 text-left font-medium">Action</th>
                <th className="px-4 py-3 text-left font-medium">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading && (
                <tr><td colSpan={13} className="text-center py-10 text-gray-400">Loading…</td></tr>
              )}
              {!isLoading && list?.items?.length === 0 && (
                <tr><td colSpan={13} className="text-center py-10 text-gray-400">No issues found</td></tr>
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
                  <td className="px-4 py-3 text-gray-500 text-xs">{row.que_type || '—'}</td>
                  <td className="px-4 py-3">
                    <span className="inline-block bg-orange-50 text-orange-700 text-xs px-2 py-0.5 rounded-full max-w-[150px] truncate" title={row.problem_type}>
                      {row.problem_type || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-[160px] truncate text-xs" title={row.comment}>
                    {row.comment || '—'}
                  </td>
                  <td className="px-4 py-3">
                    {row.issue_status === 'Resolved'
                      ? <span className="inline-flex items-center gap-1 bg-green-50 text-green-700 text-xs px-2 py-0.5 rounded-full">✓ Resolved</span>
                      : row.issue_status === 'Inprogress'
                      ? <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full">↻ Inprogress</span>
                      : <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 text-xs px-2 py-0.5 rounded-full">○ Pending</span>
                    }
                  </td>
                  {/* Issue Found — shared Yes/No dropdown */}
                  <td className="px-4 py-3">
                    <select
                      value={row.issue_found || ''}
                      onChange={(e) => setIssueFound.mutate({ qid: row.question_issue_id, value: e.target.value || null })}
                      className={`text-xs border rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-orange-400 cursor-pointer
                        ${row.issue_found === 'Yes' ? 'border-red-300 bg-red-50 text-red-700' :
                          row.issue_found === 'No'  ? 'border-green-300 bg-green-50 text-green-700' :
                          'border-gray-200 bg-white text-gray-400'}`}
                    >
                      <option value="">—</option>
                      <option value="Yes">Yes</option>
                      <option value="No">No</option>
                    </select>
                    {row.issue_found_by && (
                      <p className="text-[10px] text-gray-400 mt-0.5">{row.issue_found_by}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {row.marked_by
                      ? <span className="inline-flex items-center gap-1 text-green-700 font-medium">
                          <UserCheck size={12} /> {row.marked_by}
                        </span>
                      : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {row.marked_by === currentUser ? (
                      <button
                        onClick={() => unmarkResolved.mutate(row.id)}
                        disabled={unmarkResolved.isPending}
                        className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-500 hover:bg-red-50 hover:border-red-300 hover:text-red-600 transition-colors disabled:opacity-50"
                      >
                        Unmark
                      </button>
                    ) : row.marked_by ? (
                      <span className="text-xs text-gray-400 italic">Marked</span>
                    ) : (
                      <button
                        onClick={() => markResolved.mutate(row.id)}
                        disabled={markResolved.isPending}
                        className="text-xs px-2 py-1 rounded border border-green-300 text-green-700 hover:bg-green-50 transition-colors disabled:opacity-50"
                      >
                        Mark as Resolved
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => openDetail(row)}
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

            {/* Page numbers */}
            {(() => {
              const total = list?.pages ?? 1
              const pages = []
              for (let n = 1; n <= total; n++) {
                if (n === 1 || n === total || Math.abs(n - page) <= 1) pages.push(n)
                else if (pages[pages.length - 1] !== '…') pages.push('…')
              }
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

      {/* Chat / Team Notes panel */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <MessageSquare size={16} className="text-orange-500" />
          Team Notes
          {(notesData?.total ?? 0) > 0 && (
            <span className="text-xs text-gray-400 font-normal">{notesData.total} note{notesData.total !== 1 ? 's' : ''}</span>
          )}
        </h3>

        {/* Note input */}
        <div className="relative mb-5">
          <textarea
            ref={noteInputRef}
            value={noteContent}
            onChange={handleNoteInput}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitNote() }
              if (e.key === 'Escape') setMentionAnchor(null)
            }}
            placeholder="Write a note… Use @username to tag a teammate (Enter to send, Shift+Enter for new line)"
            rows={2}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400 resize-none pr-10"
          />

          {/* @mention autocomplete dropdown */}
          {filteredMentions.length > 0 && (
            <div className="absolute bottom-full left-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 min-w-[160px]">
              {filteredMentions.map((u) => (
                <button
                  key={u}
                  className="block w-full text-left px-3 py-2 text-sm hover:bg-orange-50 hover:text-orange-700 first:rounded-t-lg last:rounded-b-lg transition-colors"
                  onMouseDown={(e) => { e.preventDefault(); insertMention(u) }}
                >
                  @{u}
                </button>
              ))}
            </div>
          )}

          <button
            onClick={submitNote}
            disabled={!noteContent.trim() || postNote.isPending}
            title="Send note"
            className="absolute right-2.5 bottom-2.5 p-1 text-orange-500 hover:text-orange-600 disabled:opacity-40 transition-colors"
          >
            <Send size={16} />
          </button>
        </div>

        {/* Notes list */}
        <div className="space-y-4 max-h-80 overflow-y-auto pr-1">
          {(notesData?.items || []).length === 0 && (
            <p className="text-sm text-gray-400 text-center py-6">No notes yet — be the first to write one!</p>
          )}
          {(notesData?.items || []).map((note) => (
            <div key={note.id} className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center text-orange-700 text-sm font-bold shrink-0">
                {(note.author[0] || '?').toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="text-xs font-semibold text-gray-800">{note.author}</span>
                  <span className="text-xs text-gray-400">
                    {new Date(note.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </span>
                  {note.question_issue_id && (
                    <span className="text-[10px] bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded font-medium">
                      Q#{note.question_issue_id}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-700 mt-0.5 break-words">
                  {note.content.split(/(@\w+)/g).map((part, i) =>
                    part.startsWith('@')
                      ? <span key={i} className="text-orange-600 font-medium">{part}</span>
                      : part
                  )}
                </p>
              </div>
            </div>
          ))}
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
              <div className="flex items-center gap-3 flex-wrap">
                {detail.resolved
                  ? <span className="inline-flex items-center gap-1 bg-green-50 text-green-700 text-xs px-3 py-1 rounded-full font-medium">✓ Resolved</span>
                  : <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 text-xs px-3 py-1 rounded-full font-medium">○ Pending</span>
                }
                {detail.issue_found && (
                  <span className={`inline-flex items-center gap-1 text-xs px-3 py-1 rounded-full font-medium ${
                    detail.issue_found === 'Yes' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'
                  }`}>
                    Issue Found: {detail.issue_found}
                    {detail.issue_found_by && <span className="opacity-60 ml-1">· {detail.issue_found_by}</span>}
                  </span>
                )}
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

              {/* Remark section */}
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Shared Remark</p>
                {detail.remark && (
                  <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 text-sm text-gray-700 mb-3">
                    <p className="whitespace-pre-wrap">{detail.remark}</p>
                    {detail.remarked_by && (
                      <p className="text-xs text-blue-500 mt-1">— {detail.remarked_by}</p>
                    )}
                  </div>
                )}
                <textarea
                  value={remarkDraft}
                  onChange={(e) => setRemarkDraft(e.target.value)}
                  placeholder="Add or update a shared remark visible to all users…"
                  rows={3}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400 resize-none"
                />
                <div className="flex items-center gap-2 mt-2">
                  <button
                    onClick={() => saveRemark.mutate({ qid: detail.question_issue_id, remark: remarkDraft })}
                    disabled={saveRemark.isPending || remarkDraft === (detail.remark || '')}
                    className="px-4 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                  >
                    {saveRemark.isPending ? 'Saving…' : 'Save Remark'}
                  </button>
                  {saveRemark.isSuccess && (
                    <span className="text-xs text-green-600">Saved!</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
