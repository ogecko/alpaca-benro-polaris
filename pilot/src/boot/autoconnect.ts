// boot/autoconnect.ts
import { useDeviceStore } from 'stores/device'

export default async () => {
  const dev = useDeviceStore()
  await dev.connectRestAPI()
}
