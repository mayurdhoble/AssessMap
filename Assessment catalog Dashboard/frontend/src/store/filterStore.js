import { create } from 'zustand'

const useFilterStore = create((set, get) => ({
  names: [],
  dateFrom: '',
  dateTo: '',
  labels: [],
  types: [],
  statuses: [],

  setNames: (v) => set({ names: v }),
  setDateFrom: (v) => set({ dateFrom: v }),
  setDateTo: (v) => set({ dateTo: v }),
  setLabels: (v) => set({ labels: v }),
  setTypes: (v) => set({ types: v }),
  setStatuses: (v) => set({ statuses: v }),

  reset: () =>
    set({ names: [], dateFrom: '', dateTo: '', labels: [], types: [], statuses: [] }),

  getParams: () => {
    const s = get()
    const p = {}
    if (s.names.length) p.names = s.names.join(',')
    if (s.dateFrom) p.date_from = s.dateFrom
    if (s.dateTo) p.date_to = s.dateTo
    if (s.labels.length) p.labels = s.labels.join(',')
    if (s.types.length) p.types = s.types.join(',')
    if (s.statuses.length) p.statuses = s.statuses.join(',')
    return p
  },

  activeCount: () => {
    const s = get()
    return [
      s.names.length > 0, s.dateFrom, s.dateTo,
      s.labels.length > 0, s.types.length > 0, s.statuses.length > 0,
    ].filter(Boolean).length
  },
}))

export default useFilterStore
