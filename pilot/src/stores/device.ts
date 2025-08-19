import axios from 'axios'
import { defineStore, acceptHMRUpdate } from 'pinia'
import { HTMLResponseError, NonJSONResponseError, NotFound404Error } from 'src/utils/error'
import type { DescriptionResponse, ConfiguredDevicesResponse } from 'src/utils/interfaces'

export const useDeviceStore = defineStore('device', {
  state: () => ({
    alpacaHost: 'localhost',        // Hostname of Alpaca API
    alpacaPort: 11111,              // Port of Alpaca API
    alpacaConnectingMsg: '',        // Message to show while connecting in progress
    alpacaConnectErrorMsg: '',      // Message to show when there is a connection error
    alpacaConnected: false,         // Indicates whether connection to Alpaca API was successful
    alpacaServerName: '',           // fetched from /management/v1/description
    alpacaServerVersion: '',        // fetched from /management/v1/description
    alpacaDevices: [] as string[],  // fetched from /management/v1/configureddevices
    alpacaServersDiscovered: [] as { name: string; id: string }[],
    alpacaDiscovering: false,
  }),

  actions: {
    setAlpacaDevice(hostname: string, port: number) {
      this.alpacaHost = hostname;
      this.alpacaPort = port;
    },

    async connectAlpaca() {
      this.$patch({
        alpacaConnectingMsg: 'Connecting...',
        alpacaConnectErrorMsg: '',
        alpacaServerName: '',
        alpacaServerVersion: '',
        alpacaDevices: []
      });
      try {
          await this.fetchServerDescription();
          await this.fetchConfiguredDevices();
          this.alpacaConnected = true;
        } catch {
          // alpacaConnectErrorMsg is already set inside apiGet
          this.alpacaConnected = false;
        } finally {
          this.alpacaConnectingMsg = '';
        }
    },

    disconnectAlpaca() {
      this.alpacaConnected = false
    },

    async fetchServerDescription() {
      const response = await this.apiGet<DescriptionResponse>('management/v1/description');
      this.alpacaServerName = response.Value.ServerName;
      this.alpacaServerVersion = response.Value.Version;
    },

    async fetchConfiguredDevices() {
      const response = await this.apiGet<ConfiguredDevicesResponse>('management/v1/configureddevices');
      this.alpacaDevices = response.Value.map( d => (d.DeviceNumber)?`${d.DeviceType}/${d.DeviceNumber}`:`${d.DeviceType}` )
    },

    async apiGet<T>(resourcePath: string, clientID = 0, clientTransactionID = 0): Promise<T> {
      const baseUrl = `http://${this.alpacaHost}:${this.alpacaPort}`;
      const url = `${baseUrl}/${resourcePath}?ClientID=${clientID}&ClientTransactionID=${clientTransactionID}`;
      try {
        const response = await axios.get(url, {
          timeout: 5000,
          responseType: 'json',
          validateStatus: () => true, // allow non-2xx for inspection
        });
        // Handle 404 or other non-success status codes
        if (response.status === 404) {
          throw new NotFound404Error('');
        }
        // Detect HTML fallback (e.g. index.html returned instead of JSON)
        if (typeof response.data === 'string' && response.data.includes('<html')) {
          throw new HTMLResponseError('');
        }
        // Validate basic shape of Alpaca response
        if (typeof response.data !== 'object' || response.data === null) {
          throw new NonJSONResponseError('');
        }
        return response.data as T;

      } catch (error: unknown) {
        if (error instanceof NotFound404Error) {
          this.alpacaConnectErrorMsg = 'API endpoint not found (404).';
        } else if (error instanceof HTMLResponseError) {
          this.alpacaConnectErrorMsg = 'Received HTML fallback — Alpaca API service may not be running.';
        } else if (error instanceof NonJSONResponseError) {
          this.alpacaConnectErrorMsg = 'Received unexpected response format.';
        } else if (axios.isAxiosError(error)) {
          if (error.code === 'ECONNABORTED') {
            this.alpacaConnectErrorMsg = 'Connection request timed out.';
          } else if (error.message?.includes('Network Error')) {
            this.alpacaConnectErrorMsg = 'Network error — hostname may be unreachable.';
          } else if (!error.response) {
            this.alpacaConnectErrorMsg = 'No response — device may be offline or DNS failed.';
          } else {
            this.alpacaConnectErrorMsg = `Unexpected error: ${error.message || 'Unknown failure'}`;
          }
        } else {
          this.alpacaConnectErrorMsg = 'Non-Axios error occurred.';
          console.error('Unexpected error type:', error);
        }
        throw error;
      }

    },

  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDeviceStore, import.meta.hot))
}
