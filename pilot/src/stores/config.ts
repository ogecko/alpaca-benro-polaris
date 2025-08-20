import { defineStore } from 'pinia'
import { useDeviceStore } from 'stores/device'

const dev = useDeviceStore()

export type ConfigResponse = ReturnType<typeof useConfigStore>['$state']


export const useConfigStore = defineStore('config', {
  state: () => ({
    fetchedAt: 0,       // local timestamp of when config was last fetched

    // Network
    alpaca_ip_address: '',
    alpaca_port: 5555,
    polaris_ip_address: '',
    polaris_port: 9090,
    stellarium_telescope_ip_address: '',
    stellarium_telescope_port: 10001,

    // Site Info
    location: 'Unknown',
    site_latitude: -33.8598874,
    site_longitude: 151.2021771,
    site_elevation: 39,
    site_pressure: 1010,

    // Optics
    focal_length: 800,
    focal_ratio: 11,

    // Advanced Features
    verbose_driver_exceptions: true,
    advanced_control: false,
    advanced_slewing: false,
    advanced_tracking: false,
    advanced_goto: false,
    advanced_rotator: false,
    advanced_guiding: false,

    // Motion
    max_slew_rate: 7,
    max_accel_rate: 1,
    tracking_settle_time: 16,

    // Aiming Adjustment
    aiming_adjustment_enabled: true,
    aiming_adjustment_time: 2,
    aiming_adjustment_az: -0.0300750663,
    aiming_adjustment_alt: 0.0195474932,
    aim_max_error_correction: 0.5,

    // Sync
    sync_pointing_model: 0,
    sync_N_point_alignment: true,

    // Logging
    log_level: 20,
    log_to_file: true,
    log_to_stdout: true,
    log_polaris: true,
    log_performance_data: 0,
    log_performance_data_test: 0,
    log_perf_speed_interval: 5,
    log_polaris_protocol: false,
    log_stellarium_protocol: false,
    supress_polaris_frequent_msgs: true,
    supress_alpaca_polling_msgs: true,
    supress_stellarium_polling_msgs: true,

    // Log Rotation
    max_size_mb: 5,
    num_keep_logs: 5
  }),

  actions: {
    async fetchConfig() {
      try {
        const response = await dev.apiAction<ConfigResponse>('ConfigTOML');
        this.$patch(response)
        this.fetchedAt = Date.now()
      } catch (err) {
        console.warn('Config fetch failed:', err);
      }
    },

    updateConfig(newConfig: Partial<ConfigResponse>) {
      Object.assign(this.$state, newConfig)
    }
  }
})
