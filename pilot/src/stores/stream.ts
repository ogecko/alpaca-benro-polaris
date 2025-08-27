// stores/telemetry.ts
import { defineStore } from 'pinia'

type LogMessage = { text: string }
type PIDMessage = { p: number; i: number; d: number }
type KalmanMessage = { estimate: number; variance: number }
type TelemetryMessage = LogMessage | PIDMessage | KalmanMessage

export type TelemetryRecord = {
  ts: string
  topic: string
  level: string
  data: TelemetryMessage
}




export const useStreamStore = defineStore('telemetry', {
  state: () => ({
    socket: null as WebSocket | null,
    topics: {} as Record<string, TelemetryRecord[]>,
    subscriptions: new Set<string>(),
    connected: false
  }),

  actions: {
    connect(url: string) {
        if (this.socket) return

        this.socket = new WebSocket(url)
        this.socket.onerror = (event) => {
            console.error("WebSocket error:", event)
        }

        this.socket.onclose = (event) => {
        console.warn("WebSocket closed:", event.code, event.reason)
        }

        this.socket.onopen = () => {
            this.connected = true
            this.subscriptions.forEach(topic => this.subscribe(topic))
        }

        this.socket.onmessage = (event) => {
            try {
                const record = JSON.parse(event.data)
                const topic = record.topic || record.type
                if (!this.topics[topic]) this.topics[topic] = []
                this.topics[topic].push(record)
                const MAX_RECORDS = 500
                if (this.topics[topic].length > MAX_RECORDS) {
                    this.topics[topic].splice(0, this.topics[topic].length - MAX_RECORDS)
                }
            } catch (err) {
                console.warn('Invalid telemetry:', err)
            }
      }

      this.socket.onclose = () => {
        this.connected = false
        this.socket = null
      }
    },

    subscribe(topic: string, filter: Record<string, unknown> = {}) {
      this.subscriptions.add(topic)
      if (this.connected && this.socket) {
        this.socket.send(JSON.stringify({ type: 'subscribe', topic, filter }))
      }
    },

    unsubscribe(topic: string) {
      this.subscriptions.delete(topic)
      this.topics[topic] = []
      if (this.connected && this.socket) {
        this.socket.send(JSON.stringify({ type: 'unsubscribe', topic }))
      }
    },

    ping() {
      if (this.connected && this.socket) {
        this.socket.send(JSON.stringify({ type: 'ping' }))
      }
    },

    clear(topic: string) {
      this.topics[topic] = []
    }
  }
})
