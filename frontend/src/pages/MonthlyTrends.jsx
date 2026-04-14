import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import useFilterStore from '../store/filterStore'
import api from '../api/client'

const YEAR_COLORS = ['#FF6B35', '#6C3EB9', '#3B82F6', '#10B981']

export default function MonthlyTrends() {
  const store = useFilterStore()

  // Monthly trends only uses non-date filters (date range doesn't apply to YoY)
  const params = {
    ...(store.companies.length && { companies: store.companies.join(',') }),
    ...(store.library !== 'all' && { library: store.library }),
    ...(store.accountType !== 'all' && { account_type: store.accountType }),
  }

  const { data, isLoading } = useQuery({
    queryKey: ['monthly-trends', params],
    queryFn: () => api.get('/trends/monthly', { params }).then((r) => r.data),
  })

  const fmt = (n) => (n != null ? n.toLocaleString() : '—')
  const years = data?.years || []
  const currYear = years[0]
  const prevYear = years[1]

  return (
    <div className="space-y-6">
      {/* Header + totals */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <h1 className="text-xl font-bold text-gray-800">Monthly Trends (Year-over-Year)</h1>
        <div className="flex gap-6">
          {Object.entries(data?.totals || {}).map(([yr, total], i) => (
            <div key={yr} className="text-right">
              <p className="text-xs text-gray-400 uppercase tracking-wide">{yr} Total</p>
              <p className="text-2xl font-bold" style={{ color: YEAR_COLORS[i] }}>
                {fmt(total)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Line chart */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 className="font-semibold text-gray-700 mb-5">Reports by Month</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data?.chart || []} margin={{ top: 4, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => v.toLocaleString()} />
            <Tooltip formatter={(v) => (v != null ? v.toLocaleString() : 'N/A')} />
            <Legend />
            {years.map((yr, i) => (
              <Line
                key={yr}
                type="monotone"
                dataKey={yr}
                stroke={YEAR_COLORS[i]}
                strokeWidth={2.5}
                dot={{ r: 4, strokeWidth: 2 }}
                activeDot={{ r: 6 }}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Comparison table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="p-5 border-b border-gray-100">
          <h3 className="font-semibold text-gray-700">Month-wise Comparison</h3>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : !data?.has_date && (
          <div className="p-6 text-center text-amber-600 text-sm bg-amber-50">
            Date column not present in uploaded data — month-wise breakdown unavailable.
          </div>
        )}
        {(data?.table?.length > 0) && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-5 py-3 text-left font-medium text-gray-500">Month</th>
                  {prevYear && (
                    <th className="px-5 py-3 text-right font-medium text-gray-500">
                      Reports {prevYear}
                    </th>
                  )}
                  {currYear && (
                    <th className="px-5 py-3 text-right font-medium text-gray-500">
                      Reports {currYear}
                    </th>
                  )}
                  <th className="px-5 py-3 text-right font-medium text-gray-500">YoY Delta</th>
                  <th className="px-5 py-3 text-right font-medium text-gray-500">Daily Avg</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.table.map((row) => (
                  <tr key={row.month} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-semibold text-gray-700">{row.month}</td>
                    {prevYear && (
                      <td className="px-5 py-3 text-right text-gray-500">
                        {fmt(row[`reports_${prevYear}`])}
                      </td>
                    )}
                    {currYear && (
                      <td className="px-5 py-3 text-right font-semibold text-gray-800">
                        {fmt(row[`reports_${currYear}`])}
                      </td>
                    )}
                    <td className="px-5 py-3 text-right">
                      {row.delta != null ? (
                        <span
                          className={`font-medium ${row.delta >= 0 ? 'text-green-600' : 'text-red-500'}`}
                        >
                          {row.delta >= 0 ? '+' : ''}{fmt(row.delta)}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-gray-500">{fmt(row.daily_avg)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
