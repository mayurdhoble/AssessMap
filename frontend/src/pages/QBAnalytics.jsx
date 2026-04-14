import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { X, ChevronRight } from 'lucide-react'
import useFilterStore from '../store/filterStore'
import api from '../api/client'

export default function QBAnalytics() {
  const [selectedQB, setSelectedQB] = useState(null)
  const params = useFilterStore((s) => s.getParams())

  const { data: qbs } = useQuery({
    queryKey: ['qb-summary', params],
    queryFn: () => api.get('/qb/summary', { params }).then((r) => r.data),
  })

  const { data: qbCustomers, isLoading: loadingCustomers } = useQuery({
    queryKey: ['qb-customers', selectedQB, params],
    queryFn: () =>
      api.get(`/qb/${encodeURIComponent(selectedQB)}/top-customers`, { params }).then((r) => r.data),
    enabled: !!selectedQB,
  })

  const fmt = (n) => n?.toLocaleString() ?? '—'
  const chartData = (qbs || []).slice(0, 15)

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-800">QB Analytics</h1>

      {/* Bar chart */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 className="font-semibold text-gray-700 mb-4">Top 15 Question Banks by Reports</h3>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 4, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => v.toLocaleString()} />
            <YAxis type="category" dataKey="qb_name" tick={{ fontSize: 11 }} width={150} />
            <Tooltip formatter={(v) => v.toLocaleString()} />
            <Bar dataKey="total_reports" fill="#6C3EB9" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="p-5 border-b border-gray-100">
          <h3 className="font-semibold text-gray-700">All Question Banks</h3>
          <p className="text-xs text-gray-400 mt-0.5">Click any row to see top customers for that QB</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-500">QB Name</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Library</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Total Reports</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Companies Using</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Assessments</th>
                <th className="px-4 py-3 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {(qbs || []).map((row) => (
                <tr
                  key={row.qb_name}
                  onClick={() => setSelectedQB(row.qb_name === selectedQB ? null : row.qb_name)}
                  className={`cursor-pointer transition-colors
                    ${selectedQB === row.qb_name
                      ? 'bg-purple-50'
                      : 'hover:bg-gray-50'
                    }`}
                >
                  <td className="px-4 py-3 font-medium text-gray-800">{row.qb_name}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                      ${row.library === 'IMOCHA QB'
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-blue-100 text-blue-700'
                      }`}>
                      {row.library}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-orange-600">{fmt(row.total_reports)}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{row.companies_using}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{row.assessments}</td>
                  <td className="px-4 py-3 text-right text-gray-400">
                    <ChevronRight size={14} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Side panel / modal for QB customers */}
      {selectedQB && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
            <div className="flex items-start justify-between p-5 border-b border-gray-100">
              <div>
                <h3 className="font-semibold text-gray-800">{selectedQB}</h3>
                <p className="text-xs text-gray-400 mt-0.5">Top customers by reports generated</p>
              </div>
              <button
                onClick={() => setSelectedQB(null)}
                className="text-gray-400 hover:text-gray-600 transition-colors ml-4"
              >
                <X size={20} />
              </button>
            </div>
            <div className="p-5">
              {loadingCustomers ? (
                <div className="text-center py-8">
                  <div className="inline-block w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="pb-2.5 text-left font-medium text-gray-500 w-8">#</th>
                      <th className="pb-2.5 text-left font-medium text-gray-500">Company</th>
                      <th className="pb-2.5 text-right font-medium text-gray-500">Reports</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {(qbCustomers || []).map((row, i) => (
                      <tr key={row.company} className="hover:bg-gray-50">
                        <td className="py-2.5 text-gray-400 text-xs">{i + 1}</td>
                        <td className="py-2.5 font-medium text-gray-800">{row.company}</td>
                        <td className="py-2.5 text-right font-bold text-orange-600">
                          {fmt(row.reports)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
