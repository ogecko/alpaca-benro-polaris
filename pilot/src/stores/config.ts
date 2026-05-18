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
    enable_https: false,
    alpaca_pilot_http_port: 80,
    alpaca_pilot_https_port: 433,
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

    // Panorama
    sensor_size: 'Full Frame (36 × 24 mm)',
    panel_overlap: '30%',
    show_panels: false,
    cols: 3,
    rows: 1,
    hstep: 40,
    vstep: 25,
    first: 0,
    order: 0,
    track: 0,
    anchor: 0,
    ref: 0,
    r1: 90,
    r2: 5,
    r3: 0,
    panel: 0,

    // Advanced Features
    verbose_driver_exceptions: true,
    advanced_kf: false,
    advanced_control: false,
    advanced_slewing: false,
    advanced_tracking: false,
    advanced_goto: false,
    advanced_rotator: false,
    advanced_pulse_guiding: false,
    advanced_sync_guiding: false,
    advanced_alignment: false,
    advanced_scc_enabled: false,
    advanced_scc_choice: 2,
    advanced_align_mac: false,
    advanced_orbitals: false,
    advanced_pec: false,
    // Motion and Tuning Constants
    tracking_settle_time: 16,
    kf_process_noise: [1e-5, 1e-5, 1e-5, 1e-4, 1e-4, 1e-4],
    kf_measure_noise: [1e-5, 1e-5, 1e-5, 1e-4, 1e-4, 1e-4],
    pid_Kp: [0.8, 0.8, 0.8],
    pid_Ki: [0.0, 0.0, 0.0],
    pid_Kd: [0.8, 0.8, 0.8],
    pid_Ke: 0.4,
    pid_Kc: 1.0,
    pid_Kv: 0.0,
    pid_Ka: 0.0,

    z1_min_limit: -190,
    z1_max_limit: +190,
    z2_min_limit: -32,
    z2_max_limit: +40,
    z3_min_limit: -190,
    z3_max_limit: +190,
    m1_park: 0,
    m2_park: 0,
    m3_park: 0,
    guide_rate_ra: 0.5,
    guide_rate_dec: 0.5,

    // Mechanical Correction Models
    m1_offset: 0.0,
    m2_offset: 0.0,
    m3_offset: 0.0,
    m3_tilt_dm2: 0.0,
    m3_tilt_dm1: 0.0,
    m2_tilt_dm2_amp: 0.0,
    m2_tilt_dm2_zero: 0.0,
    m2_roll_coupling: 0.0,
    m2_roll_zero: 0.0,
    m3_encoder_scale: 0.0,

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
    log_quest_model: false,
    log_orbital_queries: false,
    log_pec: false,
    log_heartbeat: false,

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
          'alpaca_restapi_port', 'alpaca_socket_port', 'alpaca_discovery_port', 'enable_https', 'alpaca_pilot_http_port', 'alpaca_pilot_https_port', 'stellarium_synscan_port',
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
