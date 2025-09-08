// stores/telemetry.ts
import { defineStore } from 'pinia'
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status';
import { computed, ref } from 'vue'

export type LogMessage = { text: string }
export type PIDMessage = { p: number; i: number; d: number }
export type KalmanMessage = { θ1_meas: number;  }
export type TelemetryMessage = LogMessage | PIDMessage | KalmanMessage

export type TelemetryRecord = {
  ts: string
  topic: string
  level: string
  data: TelemetryMessage
}


export const useStreamStore = defineStore('telemetry', () => {
  const dev = useDeviceStore()
  const status = useStatusStore()

  // Reactive derived config
  const socketHost = computed(() => dev.alpacaHost)
  const socketPort = computed(() => dev.socketAPIPort)
  const socketURL = computed(() => `ws://${socketHost.value}:${socketPort.value}/ws`)
  const socketConnected = computed(() => socketConnectionStatus.value === 'connected')

  // State
  const socketConnectionStatus = ref<'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error'>('disconnected')
  const lastActivity = ref(Date.now())
  const topics = ref<Record<string, TelemetryRecord[]>>({})
  const subscriptions = ref(new Set<string>())
  const _socket = ref<WebSocket | null>(null)
  const _socketConnectedURL = ref<string | null>(null)
  const _pingInterval = ref<ReturnType<typeof setInterval> | null>(null)
  const _reconnectTimeout = ref<ReturnType<typeof setTimeout> | null>(null)
  const retryCount = ref(0)

  // Actions (unchanged logic, just scoped)
  function connectSocket(url?: string | null) {
    const targetUrl = url ?? socketURL.value
    if (!targetUrl) return

    if (_socket.value && _socketConnectedURL.value !== targetUrl) {
      console.warn(`Switching WebSocket from ${_socketConnectedURL.value} to ${targetUrl}`)
      disconnectSocket()
    }

    if (_socket.value) return

    socketConnectionStatus.value = url ? 'connecting' : 'reconnecting'
    _socket.value = new WebSocket(targetUrl)
    _socketConnectedURL.value = targetUrl

    _socket.value.onopen = () => {
      socketConnectionStatus.value = 'connected'
      lastActivity.value = Date.now()
      retryCount.value = 0
      subscriptions.value.forEach(topic => subscribe(topic))
      startPing()
    }

    _socket.value.onmessage = (event) => {
      lastActivity.value = Date.now()
      try {
        const record = JSON.parse(event.data)
        const topic = record.topic || record.type
        if (topic === 'pong') return
        if (topic === 'status') {
          status.statusUpdate(record.data)
        } else {
          if (!topics.value[topic]) topics.value[topic] = []
          topics.value[topic].push(record)
          const MAX_RECORDS = 500
          if (topics.value[topic].length > MAX_RECORDS) {
            topics.value[topic].splice(0, topics.value[topic].length - MAX_RECORDS)
          }
        }
      } catch (err) {
        console.warn('Invalid telemetry:', err)
      }
    }

    _socket.value.onerror = (event) => {
      socketConnectionStatus.value = 'error'
      console.error("WebSocket error:", event)
    }

    _socket.value.onclose = (event) => {
      socketConnectionStatus.value = 'disconnected'
      console.warn("WebSocket closed:", event.code, event.reason)
      cleanupSocket()
      scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (_reconnectTimeout.value) return
    socketConnectionStatus.value = 'reconnecting'
    const delay = Math.min(1000 * Math.pow(2, retryCount.value), 10000)
    _reconnectTimeout.value = setTimeout(() => {
      _reconnectTimeout.value = null
      retryCount.value++
      connectSocket()
    }, delay)
  }

  function disconnectSocket() {
    socketConnectionStatus.value = 'disconnected'
    cleanupSocket()
    if (_reconnectTimeout.value) {
      clearTimeout(_reconnectTimeout.value)
      _reconnectTimeout.value = null
    }
  }

  function startPing() {
    stopPing()
    _pingInterval.value = setInterval(() => {
      ping()
      checkAlive()
    }, 5000)
  }

  function stopPing() {
    if (_pingInterval.value) {
      clearInterval(_pingInterval.value)
      _pingInterval.value = null
    }
  }

  function ping() {
    if (socketConnected.value && _socket.value) {
      _socket.value.send(JSON.stringify({ type: 'ping' }))
    }
  }

  function checkAlive() {
    const now = Date.now()
    const timeout = 10000
    if (now - lastActivity.value > timeout) {
      console.warn("Socket appears stale, reconnecting...")
      cleanupSocket()
      scheduleReconnect()
    }
  }

  function cleanupSocket() {
    stopPing()
    if (_socket.value) {
      _socket.value.close()
      _socket.value = null
    }
  }

  function subscribe(topic: string, filter: Record<string, unknown> = {}) {
    subscriptions.value.add(topic)
    if (socketConnected.value && _socket.value) {
      _socket.value.send(JSON.stringify({ type: 'subscribe', topic, filter }))
    }
  }

  function unsubscribe(topic: string) {
    subscriptions.value.delete(topic)
    topics.value[topic] = []
    if (socketConnected.value && _socket.value) {
      _socket.value.send(JSON.stringify({ type: 'unsubscribe', topic }))
    }
  }

  function clear(topic: string) {
    topics.value[topic] = []
  }

  return {
    socketHost,
    socketPort,
    socketURL,
    socketConnected,
    socketConnectionStatus,
    lastActivity,
    topics,
    subscriptions,
    connectSocket,
    disconnectSocket,
    subscribe,
    unsubscribe,
    clear,
  }
})
