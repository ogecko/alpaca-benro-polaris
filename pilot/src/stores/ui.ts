// src/stores/ui.ts
// Used to store any information that needs to be persisted between page changes and on a per tab basis
// Information stored to sessionStorage will also persist across page refresh F5
import { defineStore } from 'pinia'

// Documentation links: the online site is preferred, so users always see the latest docs.
// When it can't be reached (eg. at a dark site without internet), links fall back to the
// offline copy the driver serves at /docs/ (downloaded once per driver version), if present.
const DOCS_ONLINE_ROOT = 'https://ogecko.github.io/alpaca-benro-polaris/'
const DOCS_ONLINE = `${DOCS_ONLINE_ROOT}v2.2/`
const DOCS_LOCAL = '/docs/'
const DOCS_PROBE_TIMEOUT_MS = 2500
const DOCS_RECHECK_MS = 5 * 60 * 1000

async function probe(url: string, init: RequestInit): Promise<Response | null> {
  try {
    return await fetch(url, { ...init, cache: 'no-store', signal: AbortSignal.timeout(DOCS_PROBE_TIMEOUT_MS) })
  } catch {
    return null       // network error, DNS failure or timeout
  }
}

let docsCheck: Promise<void> | null = null

export const useUIStore = defineStore('ui', {
  state: () => ({
    coordFrame: parseInt(sessionStorage.getItem('ui.coordFrame') ?? '0') as 0 | 1 | 2,
    scaleRanges: {} as Record<string, number>,
    catalogFilter: JSON.parse(sessionStorage.getItem('ui.catalogFilter') ?? '{}') as Record<string, number[]>,
    catalogSort: sessionStorage.getItem('ui.catalogSort') ?? '',
    showStatusPanel: sessionStorage.getItem('ui.showStatusPanel') === 'true',
    showLeftDrawer: (sessionStorage.getItem('ui.showLeftDrawer') ?? 'true')=== 'true',
    driverTimeout: (sessionStorage.getItem('ui.driverTimeout') ?? 1000) as number,
    docsMode: 'online' as 'online' | 'local',
    docsCheckedAt: 0,
  }),
  getters: {
    // URL for a documentation page, eg. docsUrl('pilot/') or docsUrl('initial-setup/#using-https')
    docsUrl: (state) => (page = '') => (state.docsMode === 'local' ? DOCS_LOCAL : DOCS_ONLINE) + page,
  },
  actions: {
    // Decide whether docs links go to the online site or the local copy. Run ahead of time
    // (not on click), as a link opening a new tab must do so straight away or be blocked as a popup.
    checkDocsMode(force = false): Promise<void> {
      if (docsCheck) return docsCheck
      if (!force && this.docsCheckedAt && Date.now() - this.docsCheckedAt < DOCS_RECHECK_MS) return Promise.resolve()
      docsCheck = (async () => {
        let online = navigator.onLine
        if (online) {
          // no-cors gives an opaque response if GitHub Pages answers at all, and throws if it can't be reached
          online = (await probe(`${DOCS_ONLINE_ROOT}versions.json`, { mode: 'no-cors' })) !== null
        }
        let mode: 'online' | 'local' = 'online'
        if (!online) {
          const local = await probe(DOCS_LOCAL, {})       // the driver's /docs/ route has no HEAD handler
          if (local?.ok) mode = 'local'       // otherwise keep online links rather than a "not built" page
        }
        this.docsMode = mode
        this.docsCheckedAt = Date.now()
      })().finally(() => { docsCheck = null })
      return docsCheck
    },

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
    },
    setDriverTimeout(val: string | number | null) {
      // Used in StatusBanners to detect stale connection from Pilot to the Driver
      this.driverTimeout = Math.max(1000, val as number)
      sessionStorage.setItem('ui.driverTimeout', String(this.driverTimeout))
    },
  }
})