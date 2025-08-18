import axios from 'axios'
import { defineStore, acceptHMRUpdate } from 'pinia';

export const useDeviceStore = defineStore('device', {
  state: () => ({
    alpacaConnected: false,
    alpacaHost: 'localhost',
    alpacaPort: 11111,
    selectedAlpacaDevice: null,
    availableAlpacaDevices: ['Alpaca A', 'Alpaca B', 'Alpaca C'],
  }),
  actions: {
    connectAlpaca() { /* ... */ },
    disconnectAlpaca() { /* ... */ },
    discoverAlpacaDevices() { 
      console.log(window.location.host)
    },
    monitorAlpacaLink() { /* ... */ },
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDeviceStore, import.meta.hot));
}
