import { create } from 'zustand'

const useFilterStore = create((set, get) => ({
  dateFrom: '',
  dateTo: '',
  companies: [],
  qbs: [],
  library: 'all',
  accountType: 'all',

  setDateFrom: (v) => set({ dateFrom: v }),
  setDateTo: (v) => set({ dateTo: v }),
  setCompanies: (v) => set({ companies: v }),
  setQbs: (v) => set({ qbs: v }),
  setLibrary: (v) => set({ library: v }),
  setAccountType: (v) => set({ accountType: v }),

  reset: () =>
    set({ dateFrom: '', dateTo: '', companies: [], qbs: [], library: 'all', accountType: 'all' }),

  // Returns query param object for API calls
  getParams: () => {
    const s = get()
    const p = {}
    if (s.dateFrom) p.date_from = s.dateFrom
    if (s.dateTo) p.date_to = s.dateTo
    if (s.companies.length) p.companies = s.companies.join(',')
    if (s.qbs.length) p.qbs = s.qbs.join(',')
    if (s.library !== 'all') p.library = s.library
    if (s.accountType !== 'all') p.account_type = s.accountType
    return p
  },

  activeCount: () => {
    const s = get()
    return [s.dateFrom, s.dateTo, s.companies.length > 0, s.qbs.length > 0,
      s.library !== 'all', s.accountType !== 'all'].filter(Boolean).length
  },
}))

export default useFilterStore
