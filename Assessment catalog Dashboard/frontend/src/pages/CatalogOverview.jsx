import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  PieChart, Pie, Cell, Legend, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import {
  Download, LibraryBig, CheckCircle2, Users, TrendingUp, Award, FileText,
  ExternalLink, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ArrowUpDown,
} from 'lucide-react'
import KPICard from '../components/KPICard'
import useFilterStore from '../store/filterStore'
import api from '../api/client'

const STATUS_COLORS = { Published: '#10B981', Draft: '#F59E0B', Inactive: '#9CA3AF', Unknown: '#6C3EB9' }
const TYPE_COLORS = ['#FF6B35', '#6C3EB9', '#10B981', '#3B82F6', '#F59E0B', '#EC4899', '#14B8A6', '#8B5CF6']

const RADIAN = Math.PI / 180
const renderPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.06) return null
  const r = innerRadius + (outerRadius - innerRadius) * 0.55
  const x = cx + r * Math.cos(-midAngle * RADIAN)
  const y = cy + r * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

const COLUMNS = [
  { key: 'name', label: 'Assessment', sortable: true },
  { key: 'created_on', label: 'Created', sortable: true },
  { key: 'assessment_type', label: 'Type', sortable: false },
  { key: 'test_status', label: 'Status', sortable: false },
  { key: 'total_questions', label: 'Total Q', sortable: true },
  { key: 'selected_questions', label: 'Selected Q', sortable: false },
  { key: 'duration', label: 'Duration', sortable: true },
  { key: 'invited', label: 'Invited', sortable: true },
  { key: 'completed', label: 'Completed', sortable: true },
  { key: 'pending', label: 'Pending', sortable: false },
  { key: 'avg_score', label: 'Avg Score %', sortable: true },
  { key: 'label', label: 'Label', sortable: false },
  { key: 'link', label: 'Link', sortable: false },
]

const STATUS_BADGE = {
  Published: 'bg-green-50 text-green-700',
  Draft: 'bg-amber-50 text-amber-700',
  Inactive: 'bg-gray-100 text-gray-500',
  Unknown: 'bg-purple-50 text-purple-700',
}

