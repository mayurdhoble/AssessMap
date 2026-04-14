import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import useFilterStore from '../store/filterStore'
import api from '../api/client'

// ── QB sub-table rendered inside the accordion ──────────────────────────────
function CategoryQBs({ category, params }) {
  const { data: qbs, isLoading } = useQuery({
    queryKey: ['category-qbs', category, params],
    queryFn: () =>
      api
        .get(`/category/${encodeURIComponent(category)}/qbs`, { params })
        .then((r) => r.data),
  })

  const fmt = (n) => n?.toLocaleString() ?? '—'

  if (isLoading) {
    return (
      <tr>
        <td colSpan={6} className="px-6 py-4 bg-orange-50/60">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Loader2 size={14} className="animate-spin" />
            Loading QBs…
          </div>
        </td>
      </tr>
    )
  }

  if (!qbs?.length) {
    return (
      <tr>
        <td colSpan={6} className="px-6 py-3 bg-orange-50/60 text-sm text-gray-400 italic">
          No QBs found for this category.
        </td>
      </tr>
    )
  }

  return (
    <tr>
      <td colSpan={6} className="p-0 bg-orange-50/40">
        <div className="border-t border-orange-100">
          {/* Sub-header */}
          <div className="px-6 py-2 bg-orange-50 border-b border-orange-100 flex items-center justify-between">
            <span className="text-xs font-semibold text-orange-700 uppercase tracking-wide">
              Question Banks in this category
            </span>
            <span className="text-xs text-orange-500">{qbs.length} QBs</span>
          </div>

          {/* Sub-table */}
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-orange-50/80 border-b border-orange-100">
                <th className="pl-10 pr-4 py-2.5 text-left font-medium text-gray-500">#</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-500">QB Name</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-500">Library</th>
                <th className="px-4 py-2.5 text-right font-medium text-gray-500">Reports</th>
                <th className="px-4 py-2.5 text-right font-medium text-gray-500">Companies</th>
                <th className="px-4 py-2.5 text-right font-medium text-gray-500">Assessments</th>
                <th className="px-4 py-2.5 text-right font-medium text-gray-500">Recruiters</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-orange-100/60">
              {qbs.map((qb, i) => (
                <tr key={qb.qb_name} className="hover:bg-orange-50 transition-colors">
                  <td className="pl-10 pr-4 py-2.5 text-gray-400 text-xs">{i + 1}</td>
                  <td className="px-4 py-2.5 font-medium text-gray-800">{qb.qb_name}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium
                        ${qb.library === 'IMOCHA QB'
                          ? 'bg-purple-100 text-purple-700'
                          : 'bg-blue-100 text-blue-700'
                        }`}
                    >
                      {qb.library}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-bold text-orange-600">
                    {fmt(qb.reports)}
                  </td>
                  <td className="px-4 py-2.5 text-right text-gray-600">{qb.companies}</td>
                  <td className="px-4 py-2.5 text-right text-gray-600">{qb.assessments}</td>
                  <td className="px-4 py-2.5 text-right text-gray-600">{qb.recruiters}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </td>
    </tr>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function CategoryAnalysis() {
  const [expanded, setExpanded] = useState(new Set())
  const params = useFilterStore((s) => s.getParams())

  const { data: categories } = useQuery({
    queryKey: ['categories', params],
    queryFn: () => api.get('/category/breakdown', { params }).then((r) => r.data),
  })

  const { data: acctComp } = useQuery({
    queryKey: ['account-type-comparison', params],
    queryFn: () => api.get('/category/account-type-comparison', { params }).then((r) => r.data),
  })

  const fmt = (n) => n?.toLocaleString() ?? '—'
  const top20 = (categories || []).slice(0, 20)

  const toggleRow = (category) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(category) ? next.delete(category) : next.add(category)
      return next
    })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-800">Category & Account Type Analysis</h1>

      {/* Top charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category bar chart */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Top Categories by Reports</h3>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={top20} layout="vertical" margin={{ left: 4, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => v.toLocaleString()} />
              <YAxis type="category" dataKey="category" tick={{ fontSize: 10 }} width={150} />
              <Tooltip formatter={(v) => v.toLocaleString()} />
              <Bar dataKey="reports" fill="#FF6B35" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Account type cards */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Account Type Breakdown</h3>
          <div className="space-y-4">
            {(acctComp || []).map((row, i) => (
              <div
                key={row.account_type}
                className={`p-5 rounded-xl border ${i === 0 ? 'border-orange-200 bg-orange-50' : 'border-blue-200 bg-blue-50'}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-semibold text-gray-700">Account Type {row.account_type}</span>
                  <span className={`text-3xl font-bold ${i === 0 ? 'text-orange-600' : 'text-blue-600'}`}>
                    {fmt(row.reports)}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="bg-white/70 rounded-lg p-2">
                    <p className="font-bold text-gray-800">{row.companies}</p>
                    <p className="text-xs text-gray-500">Companies</p>
                  </div>
                  <div className="bg-white/70 rounded-lg p-2">
                    <p className="font-bold text-gray-800">{row.recruiters}</p>
                    <p className="text-xs text-gray-500">Recruiters</p>
                  </div>
                  <div className="bg-white/70 rounded-lg p-2">
                    <p className="font-bold text-gray-800">{row.qbs}</p>
                    <p className="text-xs text-gray-500">QBs Used</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Accordion table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="p-5 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-700">All Categories</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Click any row to expand and see its Question Banks
            </p>
          </div>
          <div className="flex items-center gap-3">
            {expanded.size > 0 && (
              <button
                onClick={() => setExpanded(new Set())}
                className="text-xs text-gray-400 hover:text-red-500 transition-colors"
              >
                Collapse all
              </button>
            )}
            <span className="text-xs text-gray-400">{categories?.length} categories</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 w-8" />
                <th className="px-4 py-3 text-left font-medium text-gray-500">Category</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Reports</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Companies</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">QBs</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Recruiters</th>
              </tr>
            </thead>
            <tbody>
              {(categories || []).map((row) => {
                const isOpen = expanded.has(row.category)
                return (
                  <>
                    {/* Category row */}
                    <tr
                      key={row.category}
                      onClick={() => toggleRow(row.category)}
                      className={`cursor-pointer border-t border-gray-50 transition-colors
                        ${isOpen ? 'bg-orange-50' : 'hover:bg-gray-50'}`}
                    >
                      {/* Expand icon */}
                      <td className="px-4 py-3 text-gray-400">
                        {isOpen
                          ? <ChevronDown size={15} className="text-orange-500" />
                          : <ChevronRight size={15} />
                        }
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-800">
                        {row.category || <span className="text-gray-400 italic">uncategorized</span>}
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-orange-600">
                        {fmt(row.reports)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">{row.companies}</td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        <span className={isOpen ? 'text-orange-600 font-semibold' : ''}>
                          {row.qbs}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">{row.recruiters}</td>
                    </tr>

                    {/* Accordion content — QB sub-table */}
                    {isOpen && (
                      <CategoryQBs
                        key={`qbs-${row.category}`}
                        category={row.category}
                        params={params}
                      />
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
