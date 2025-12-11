export class PollingManager {
  private intervalId: number | null = null
  private pollFn: (() => void | Promise<void>) | null = null
  private fnName: (string | null) = null
  private intervalMs: number = 10000

  constructor() {}

  startPolling(fn: () => void, intervalSeconds: number = 10, label?: string) {
    this.fnName = label || fn.name || '[anonymous]'
    console.log(`Starting polling: ${this.fnName} every ${intervalSeconds}s`)

    this.pollFn = fn
    this.intervalMs = intervalSeconds * 1000

    this.intervalId = window.setInterval(() => {
      if (document.visibilityState === 'visible' && this.pollFn) {
        Promise.resolve(this.pollFn())
          .catch(err => console.warn('Polling function threw:', err))
      }
    }, this.intervalMs)
  }

  stopPolling() {
    if (this.intervalId !== null) {
      console.log(`Stop polling: ${this.fnName}`)
      clearInterval(this.intervalId)
      this.intervalId = null
    }
  }
}