export default function CatalogOverview() {
  const params = useFilterStore((s) => s.getParams())
  const [page, setPage] = useState(1)
  const [limit, setLimit] = useState(50)
  const [sortBy, setSortBy] = useState('created_on')
  const [sortDir, setSortDir] = useState('desc')

  const { data: kpis } = useQuery({
    queryKey: ['catalog-kpis', params],
    queryFn: () => api.get('/catalog/kpis', { params }).then((r) => r.data),
  })

  const { data: summary } = useQuery({
    queryKey: ['catalog-summary', params],
    queryFn: () => api.get('/catalog/summary', { params }).then((r) => r.data),
  })

  const { data: list, isLoading } = useQuery({
    queryKey: ['catalog-table', params, page, limit, sortBy, sortDir],
    queryFn: () => api.get('/catalog', {
      params: { ...params, page, limit, sort_by: sortBy, sort_dir: sortDir },
    }).then((r) => r.data),
  })

  const handleSort = (key) => {
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(key)
      setSortDir('desc')
    }
    setPage(1)
  }

  const handleExport = async () => {
    const res = await api.get('/catalog/export', { params, responseType: 'blob', timeout: 300_000 })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `assessment_catalog_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <LibraryBig className="text-orange-500" size={24} />
          <h1 className="text-xl font-bold text-gray-800">Assessment Catalog</h1>
        </div>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Download size={15} />
          Export to Excel
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <KPICard title="Assessments"     value={kpis ? kpis.total_assessments.toLocaleString() : '—'} color="orange" icon={LibraryBig} />
        <KPICard title="Published"       value={kpis ? kpis.published.toLocaleString() : '—'}          color="green"  icon={CheckCircle2} />
        <KPICard title="Total Invited"   value={kpis ? kpis.total_invited.toLocaleString() : '—'}      color="blue"   icon={Users} />
        <KPICard title="Total Completed" value={kpis ? kpis.total_completed.toLocaleString() : '—'}    color="teal"   icon={CheckCircle2} />
        <KPICard title="Completion Rate" value={kpis ? `${kpis.completion_rate}%` : '—'}               color="purple" icon={TrendingUp} />
        <KPICard title="Avg Score"       value={kpis ? `${kpis.avg_score}%` : '—'}                     color="indigo" icon={Award} />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Assessments by Status</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={summary?.status_split || []} dataKey="value" nameKey="name" cx="50%" cy="50%"
                outerRadius={90} labelLine={false} label={renderPieLabel}>
                {(summary?.status_split || []).map((s) => (
                  <Cell key={s.name} fill={STATUS_COLORS[s.name] || '#9CA3AF'} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => v.toLocaleString()} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Assessments by Type</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={summary?.type_split?.slice(0, 8) || []} layout="vertical" margin={{ left: 4, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={130} />
              <Tooltip />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} name="Assessments">
                {(summary?.type_split?.slice(0, 8) || []).map((_, i) => (
                  <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Top Assessments by Candidates Invited</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={summary?.top_invited || []} layout="vertical" margin={{ left: 4, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 9 }} width={160} />
              <Tooltip />
              <Bar dataKey="invited" fill="#FF6B35" radius={[0, 4, 4, 0]} name="Invited" />
              <Bar dataKey="completed" fill="#10B981" radius={[0, 4, 4, 0]} name="Completed" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Candidate Funnel</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={summary?.funnel || []} margin={{ left: 4, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip formatter={(v) => v.toLocaleString()} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]} name="Candidates">
                {(summary?.funnel || []).map((_, i) => (
                  <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100">
          <p className="text-sm text-gray-500">
            {list ? `${list.total.toLocaleString()} assessments · Page ${list.page} of ${list.pages}` : 'Loading…'}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
                {COLUMNS.map((c) => (
                  <th key={c.key} className="px-4 py-3 text-left font-medium whitespace-nowrap">
                    {c.sortable ? (
                      <button onClick={() => handleSort(c.key)} className="flex items-center gap-1 hover:text-orange-600">
                        {c.label}
                        <ArrowUpDown size={11} className={sortBy === c.key ? 'text-orange-500' : 'text-gray-300'} />
                      </button>
                    ) : c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading && (
                <tr><td colSpan={COLUMNS.length} className="text-center py-10 text-gray-400">Loading…</td></tr>
              )}
              {!isLoading && list?.items?.length === 0 && (
                <tr><td colSpan={COLUMNS.length} className="text-center py-10 text-gray-400">No assessments found</td></tr>
              )}
              {list?.items?.map((row) => (
                <tr key={row.test_id} className="hover:bg-gray-50/60 transition-colors">
                  <td className="px-4 py-3 text-gray-700 max-w-[200px] truncate text-xs font-medium" title={row.test_name}>
                    {row.test_name || '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">
                    {row.created_on
                      ? new Date(row.created_on).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-600 max-w-[140px] truncate text-xs" title={row.assessment_type}>
                    {row.assessment_type || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[row.test_status] || 'bg-gray-100 text-gray-500'}`}>
                      {row.test_status || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{row.total_questions}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{row.selected_questions}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{row.duration} min</td>
                  <td className="px-4 py-3 text-gray-700 text-xs font-medium">{row.invited}</td>
                  <td className="px-4 py-3 text-green-700 text-xs">{row.completed}</td>
                  <td className="px-4 py-3 text-amber-600 text-xs">{row.pending}</td>
                  <td className="px-4 py-3 text-gray-700 text-xs font-medium">{row.avg_score}%</td>
                  <td className="px-4 py-3 text-gray-500 max-w-[130px] truncate text-xs" title={row.assessment_label}>
                    {row.assessment_label || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <a href={row.assessment_link} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1 text-xs text-orange-600 hover:text-orange-700 font-medium hover:underline">
                      <ExternalLink size={12} /> Open
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-100 flex-wrap gap-4 bg-gray-50/50">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">
              {list
                ? <><span className="font-semibold text-gray-700">{((page - 1) * limit) + 1}–{Math.min(page * limit, list.total)}</span> of <span className="font-semibold text-gray-700">{list.total.toLocaleString()}</span></>
                : '—'}
            </span>
            <select
              value={limit}
              onChange={(e) => { setLimit(Number(e.target.value)); setPage(1) }}
              className="border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm text-gray-600 font-medium focus:outline-none focus:ring-2 focus:ring-orange-400 bg-white cursor-pointer"
            >
              {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} rows</option>)}
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <button onClick={() => setPage(1)} disabled={page === 1}
              className="p-2 rounded-lg border border-gray-300 bg-white text-gray-500 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600 disabled:opacity-35 disabled:cursor-not-allowed transition-colors">
              <ChevronsLeft size={15} />
            </button>
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-600 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600 disabled:opacity-35 disabled:cursor-not-allowed transition-colors">
              <ChevronLeft size={14} /> Prev
            </button>
            <span className="px-3 text-sm text-gray-600">Page {page} of {list?.pages ?? 1}</span>
            <button onClick={() => setPage((p) => Math.min(list?.pages ?? 1, p + 1))} disabled={page === list?.pages}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-600 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600 disabled:opacity-35 disabled:cursor-not-allowed transition-colors">
              Next <ChevronRight size={14} />
            </button>
            <button onClick={() => setPage(list?.pages ?? 1)} disabled={page === list?.pages}
              className="p-2 rounded-lg border border-gray-300 bg-white text-gray-500 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-600 disabled:opacity-35 disabled:cursor-not-allowed transition-colors">
              <ChevronsRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
