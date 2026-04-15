import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { FileText, Building2, Users, BookOpen, ClipboardList, LayoutGrid } from 'lucide-react'
import KPICard from '../components/KPICard'
import useFilterStore from '../store/filterStore'
import api from '../api/client'

const COLORS = ['#FF6B35', '#6C3EB9', '#3B82F6', '#10B981', '#F59E0B',
                '#EF4444', '#8B5CF6', '#06B6D4', '#84CC16', '#F97316']

const RADIAN = Math.PI / 180
const renderPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.05) return null
  const radius = innerRadius + (outerRadius - innerRadius) * 0.55
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm">
      <p className="font-medium text-gray-700 mb-1">{label}</p>
      <p className="text-orange-600 font-bold">{payload[0]?.value?.toLocaleString()}</p>
    </div>
  )
}

export default function Overview() {
  const params = useFilterStore((s) => s.getParams())

  const { data: kpis }         = useQuery({ queryKey: ['kpis', params],         queryFn: () => api.get('/overview/kpis',           { params }).then(r => r.data) })
  const { data: topCompanies } = useQuery({ queryKey: ['top-co', params],        queryFn: () => api.get('/overview/top-companies',  { params: { ...params, limit: 10 } }).then(r => r.data) })
  const { data: topQbs }       = useQuery({ queryKey: ['top-qb', params],        queryFn: () => api.get('/overview/top-qbs',        { params: { ...params, limit: 10 } }).then(r => r.data) })
  const { data: libSplit }     = useQuery({ queryKey: ['lib-split', params],     queryFn: () => api.get('/overview/library-split',  { params }).then(r => r.data) })
  const { data: navSplit }     = useQuery({ queryKey: ['nav-split', params],     queryFn: () => api.get('/overview/navigation-split', { params }).then(r => r.data) })

  const fmt = (n) => n?.toLocaleString() ?? '—'

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-800">Overview</h1>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
        <KPICard title="Total Reports"   value={fmt(kpis?.total_reports)}   color="orange" icon={FileText} />
        <KPICard title="Total Rows"      value={fmt(kpis?.total_assessments)} color="purple" icon={ClipboardList} />
        <KPICard title="Companies"       value={fmt(kpis?.unique_companies)} color="blue"   icon={Building2} />
        <KPICard title="Recruiters"      value={fmt(kpis?.unique_recruiters)} color="green"  icon={Users} />
        <KPICard title="Active QBs"      value={fmt(kpis?.active_qbs)}      color="teal"   icon={BookOpen} />
        <KPICard title="Active Tests"    value={fmt(kpis?.active_tests)}    color="indigo" icon={LayoutGrid} />
      </div>

      {/* Bar charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Top 10 Companies by Reports</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={topCompanies} layout="vertical" margin={{ left: 4, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => v.toLocaleString()} />
              <YAxis type="category" dataKey="company" tick={{ fontSize: 11 }} width={130} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="reports" fill="#FF6B35" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Top 10 Question Banks by Reports</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={topQbs} layout="vertical" margin={{ left: 4, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => v.toLocaleString()} />
              <YAxis type="category" dataKey="qb" tick={{ fontSize: 11 }} width={140} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="reports" fill="#6C3EB9" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Pie charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Library Split</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={libSplit}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={85}
                labelLine={false}
                label={renderPieLabel}
              >
                {libSplit?.map((_, i) => <Cell key={i} fill={COLORS[i]} />)}
              </Pie>
              <Tooltip formatter={(v) => v.toLocaleString()} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Navigation Type Split</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={navSplit}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={85}
                labelLine={false}
                label={renderPieLabel}
              >
                {navSplit?.map((_, i) => <Cell key={i} fill={COLORS[i + 2]} />)}
              </Pie>
              <Tooltip formatter={(v) => v.toLocaleString()} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
