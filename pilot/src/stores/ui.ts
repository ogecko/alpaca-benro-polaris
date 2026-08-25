// src/stores/ui.ts
// Used to store any information that needs to be persisted between page changes and on a per tab basis
// Information stored to sessionStorage will also persist across page refresh F5
import { defineStore } from 'pinia'

export const useUIStore = defineStore('ui', {
  state: () => ({
    coordFrame: parseInt(sessionStorage.getItem('ui.coordFrame') ?? '0') as 0 | 1 | 2,
    scaleRanges: {} as Record<string, number>,
    catalogFilter: JSON.parse(sessionStorage.getItem('ui.catalogFilter') ?? '{}') as Record<string, number[]>,
    catalogSort: sessionStorage.getItem('ui.catalogSort') ?? '',
    showStatusPanel: sessionStorage.getItem('ui.showStatusPanel') === 'true',
    showLeftDrawer: (sessionStorage.getItem('ui.showLeftDrawer') ?? 'true')=== 'true',
  }),
  actions: {
    setCoordFrame(val: 0 | 1 | 2) {
      this.coordFrame = val
      sessionStorage.setItem('ui.coordFrame', String(val))
    },
    cycleCoordFrame() {
      const newval = ((this.coordFrame + 1) % 3) as 0 | 1 | 2
      this.coordFrame = newval
      sessionStorage.setItem('ui.coordFrame', String(newval))
    },
    setScaleRange(label: string, range: number) {
      this.scaleRanges[label] = range
    },
    getScaleRange(label: string, defaultRange: number): number {
      return this.scaleRanges[label] ?? defaultRange
    },
    setCatalogFilter(filter: Record<string, number[] | undefined>) {
      this.catalogFilter = JSON.parse(JSON.stringify(filter))
      sessionStorage.setItem('ui.catalogFilter', JSON.stringify(this.catalogFilter))
    },
    setCatalogSort(sort: string) {
      this.catalogSort = sort
      sessionStorage.setItem('ui.catalogSort', sort)
    },
    toggleShowStatusPanel() {
      this.showStatusPanel = !this.showStatusPanel
      sessionStorage.setItem('ui.showStatusPanel', String(this.showStatusPanel))
    },
    toggleShowLeftDrawer() {
      this.setShowLeftDrawer(!this.showLeftDrawer)
    },
    setShowLeftDrawer(val: boolean) {
      // Dedicated setter (rather than relying on q-drawer's v-model to mutate
      // showLeftDrawer directly) so every path that changes it -- including the
      // drawer dismissing itself, eg. clicking its own backdrop in overlay mode --
      // persists to sessionStorage, not just the explicit toggle button.
      this.showLeftDrawer = val
      sessionStorage.setItem('ui.showLeftDrawer', String(val))
    }
  }
})