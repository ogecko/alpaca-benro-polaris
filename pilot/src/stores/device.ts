import axios from 'axios'
import { defineStore, acceptHMRUpdate } from 'pinia'
import { HTMLResponseError, NonJSONResponseError, NotFound404Error, AlpacaResponseError } from 'src/utils/error'
import type { DescriptionResponse, ConfiguredDevicesResponse, SupportedActionsResponse, ActionResponse } from 'src/utils/interfaces'
import { sleep } from 'src/utils/sleep'
import type { ConfigResponse } from 'src/stores/config'

export const useDeviceStore = defineStore('device', {
  state: () => ({
    alpacaHost: '',                 // Hostname of Alpaca Driver
    restAPIPort: 5555,              // Port of Alpaca REST API
    socketAPIPort: 5556,            // Port of Alpaca Socket API
    restAPIConnectingMsg: '',       // Message to show while connecting in progress
    restAPIConnectErrorMsg: '',     // Message to show when there is a connection error
    restAPIConnected: false,        // Indicates whether connection to Alpaca API was successful
    restAPIConnectedAt: 0,          // Timestamp of last successful alpaca connection
    alpacaClientID: 860,            // ClientID of Alpaca Pilot App
    alpacaClientTransactionID: 1000,// ClientTransactionID of Alpaca Pilot App
    alpacaServerName: '',           // fetched from /management/v1/description
    alpacaServerVersion: '',        // fetched from /management/v1/description
    alpacaDevices: [] as string[],  // fetched from /management/v1/configureddevices
    alpacaSupportedActions: [] as string[], // fetched from /api/v1/telescope/0/supportedactions
    alpacaServersDiscovered: [] as { name: string; id: string }[],
    alpacaDiscovering: false,
  }),

  actions: {
    async connectRestAPI() {
      this.$patch({
        restAPIConnectingMsg: 'Connecting...',
        alpacaClientID: 8000+Math.floor(Math.random()*1000),
        restAPIConnectErrorMsg: '',
        alpacaServerName: '',
        alpacaServerVersion: '',
        alpacaDevices: []
      });
      try {
          await sleep(200);  // some time to see connecting message
          await this.fetchServerDescription();
          await this.fetchConfiguredDevices();
          await this.fetchSupportedActions();
          const response = await this.apiAction<ConfigResponse>('Polaris:ConfigFetch', '{"configNames": ["alpaca_socket_port"]}'); 
          this.socketAPIPort = response.alpaca_socket_port || 5556
          this.restAPIConnected = true;
          this.restAPIConnectedAt = Date.now();
          this.restAPIConnectErrorMsg = ''
        } catch {
          // restAPIConnectErrorMsg is already set inside apiGet
          this.restAPIConnected = false;
        } finally {
          this.restAPIConnectingMsg = '';
        }
    },

    disconnectRestAPI() {
      this.restAPIConnected = false
    },

    async fetchServerDescription() {
      const response = await this.api<DescriptionResponse>('management/v1/description');
      this.alpacaServerName = response.Value.ServerName;
      this.alpacaServerVersion = response.Value.Version;
    },

    async fetchConfiguredDevices() {
      const response = await this.api<ConfiguredDevicesResponse>('management/v1/configureddevices');
      this.alpacaDevices = response.Value.map( d => (d.DeviceNumber)?`${d.DeviceType}/${d.DeviceNumber}`:`${d.DeviceType}` )
    },

    async fetchSupportedActions() {
      const response = await this.api<SupportedActionsResponse>('api/v1/telescope/0/supportedactions');
      this.alpacaSupportedActions = response.Value
    },

    async alpacaAbortSlew() {
      return await this.api<SupportedActionsResponse>('api/v1/telescope/0/abortslew',{});
    },
  
    async alpacaTracking(state:boolean) {
      return await this.api<SupportedActionsResponse>('api/v1/telescope/0/tracking',{ Tracking: state });
    },
  
    async alpacaTrackingRate(n:number) {
      return await this.api<SupportedActionsResponse>('api/v1/telescope/0/trackingrate',{ TrackingRate: n });
    },
  
    async alpacaPark() {
      return await this.api<SupportedActionsResponse>('api/v1/telescope/0/park',{});
    },

    async alpacaUnPark() {
      return await this.api<SupportedActionsResponse>('api/v1/telescope/0/unpark',{});
    },

    async alpacaMoveMechanical(roll:number) {
      return await this.api<SupportedActionsResponse>('api/v1/rotator/0/movemechanical',{ Position: roll });
    },

    async alpacaMoveAbsolute(pa:number) {
      return await this.api<SupportedActionsResponse>('api/v1/rotator/0/moveabsolute',{ Position: pa });
    },

    async alpacaMoveAxis(axis:number, rate:number) {
      return await this.api<SupportedActionsResponse>('api/v1/telescope/0/moveaxis',{ Axis: axis, Rate: rate });
    },

    async alpacaSlewToAltAz(alt:number, az:number) {
      return await this.api<SupportedActionsResponse>('api/v1/telescope/0/slewtoaltazasync',{ Altitude: alt, Azimuth: az });
    },

    async alpacaSlewToCoord(ra:number, dec:number) {
      return await this.api<SupportedActionsResponse>('api/v1/telescope/0/slewtocoordinatesasync',{ RightAscension: ra, Declination: dec });
    },

    async setPolarisMode(mode:number) {
      await this.apiAction<void>('Polaris:SetMode', `{"mode": ${mode}}`)
    },

    async setPolarisCompass(compass:number) {
      await this.apiAction<void>('Polaris:SetCompass', `{"compass": ${compass}}`)
    },

    async setPolarisAlignment(az:number, alt:number) {
      await this.apiAction<void>('Polaris:SetAlignment', `{"azimuth": ${az}, "altitude": ${alt}}`)
    },

    async bleSelectDevice(name:string) {
      await this.apiAction<void>('Polaris:bleSelectDevice', `{"name": "${name}"}`)
    },

    async bleEnableWifi() {
      await this.apiAction<void>('Polaris:bleEnableWifi')
    },

    async connectPolaris() {
      await this.apiAction<void>('Polaris:ConnectPolaris')
    },

    async disconnectPolaris() {
      await this.apiAction<void>('Polaris:DisconnectPolaris')
    },

    async apiAction<T>(action: string, parameters: object | string = ' '): Promise<T> {
        const result = await this.api<ActionResponse>('api/v1/telescope/0/action', {
            Action: action,
            Parameters: parameters
        });
        return result.Value as T;
    },

    async api<T>(
      resourcePath: string,
      body?: Record<string, unknown>   // implies a PUT when included, 
    ): Promise<T> {
      this.alpacaClientTransactionID++
      const ClientID = this.alpacaClientID
      const ClientTransactionID = this.alpacaClientTransactionID
      const isPut = body
      const isJSONContent = (isPut && body.Action && body.Action=='Polaris:ConfigUpdate')
      const baseUrl = `http://${this.alpacaHost}:${this.restAPIPort}`;
      const url = isPut ? `${baseUrl}/${resourcePath}` : `${baseUrl}/${resourcePath}?ClientID=${ClientID}&ClientTransactionID=${ClientTransactionID}`;
      const payload = isPut ? { ...body, ClientID, ClientTransactionID } : {}
      const options = {
          timeout: 5000,
          // responseType: 'json',      // node.js only
          validateStatus: () => true,
          headers: { 'Content-Type': isJSONContent ? 'application/json': 'application/x-www-form-urlencoded' },
        }

      try {
        const response = isPut ? await axios.put(url, payload, options) : await axios.get(url, options)

        if (response.status === 404) {
          throw new NotFound404Error('');
        }
        if (typeof response.data === 'string' && response.data.includes('<html')) {
          throw new HTMLResponseError('');
        }
        if (typeof response.data !== 'object' || response.data === null) {
          throw new NonJSONResponseError('');
        }
        if (response.data.ErrorNumber) {
          throw new AlpacaResponseError(response.data.ErrorMessage)
        }

        return response.data as T;

      } catch (error: unknown) {
        if (error instanceof AlpacaResponseError) {
          this.restAPIConnectErrorMsg = error.message;
          console.error(error)
        } else if (error instanceof NotFound404Error) {
          this.restAPIConnectErrorMsg = 'API endpoint not found (404).';
        } else if (error instanceof HTMLResponseError) {
          this.restAPIConnectErrorMsg = 'Received HTML fallback — Alpaca API service may not be running.';
        } else if (error instanceof NonJSONResponseError) {
          this.restAPIConnectErrorMsg = 'Received unexpected response format.';
        } else if (axios.isAxiosError(error)) {
          if (error.code === 'ECONNABORTED') {
            this.restAPIConnectErrorMsg = 'Connection request timed out.';
            this.restAPIConnected = false
          } else if (error.message?.includes('Network Error')) {
            this.restAPIConnectErrorMsg = 'Network error — hostname may be unreachable.';
          } else if (!error.response) {
            this.restAPIConnectErrorMsg = 'No response — device may be offline or DNS failed.';
          } else {
            this.restAPIConnectErrorMsg = `Unexpected error: ${error.message || 'Unknown failure'}`;
          }
        } else {
          this.restAPIConnectErrorMsg = 'Non-Axios error occurred.';
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
