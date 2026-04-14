import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { ArrowLeft } from 'lucide-react'
import api from '../api/client'
import useFilterStore from '../store/filterStore'

export default function CompanyDetail() {
  const { companyName } = useParams()
  const navigate = useNavigate()
  const store = useFilterStore()

  const company = decodeURIComponent(companyName)
  const params = {
    company,
    ...(store.dateFrom && { date_from: store.dateFrom }),
    ...(store.dateTo && { date_to: store.dateTo }),
  }

  const { data, isLoading } = useQuery({
    queryKey: ['company-detail', company, params.date_from, params.date_to],
    queryFn: () => api.get('/company/detail', { params }).then((r) => r.data),
  })

  const fmt = (n) => n?.toLocaleString() ?? '—'

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400">Loading…</div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-xl font-bold text-gray-800">{company}</h1>
          <p className="text-sm text-gray-400">
            {fmt(data?.total_reports)} total reports · {fmt(data?.total_rows)} rows
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Top Question Banks</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data?.top_qbs || []} layout="vertical" margin={{ left: 4, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => v.toLocaleString()} />
              <YAxis type="category" dataKey="qb_name" tick={{ fontSize: 11 }} width={130} />
              <Tooltip formatter={(v) => v.toLocaleString()} />
              <Bar dataKey="reports" fill="#FF6B35" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Categories Used</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart
              data={(data?.categories || []).slice(0, 8)}
              layout="vertical"
              margin={{ left: 4, right: 16 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => v.toLocaleString()} />
              <YAxis type="category" dataKey="category" tick={{ fontSize: 11 }} width={130} />
              <Tooltip formatter={(v) => v.toLocaleString()} />
              <Bar dataKey="reports" fill="#6C3EB9" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recruiters */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
          <div className="p-5 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-700">Recruiters</h3>
            <span className="text-xs text-gray-400">{data?.recruiters?.length} total</span>
          </div>
          <div className="overflow-y-auto max-h-64">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium text-gray-500">Email</th>
                  <th className="px-4 py-2.5 text-right font-medium text-gray-500">Reports</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {(data?.recruiters || []).map((r) => (
                  <tr key={r.email} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 text-gray-600 text-xs truncate max-w-xs" title={r.email}>
                      {r.email}
                    </td>
                    <td className="px-4 py-2.5 text-right font-medium text-orange-600">{fmt(r.reports)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Top Tests */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
          <div className="p-5 border-b border-gray-100">
            <h3 className="font-semibold text-gray-700">Top Tests</h3>
          </div>
          <div className="overflow-y-auto max-h-64">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium text-gray-500">Test Name</th>
                  <th className="px-4 py-2.5 text-right font-medium text-gray-500">Reports</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {(data?.top_tests || []).map((t) => (
                  <tr key={t.test_name} className="hover:bg-gray-50">
                    <td
                      className="px-4 py-2.5 text-gray-600 text-xs truncate max-w-xs"
                      title={t.test_name}
                    >
                      {t.test_name}
                    </td>
                    <td className="px-4 py-2.5 text-right font-medium text-orange-600">{fmt(t.reports)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
