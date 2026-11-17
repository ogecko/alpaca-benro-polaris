// boot/analytics.ts
// Anonymous page-view analytics for Alpaca Pilot (Google Analytics 4, the "Alpaca Pilot App" stream of the docs property).
// Turned on and off by enable_analytics in the driver config (Network Settings > Send Anonymous Usage Analytics).
//  * Nothing is loaded or sent until the driver config has been fetched, so a user who turned it off is never counted.
//  * Pilot runs at addresses such as 192.168.0.5 or nina01.local; each page is reported against a fixed placeholder
//    host instead, so no local address or hostname is sent, and the same page from any host reports as one page.
//  * Offline (eg. at a dark site) the Google tag simply fails to load and nothing is sent; GA does not queue hits.
import { defineBoot } from '#q-app'
import { watch } from 'vue'
import { useConfigStore } from 'stores/config'
import { useDeviceStore } from 'stores/device'
import { version as pilotVersion } from '../../package.json'

const MEASUREMENT_ID = 'G-G10HDVFJ0N'
const REPORTED_HOST = 'https://alpaca-pilot.app'

type Gtag = (...args: unknown[]) => void
declare global {
  interface Window { dataLayer?: unknown[]; gtag?: Gtag; [key: `ga-disable-${string}`]: boolean | undefined }
}

let loaded = false

// Pilot's document.title is always "Alpaca Pilot App", so name each page from its path: '/dashboard' -> 'Pilot - Dashboard'
function pageTitle(path: string): string {
  const page = path.split('/').filter(Boolean)[0]
  return `Pilot - ${page ? page.charAt(0).toUpperCase() + page.slice(1) : 'Startup'}`
}

function loadGtag(driverVersion: string) {
  window.dataLayer = window.dataLayer || []
  // gtag must push the arguments object itself, not an array, for the Google tag to read it
  // eslint-disable-next-line prefer-rest-params
  window.gtag = function () { window.dataLayer!.push(arguments) }
  window.gtag('js', new Date())
  window.gtag('config', MEASUREMENT_ID, {
    send_page_view: false,        // sent on each route change below
    app_version: pilotVersion,    // custom dimension "App version"
    driver_version: driverVersion // custom dimension "Driver version"
  })
  const script = document.createElement('script')
  script.async = true
  script.src = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`
  document.head.appendChild(script)
  loaded = true
}

export default defineBoot(({ router }) => {
  const cfg = useConfigStore()
  const dev = useDeviceStore()

  const isEnabled = () => cfg.fetchedAt > 0 && cfg.enable_analytics

  function pageView(path: string) {
    if (!loaded || !isEnabled()) return
    // Set (not just send) the placeholder location, so the other events GA sends, such as scrolls and outbound
    // clicks, report it too, rather than the local address in the browser's address bar
    window.gtag!('set', { page_location: `${REPORTED_HOST}${path}`, page_title: pageTitle(path) })
    window.gtag!('event', 'page_view')
  }

  // Start (or pause/resume) once the config is known and whenever enable_analytics changes
  watch(
    () => isEnabled(),
    (enabled) => {
      window[`ga-disable-${MEASUREMENT_ID}`] = !enabled
      if (enabled && !loaded) {
        loadGtag(dev.alpacaServerVersion)
        pageView(router.currentRoute.value.path)
      }
    },
    { immediate: true },
  )

  router.afterEach((to, from) => {
    if (to.path !== from.path) pageView(to.path)
  })
})
