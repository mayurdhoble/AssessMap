import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import useFilterStore from '../store/filterStore'
import api from '../api/client'

export default function CompanyDrilldown() {
  const navigate = useNavigate()
  const params = useFilterStore((s) => s.getParams())
  // Company list uses only library + account_type filters (no QB filter)
  const listParams = {
    ...(params.date_from && { date_from: params.date_from }),
    ...(params.date_to && { date_to: params.date_to }),
    ...(params.library && { library: params.library }),
    ...(params.account_type && { account_type: params.account_type }),
  }

  const { data: companies, isLoading } = useQuery({
    queryKey: ['company-summary', listParams],
    queryFn: () => api.get('/company/summary', { params: listParams }).then((r) => r.data),
  })

  const fmt = (n) => n?.toLocaleString() ?? '—'

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-800">Companies</h1>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="p-5 border-b border-gray-100">
          <h3 className="font-semibold text-gray-700">
            All Companies
            {companies?.length ? (
              <span className="ml-2 text-sm font-normal text-gray-400">({companies.length})</span>
            ) : null}
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">Click a row to drill into company details</p>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 w-10">#</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Company</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Account Type</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Reports</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Recruiters</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Tests</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">QBs</th>
                  <th className="px-4 py-3 w-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {(companies || []).map((row, i) => (
                  <tr
                    key={row.company}
                    onClick={() => navigate(`/company/${encodeURIComponent(row.company)}`)}
                    className="cursor-pointer hover:bg-orange-50 transition-colors"
                  >
                    <td className="px-4 py-3 text-gray-400 text-xs">{i + 1}</td>
                    <td className="px-4 py-3 font-medium text-orange-600">{row.company}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                        ${row.account_type === '1'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-blue-100 text-blue-700'
                        }`}>
                        Type {row.account_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-bold text-orange-600">{fmt(row.reports)}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.recruiters}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.tests}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.qbs}</td>
                    <td className="px-4 py-3 text-right text-gray-400">
                      <ChevronRight size={14} />
                    </td>
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
