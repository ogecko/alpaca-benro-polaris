export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// needs to be converted to a composable
// import { useTimeout } from 'quasar'
// const { registerTimeout, removeTimeout } = useTimeout()

// export function sleep(ms:number): Promise<void> {
//   return new Promise(resolve => registerTimeout(resolve, ms))
// }

// export function removeSleep() {
//   removeTimeout()
// }

