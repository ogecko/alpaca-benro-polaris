import { effectScope, ref, watch } from 'vue'
import { Notify } from 'quasar'
import { useConfigStore } from 'src/stores/config'
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status'
import { getLocationServices } from 'src/utils/locationServices'

// A GPS Locate runs in the driver, which reports it in its status (gpsrun, gpsstate, gpsattempts, gpserror): every
// Pilot window sees its progress. The window that started (or joined) a Locate follows that run to its result here,
// wherever Pilot is, and only that window adds the site name and pressure and announces it -- once.

export const followedGpsRun = ref(0)          // the Locate this window is waiting on (0: none)
let watching = false
let onApplied: ((keys: string[]) => void) | null = null

// The Settings page highlights the fields a Locate changed, while it is open
export function setGpsLocateAppliedHandler(handler: ((keys: string[]) => void) | null) {
  onApplied = handler
}

export async function startGpsLocate(): Promise<void> {
  const dev = useDeviceStore()
  watchGpsStatus()
  try {
    const { run, joined } = await dev.alpacaGpsLocate()
    if (joined && run !== followedGpsRun.value) {
      Notify.create({ message: 'A GPS Locate is already running (started from another Pilot window). Its result will be shown here.',
        type: 'info', position: 'top', timeout: 5000 })
    }
    followedGpsRun.value = run
    await finishIfDone()                        // a quick Locate may already be over
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    Notify.create({ message: `GPS Locate could not start: ${message}`, type: 'negative', position: 'top',
      multiLine: true, classes: 'notify-wrap',
      timeout: 10000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  }
}

function watchGpsStatus() {
  if (watching) return
  watching = true
  const p = useStatusStore()
  // detached: keeps following while the page that started the Locate is left
  effectScope(true).run(() => {
    watch(() => [p.gpsrun, p.gpsstate], () => { void finishIfDone() })
  })
}

async function finishIfDone() {
  const p = useStatusStore()
  const cfg = useConfigStore()
  const run = followedGpsRun.value
  if (!run || p.gpsrun !== run || p.gpsstate === 'running' || p.gpsstate === 'idle') return
  followedGpsRun.value = 0
  if (p.gpsstate !== 'found') {
    // no fallback to the browser's location: at a dark site it can be somewhere else entirely (IP-based)
    Notify.create({
      message: p.gpserror || 'No valid GPS fix. Location unchanged.',
      type: 'negative', position: 'top', multiLine: true, classes: 'notify-wrap',   // a few lines, not one wide one
      timeout: 10000,                           // long enough to read why (no fix yet, or no data from the port)
      actions: [{ icon: 'mdi-close', color: 'white' }],
    })
    return
  }
  // the driver has applied latitude, longitude and elevation; add the site's name and pressure (online lookups)
  await cfg.configFetch(['site_latitude', 'site_longitude', 'site_elevation'])
  const result = await getLocationServices(cfg.site_latitude, cfg.site_longitude, cfg.site_elevation)
  if (result.success) {
    await cfg.configUpdate(result.data)
    onApplied?.(Object.keys(result.data))
  }
  Notify.create({ message: 'Location updated by GPS receiver.', type: 'positive', position: 'top', timeout: 3000,
    actions: [{ icon: 'mdi-close', color: 'white' }] })
}
