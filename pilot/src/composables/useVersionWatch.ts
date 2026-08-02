// src/composables/useVersionWatch.ts
import { onUnmounted } from 'vue'
import axios from 'axios'

export function useVersionWatch() {
  const initialVersion = { https: null as boolean | null, spa: '', boot: '' }
  let timer: ReturnType<typeof setInterval> | null = null


  async function checkVersion() {
    try {
      const r = await axios.get('/version', { timeout: 5000 })
      if (initialVersion.https === null) {
        initialVersion.https = r.data.https
        initialVersion.spa   = r.data.spa
        initialVersion.boot  = r.data.boot
        return
      }
      const httpsChanged = r.data.https !== initialVersion.https
      const spaChanged   = r.data.spa   !== initialVersion.spa
      const bootChanged  = r.data.boot  !== initialVersion.boot
      if (httpsChanged || spaChanged || bootChanged) {
        console.log(`Reloading — https changed: ${httpsChanged}, spa changed: ${spaChanged}, boot changed: ${bootChanged}`)
        window.location.reload()
      }
    } catch { /* retry next interval */ }
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