// src/composables/useVersionWatch.ts
import { onUnmounted } from 'vue'
import axios from 'axios'

export function useVersionWatch() {
  const initialVersion = { https: null as boolean | null, spa: '' }
  let timer: ReturnType<typeof setInterval> | null = null

  async function checkVersion(): Promise<void> {
    try {
      const r = await axios.get('/version', { timeout: 5000 })
      if (initialVersion.https === null) {
        // Capture baseline on first successful response
        initialVersion.https = r.data.https
        initialVersion.spa   = r.data.spa
        return
      }
      const httpsChanged = r.data.https !== initialVersion.https
      const spaChanged   = r.data.spa   !== initialVersion.spa
      if (httpsChanged || spaChanged) {
        console.log(`Reloading — https changed: ${httpsChanged}, spa changed: ${spaChanged}`)
        window.location.href = window.location.origin
      }
    } catch {
      // Server unreachable — driver may be restarting, retry next interval
    }
  }

  function startVersionWatch(): void {
    void checkVersion()
    timer = setInterval(() => { void checkVersion() }, 10_000)
  }

  onUnmounted(() => {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  })

  return { startVersionWatch }
}