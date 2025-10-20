import { defineStore } from 'pinia'
import { useDeviceStore } from 'stores/device'

const dev = useDeviceStore()

export type ConfigResponse = ReturnType<typeof useConfigStore>['$state']


export const useConfigStore = defineStore('config', {
  state: () => ({
    fetchedAt: 0,             // local timestamp of when config was last fetched
    isSaving: false,          // saving overrides to Driver
    isRestoring: false,       // restoring config from config.toml
    isRestartRequired: false, // network services keys have changed

    // Network
    polaris_auto_retry: true,
    polaris_ip_address: '',
    polaris_port: 9090,
    enable_restapi: true,
    enable_socket: true,
    enable_discovery: true,
    enable_pilot: true,
    enable_synscan: true,
    alpaca_restapi_port: 5555,
    alpaca_socket_port: 5556,
    alpaca_discovery_port: 32227,
    alpaca_pilot_port: 80,
    stellarium_synscan_port: 10001,
    stellarium_synscan_ip_address: '',
    alpaca_restapi_ip_address: '',

    // Site Info
    location: 'Unknown',
    site_latitude: -33.8598874,
    site_longitude: 151.2021771,
    site_elevation: 39,
    site_pressure: 1010,
    default_azimuth: '180',
    default_altitude: '45',

    // Optics
    focal_length: 800,
    focal_ratio: 11,

    // Advanced Features
    verbose_driver_exceptions: true,
    advanced_kf: false,
    advanced_control: false,
    advanced_slewing: false,
    advanced_tracking: false,
    advanced_goto: false,
    advanced_rotator: false,
    advanced_guiding: false,
    advanced_alignment: false,

    // Motion
    max_slew_rate: 0.0,
    max_accel_rate: 0.0,
    tracking_settle_time: 16,
    kf_process_noise: [1e-5, 1e-5, 1e-5, 1e-4, 1e-4, 1e-4], 
    kf_measure_noise: [1e-5, 1e-5, 1e-5, 1e-4, 1e-4, 1e-4], 
    z1_min_limit: -190,
    z1_max_limit: +190,
    z2_min_limit: -32,
    z2_max_limit: +40,
    z3_min_limit: -190,
    z3_max_limit: +190,
    m1_park: 0,
    m2_park: 0,
    m3_park: 0,


    // Aiming Adjustment
    aiming_adjustment_enabled: true,
    aiming_adjustment_time: 2,
    aiming_adjustment_az: -0.0300750663,
    aiming_adjustment_alt: 0.0195474932,
    aim_max_error_correction: 0.5,

    // Logging
    log_level: 'INFO',
    log_to_file: true,
    log_to_stdout: true,

    log_performance_data: 0,
    log_performance_data_test: 0,
    log_perf_speed_interval: 5,
    
    log_polaris: true,
    log_stellarium_protocol: false,
    supress_polaris_frequent_msgs: true,
    supress_alpaca_polling_msgs: true,
    supress_stellarium_polling_msgs: true,

    log_alpaca_protocol: false,
    log_alpaca_polling: false, 
    log_alpaca_discovery: false, 
    log_alpaca_actions: false, 
    log_pulse_guiding: false,   
    log_rotator_protocol: false, 
    log_synscan_protocol: false,
    log_synscan_polling: false,
    log_polaris_ble: false,
    log_polaris_protocol: false,
    log_polaris_polling: false,
    
    log_telemetry_data: false,
    log_aiming_data: false,
    log_drift_data: false,
    log_periodic_data: false,
    log_kalman_data: false,
    log_pid_data: false,
    log_sync_data: false,

    // Log Rotation
    max_size_mb: 5,
    num_keep_logs: 5
  }),

  actions: {
    async configFetch(configNames:string[]=[]) {
      try {
        const names = configNames.map(d=>`"${d}"`).join(',')
        const payload = `{"configNames": [${names}]}`
        const response = await dev.apiAction<ConfigResponse>('Polaris:ConfigFetch', payload);
        this.$patch(response)
        this.fetchedAt = Date.now()
      } catch (err) {
        console.warn('Config fetch failed:', err);
      }
    },

    async configUpdate(payload: Partial<ConfigResponse>) {
      try {
        const updated = await dev.apiAction<ConfigResponse>('Polaris:ConfigUpdate', payload)
        this.$patch(updated)
        console.log('configUpdate',updated)
        // Check if we need to refetch configured devices
        if (
          Object.prototype.hasOwnProperty.call(updated, 'advanced_control') ||
          Object.prototype.hasOwnProperty.call(updated, 'advanced_rotator')
        ) {
          await dev.fetchConfiguredDevices()
        }
        // Check if any updated key requires restart
        const restartKeys = [
          'polaris_auto_retry', 'enable_restapi', 'enable_socket', 'enable_discovery', 'enable_pilot', 'enable_synscan', 
          'alpaca_restapi_port', 'alpaca_socket_port', 'alpaca_discovery_port', 'alpaca_pilot_port', 'stellarium_synscan_port', 
        ]
        const updatedKeys = Object.keys(updated)
        const requiresRestart = updatedKeys.some(key => restartKeys.includes(key))
        if (requiresRestart) {
          this.isRestartRequired = true
          console.info(`ABP Driver Restart required due to: ${updatedKeys.join(', ')}`)
        }
      } catch (err) {
        const keys = Object.keys(payload).join(', ')
        console.warn(`Failed to update ${keys}:`, err)
      }
    },
    async configSave() {
      this.isSaving = true
      try {
        await dev.apiAction<ConfigResponse>('Polaris:ConfigSave')
        if (this.isRestartRequired) {
          this.isRestartRequired = false
          await dev.apiAction<string>('Polaris:RestartDriver')
        }
        return true
      } catch (err) {
        console.warn('Config Save failed:', err);
        return false
      } finally {
        this.isSaving = false
      }
    },
    async configRestore() {
      this.isRestoring = true
      try {
        const response = await dev.apiAction<ConfigResponse>('Polaris:ConfigRestore');
        this.$patch(response)
        this.fetchedAt = Date.now()
        return true
      } catch (err) {
        console.warn('Config restore failed:', err);
        return false
      } finally {
        this.isRestoring = false
      }
    },


  }
})
