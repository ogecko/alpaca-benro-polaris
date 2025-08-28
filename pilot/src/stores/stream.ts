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
    socketHost: 'nina01' as string,
    socketPort: 5556 as number,
    // socketURL is computed from socketHost and socketPort
    topics: {} as Record<string, TelemetryRecord[]>,
    subscriptions: new Set<string>(),
    socketConnectionStatus: 'disconnected' as 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error',
    lastActivity: Date.now(),
    _socket: null as WebSocket | null,            // holder for actual WebSocket
    _socketConnectedURL: null as string | null,   // URL of WebSocket connected
    _pingInterval: null as ReturnType<typeof setInterval> | null,
    _reconnectTimeout: null as ReturnType<typeof setTimeout> | null,
    retryCount: 0,
  }),

  getters: {
    socketURL: (state) => `ws://${state.socketHost}:${state.socketPort}/ws`,
    socketConnected: (state) => state.socketConnectionStatus === 'connected',
  },

  actions: {
    connectSocket(url?: string | null) {
      const targetUrl = url ?? this.socketURL;
      if (!targetUrl) return;

      // If already connected to a different URL, disconnect first
      if (this._socket && this._socketConnectedURL !== targetUrl) {
        console.warn(`Switching WebSocket from ${this._socketConnectedURL} to ${targetUrl}`);
        this.disconnectSocket(); // clean up old socket and timers
      }

      if (this._socket) return; // still connected to same URL

      this.socketConnectionStatus = url ? 'connecting': 'reconnecting';
      this._socket = new WebSocket(targetUrl);
      this._socketConnectedURL = targetUrl

      this._socket.onopen = () => {
        this.socketConnectionStatus = 'connected'; 
        this.lastActivity = Date.now();
        this.retryCount = 0;

        this.subscriptions.forEach(topic => this.subscribe(topic));

        this.startPing();
      };

      this._socket.onmessage = (event) => {
        this.lastActivity = Date.now(); // update activity
        try {
          const record = JSON.parse(event.data);
          const topic = record.topic || record.type;
          if (!this.topics[topic]) this.topics[topic] = [];
          this.topics[topic].push(record);
          const MAX_RECORDS = 500;
          if (this.topics[topic].length > MAX_RECORDS) {
            this.topics[topic].splice(0, this.topics[topic].length - MAX_RECORDS);
          }
        } catch (err) {
          console.warn('Invalid telemetry:', err);
        }
      };

      this._socket.onerror = (event) => {
        this.socketConnectionStatus = 'error'; 
        console.error("WebSocket error:", event);
      };

      this._socket.onclose = (event) => {
        this.socketConnectionStatus = 'disconnected';
        console.warn("WebSocket closed:", event.code, event.reason);
        this.cleanupSocket();
        this.scheduleReconnect();
      };
    },

    scheduleReconnect() {
      if (this._reconnectTimeout) return;
      this.socketConnectionStatus = 'reconnecting'; 

      const delay = Math.min(1000 * Math.pow(2, this.retryCount), 10000); // exponential backoff
      this._reconnectTimeout = setTimeout(() => {
        this._reconnectTimeout = null;
        this.retryCount++;
        this.connectSocket();
      }, delay);
    },


    disconnectSocket() {
      this.socketConnectionStatus = 'disconnected';
      this.cleanupSocket();
      if (this._reconnectTimeout) {
        clearTimeout(this._reconnectTimeout);
        this._reconnectTimeout = null;
      }
    },

    startPing() {
      this.stopPing();
      this._pingInterval = setInterval(() => {
        this.ping();
        this.checkAlive();
      }, 5000); // every 5s
    },

    stopPing() {
      if (this._pingInterval) {
        clearInterval(this._pingInterval);
        this._pingInterval = null;
      }
    },

    ping() {
      if (this.socketConnected && this._socket) {
        this._socket.send(JSON.stringify({ type: 'ping' }))
      }
    },

    checkAlive() {
      const now = Date.now();
      const timeout = 10000; // 10s without activity
      if (now - this.lastActivity > timeout) {
        console.warn("Socket appears stale, reconnecting...");
        this.cleanupSocket();
        this.scheduleReconnect();
      }
    },

    cleanupSocket() {
      this.stopPing();
      if (this._socket) {
        this._socket.close();
        this._socket = null;
      }
    },


    subscribe(topic: string, filter: Record<string, unknown> = {}) {
      this.subscriptions.add(topic)
      if (this.socketConnected && this._socket) {
        this._socket.send(JSON.stringify({ type: 'subscribe', topic, filter }))
      }
    },

    unsubscribe(topic: string) {
      this.subscriptions.delete(topic)
      this.topics[topic] = []
      if (this.socketConnected && this._socket) {
        this._socket.send(JSON.stringify({ type: 'unsubscribe', topic }))
      }
    },

    clear(topic: string) {
      this.topics[topic] = []
    }
  }
})
