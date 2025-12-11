// boot/autoconnect.ts
import { useDeviceStore } from 'stores/device'

export default async () => {
  const dev = useDeviceStore()

  if (dev.alpacaHost && dev.restAPIPort) {
    await dev.connectRestAPI()
  }
}
