// boot/autoconnect.ts
import { AppVisibility } from 'quasar'
import { useDeviceStore } from 'stores/device'

export default async () => {
  // Quasar's AppVisibility starts out "visible" and only changes on a visibilitychange event, which a page loaded in
  // a hidden tab never gets (e.g. the version watch reloading a background tab after a driver restart). Such a page
  // then subscribed to status as if visible, and the dashboard dials queued d3 transitions that a hidden tab never
  // runs -- hours of them, all started at once on return: a black, frozen tab at 100% CPU.
  AppVisibility.appVisible = !document.hidden
  const dev = useDeviceStore()
  await dev.connectRestAPI()
}
