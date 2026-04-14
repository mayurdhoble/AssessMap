import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { Filter, X, ChevronDown } from 'lucide-react'
import useFilterStore from '../store/filterStore'
import api from '../api/client'

function MultiSelect({ options, value, onChange, placeholder }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [dropPos, setDropPos] = useState({ top: 0, left: 0 })
  const btnRef = useRef(null)
  const dropRef = useRef(null)
  const selected = value || []

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (
        btnRef.current && !btnRef.current.contains(e.target) &&
        dropRef.current && !dropRef.current.contains(e.target)
      ) {
        setOpen(false)
        setSearch('')
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Recompute drop position on scroll / resize while open
  useEffect(() => {
    if (!open) return
    const update = () => {
      if (btnRef.current) {
        const r = btnRef.current.getBoundingClientRect()
        setDropPos({ top: r.bottom + 4, left: r.left })
      }
    }
    update()
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
    }
  }, [open])

  const handleToggle = () => {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect()
      setDropPos({ top: r.bottom + 4, left: r.left })
    }
    setOpen((v) => !v)
    if (open) setSearch('')
  }

  const filtered = options.filter((o) => o.toLowerCase().includes(search.toLowerCase()))

  const toggle = (opt) => {
    onChange(selected.includes(opt) ? selected.filter((v) => v !== opt) : [...selected, opt])
  }

  const dropdown = open
    ? createPortal(
        <div
          ref={dropRef}
          style={{ position: 'fixed', top: dropPos.top, left: dropPos.left, zIndex: 9999, width: 272 }}
          className="bg-white border border-gray-200 rounded-lg shadow-2xl"
        >
          {/* Search */}
          <div className="p-2 border-b border-gray-100">
            <input
              autoFocus
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search…"
              className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:border-orange-300"
            />
          </div>

          {/* Clear all */}
          {selected.length > 0 && (
            <button
              onClick={() => { onChange([]); setOpen(false); setSearch('') }}
              className="w-full text-left px-3 py-2 text-xs text-orange-600 hover:bg-orange-50 border-b border-gray-100"
            >
              Clear all ({selected.length} selected)
            </button>
          )}

          {/* Options list */}
          <div className="max-h-56 overflow-y-auto">
            {filtered.length === 0 && (
              <p className="px-3 py-3 text-xs text-gray-400">No matches</p>
            )}
            {filtered.map((opt) => (
              <label
                key={opt}
                className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(opt)}
                  onChange={() => toggle(opt)}
                  className="accent-orange-500 shrink-0"
                />
                <span className="text-sm text-gray-700 truncate">{opt}</span>
              </label>
            ))}
          </div>
        </div>,
        document.body
      )
    : null

  return (
    <>
      <button
        ref={btnRef}
        onClick={handleToggle}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-colors whitespace-nowrap
          ${selected.length > 0
            ? 'border-orange-300 bg-orange-50 text-orange-700'
            : 'border-gray-200 text-gray-600 hover:border-gray-300'
          }`}
      >
        {selected.length > 0 ? `${placeholder} (${selected.length})` : placeholder}
        <ChevronDown size={14} />
      </button>
      {dropdown}
    </>
  )
}

export default function GlobalFilters() {
  const store = useFilterStore()
  const count = store.activeCount()

  const { data: options } = useQuery({
    queryKey: ['filter-options'],
    queryFn: () => api.get('/filters/options').then((r) => r.data),
    staleTime: 60_000,
  })

  return (
    <div className="flex items-center gap-2 flex-wrap w-full">
      {/* Label */}
      <div className="flex items-center gap-1.5 text-gray-500 text-sm font-medium shrink-0">
        <Filter size={15} />
        Filters
        {count > 0 && (
          <span className="bg-orange-500 text-white text-xs w-4 h-4 rounded-full flex items-center justify-center leading-none">
            {count}
          </span>
        )}
      </div>

      {/* Date range */}
      <div className="flex items-center gap-1 shrink-0">
        <input
          type="date"
          value={store.dateFrom}
          onChange={(e) => store.setDateFrom(e.target.value)}
          className="px-2 py-1.5 border border-gray-200 rounded-lg text-sm text-gray-600 focus:outline-none focus:border-orange-300"
        />
        <span className="text-gray-400 text-xs">–</span>
        <input
          type="date"
          value={store.dateTo}
          onChange={(e) => store.setDateTo(e.target.value)}
          className="px-2 py-1.5 border border-gray-200 rounded-lg text-sm text-gray-600 focus:outline-none focus:border-orange-300"
        />
      </div>

      <MultiSelect
        options={options?.companies || []}
        value={store.companies}
        onChange={store.setCompanies}
        placeholder="Companies"
      />

      <MultiSelect
        options={options?.qbs || []}
        value={store.qbs}
        onChange={store.setQbs}
        placeholder="Question Banks"
      />

      <select
        value={store.library}
        onChange={(e) => store.setLibrary(e.target.value)}
        className={`px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:border-orange-300 transition-colors
          ${store.library !== 'all' ? 'border-orange-300 bg-orange-50 text-orange-700' : 'border-gray-200 text-gray-600'}`}
      >
        <option value="all">All Libraries</option>
        {(options?.libraries || []).map((l) => (
          <option key={l} value={l}>{l}</option>
        ))}
      </select>

      <select
        value={store.accountType}
        onChange={(e) => store.setAccountType(e.target.value)}
        className={`px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:border-orange-300 transition-colors
          ${store.accountType !== 'all' ? 'border-orange-300 bg-orange-50 text-orange-700' : 'border-gray-200 text-gray-600'}`}
      >
        <option value="all">All Account Types</option>
        {(options?.account_types || []).map((a) => (
          <option key={a} value={a}>Type {a}</option>
        ))}
      </select>

      {count > 0 && (
        <button
          onClick={store.reset}
          className="flex items-center gap-1 px-2 py-1.5 text-sm text-gray-400 hover:text-red-500 transition-colors"
        >
          <X size={14} />
          Reset
        </button>
      )}
    </div>
  )
}
