import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Users, Building2, TrendingUp, ClipboardList } from 'lucide-react'
import KPICard from '../components/KPICard'
import useFilterStore from '../store/filterStore'
import api from '../api/client'

export default function UsageInsights() {
  const [topN, setTopN] = useState(20)
  const params = useFilterStore((s) => s.getParams())

  const { data: summary } = useQuery({
    queryKey: ['usage-summary', params],
    queryFn: () => api.get('/usage/summary', { params }).then((r) => r.data),
  })

  const { data: topCustomers } = useQuery({
    queryKey: ['top-customers', params, topN],
    queryFn: () => api.get('/usage/top-customers', { params: { ...params, limit: topN } }).then((r) => r.data),
  })

  const fmt = (n) => n?.toLocaleString() ?? '—'

  const dateLabel =
    params.date_from || params.date_to
      ? `${params.date_from || '…'} → ${params.date_to || '…'}`
      : 'All time'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-gray-800">Usage Insights</h1>
        <span className="text-sm text-gray-500 bg-white border border-gray-200 px-3 py-1.5 rounded-lg">
          {dateLabel}
        </span>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-4">
        <KPICard title="Total Reports"    value={fmt(summary?.total_reports)}    color="orange" icon={FileText} />
        <KPICard title="Total Rows"       value={fmt(summary?.total_rows)}       color="purple" icon={ClipboardList} />
        <KPICard title="Unique Users"     value={fmt(summary?.unique_users)}     color="blue"   icon={Users} />
        <KPICard title="Unique Customers" value={fmt(summary?.unique_customers)} color="green"  icon={Building2} />
        <KPICard title="Avg / Day"        value={fmt(summary?.avg_per_day)}      color="teal"   icon={TrendingUp} />
      </div>

      {/* Top customers table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="p-5 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
          <h3 className="font-semibold text-gray-700">Top Customers</h3>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            Show top
            <select
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="px-2 py-1 border border-gray-200 rounded-lg text-sm focus:outline-none"
            >
              {[10, 20, 50, 100].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            customers
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-500 w-10">#</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Company</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Reports</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Recruiters</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Tests Used</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">QBs Used</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {(topCustomers || []).map((row, i) => (
                <tr key={row.company} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-400 text-xs">{i + 1}</td>
                  <td className="px-4 py-3 font-medium text-gray-800">{row.company}</td>
                  <td className="px-4 py-3 text-right font-bold text-orange-600">{fmt(row.reports)}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{row.recruiters}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{row.tests}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{row.qbs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
