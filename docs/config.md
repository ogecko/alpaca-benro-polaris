# Configuration Reference
[Network](#network) · [Site and Equipment](#site-and-equipment) · [Panorama](#panorama) · [Control](#control) · [Models](#models) · [Aiming](#aiming) · [Logging](#logging)

This page lists every setting of the Alpaca Driver, with its default value. It is generated from the driver's configuration file, `driver/config.toml`, by `utility/docs/make_config_reference.py`: change the file's comments rather than this page.

**Where settings live.** `driver/config.toml` holds the default for each setting, and is replaced when the driver is updated, so don't edit it to change a setting. Instead, change settings in Alpaca Pilot: most are on its Settings page, and some on its PID Tuning, Kalman, Panorama and Dashboard pages. Alpaca Pilot saves the settings you have changed to `data/config.pilot.json`, which the driver applies on top of the defaults each time it starts. Restoring the defaults deletes that file.

**Changing settings from a script.** The `Polaris:ConfigFetch`, `Polaris:ConfigUpdate`, `Polaris:ConfigSave` and `Polaris:ConfigRestore` Device Actions read, change, save and restore settings (see the [Alpaca API Reference](./alpaca-api.md#device-actions)). A change takes effect straight away, except for the settings marked **Restart** below, which need a driver restart.

## Network

How the driver connects to the Benro Polaris, and the services it provides to applications.

These settings are in the `[network]` section of `config.toml`.

| Setting | Default | Restart | Description |
|---|---|---|---|
| `polaris_auto_retry` | `true` | Yes | If the connection to the Polaris fails: true = keep retrying, false = wait for Alpaca Pilot to reconnect. |
| `enable_remote_shutdown` | `true` |  | Allow Alpaca Pilot to shut down the computer the driver runs on (Polaris:ShutdownOS). |
| `polaris_ip_address` | `'192.168.0.1'` |  | IP address of the Benro Polaris on its Wi-Fi hotspot. |
| `polaris_port` | `9090` |  | Port the Benro Polaris listens on. |
| `polaris_wifi_password` | `''` |  | WPA2 password for the Polaris hotspot, used when the driver joins it (Windows only). Leave blank: the hotspot is open. |
| `enable_restapi` | `true` | Yes | Provide the Alpaca REST API service (required, don't turn off). |
| `enable_socket` | `true` | Yes | Provide the Alpaca Pilot WebSocket service. |
| `enable_discovery` | `true` | Yes | Provide the Alpaca discovery service, so applications can find the driver. |
| `enable_mdns` | `true` | Yes | Advertise Alpaca Pilot on the local network over mDNS, as http://<mdns_name>. |
| `mdns_name` | `'ap.local'` | Yes | Name advertised over mDNS (always ends in .local). |
| `enable_pilot` | `true` | Yes | Provide the Alpaca Pilot web server. |
| `enable_synscan` | `true` | Yes | Provide the SynScan service, for Stellarium and SkySafari. |
| `enable_rest_https` | `false` |  | Serve the Alpaca REST API over HTTPS (NINA then needs Options > Equipment > ASCOM Alpaca Discovery > Use HTTPS). |
| `enable_https` | `false` | Yes | Serve Alpaca Pilot and its WebSocket over HTTPS/WSS, with a self-signed certificate. |
| `alpaca_pilot_https_port` | `443` | Yes | Alpaca Pilot's HTTPS port, used when enable_https is true. |
| `alpaca_pilot_http_port` | `80` | Yes | Alpaca Pilot's HTTP port, used when enable_https is false. |
| `alpaca_restapi_port` | `5555` | Yes | Port for the Alpaca REST API. |
| `alpaca_socket_port` | `5556` | Yes | Port for the Alpaca Pilot WebSocket. |
| `alpaca_discovery_port` | `32227` | Yes | UDP port for Alpaca discovery. |
| `stellarium_synscan_port` | `10001` | Yes | Port for the SynScan service (Stellarium, SkySafari). |
| `stellarium_synscan_ip_address` | `''` |  | IP address the SynScan service listens on: `''` = all addresses, `'127.0.0.1'` = this computer only. |
| `alpaca_restapi_ip_address` | `''` |  | IP address the Alpaca REST API listens on: `''` = all addresses, `'127.0.0.1'` = this computer only. |
| `preset_action` | `''` |  | Set by Alpaca Pilot to act on a preset: `'<verb>_<type>'`, with verb save, load or delete, and type loc or pano. Resets to `''`. |
| `preset_name` | `''` |  | Name of the preset to act on. |

## Site and Equipment

Your observing site, GPS receiver, and lens or telescope.

These settings are in the `[server]` section of `config.toml`.

| Setting | Default | Restart | Description |
|---|---|---|---|
| `location_source` | `'browser'` |  | Where Alpaca Pilot's Locate gets your position: `'browser'` (the browser's location services) or `'gps'` (a GPS receiver). |
| `gps_provider` | `'nmea'` |  | GPS receiver protocol: `'nmea'` (serial or USB, all platforms), `'gpsd'` (Linux) or `'ubx'` (serial). |
| `gpsd_host` | `'127.0.0.1'` |  | GPSD server hostname or IP address. |
| `gpsd_port` | `2947` |  | GPSD server TCP port. |
| `gps_serial_device` | `''` |  | GPS serial port (for example COM9 or /dev/ttyACM0), chosen in Alpaca Pilot's GPS Receiver settings. |
| `gps_serial_baudrate` | `9600` |  | GPS serial baud rate. |
| `gps_max_attempts` | `5` |  | Maximum GPS polls (1-20); three agreeing fixes are needed. |
| `gps_retry_max_delay` | `15.0` |  | Longest wait between GPS polls (seconds); the wait doubles every two attempts. |
| `location_list` | `''` |  | Saved location names, sorted and separated by \|, for Alpaca Pilot's locations list. |
| `location` | Set in Alpaca Pilot |  | Name of your observing site (any text). |
| `site_latitude` | Set in Alpaca Pilot |  | Site latitude (degrees, positive north, WGS84). |
| `site_longitude` | Set in Alpaca Pilot |  | Site longitude (degrees, positive east, WGS84). |
| `site_elevation` | Set in Alpaca Pilot |  | Site elevation above mean sea level (metres). |
| `site_pressure` | `1010` |  | Atmospheric pressure (millibars), for the refraction correction. 1010 is the standard atmosphere; 0 turns the correction off. |
| `focal_length` | `800` |  | Focal length of your lens or telescope (mm). |
| `focal_ratio` | `11.0` |  | Focal ratio of your lens or telescope (focal length / aperture). |
| `verbose_driver_exceptions` | `true` |  | Give more detail when the driver reports an error. |
| `default_azimuth` | `'180'` |  | Default azimuth for Alpaca Pilot's Compass and Single Star Alignment, as text: decimal degrees (`'180'`) or `deg:mm:ss` (`'180:30:00'`). |
| `default_altitude` | `'45'` |  | Default altitude for Alpaca Pilot's Single Star Alignment, as text: decimal degrees (`'45'`) or `deg:mm:ss` (`'45:30:00'`). |

## Panorama

The Panorama Grid and the Panel Spacing Calculator. Alpaca Pilot sets most of these from its Panorama pages (see [Creating Panoramas](./panoramas.md)).

These settings are in the `[panorama]` section of `config.toml`.

| Setting | Default | Restart | Description |
|---|---|---|---|
| `pano_list` | `''` |  | Saved panorama names, sorted and separated by \|, for Alpaca Pilot's panoramas list. |
| `pano_name` | `''` |  | Name of the panorama defined below. |
| `sensor_size` | `'Full Frame (36 × 24 mm)'` |  | Camera sensor size, used only by the Panel Spacing Calculator. |
| `panel_overlap` | `'30%'` |  | Overlap between adjacent panels, used only by the Panel Spacing Calculator. |
| `show_panels` | `false` |  | Show the Panorama Grid's panel navigation on the Dashboard. |
| `cols` | `3` |  | Number of panels across the mosaic (2-14). |
| `rows` | `1` |  | Number of panels down the mosaic (1-3). |
| `hstep` | `40.0` |  | Horizontal distance between panel centres (degrees). |
| `vstep` | `25.0` |  | Vertical distance between panel centres (degrees). |
| `first` | `0` |  | Which corner is panel 1: 0 = top left, 1 = top right, 2 = bottom left, 3 = bottom right. |
| `order` | `0` |  | Order the panels are captured in: 0 = row by row, 1 = column by column, 2 = serpentine. |
| `track` | `0` |  | Roll and tracking after moving to each panel: 0 = landscape, untracked; 1 = sky, horizon-locked; 2 = sky, celestial; 3 = sky, Milky Way. |
| `anchor` | `0` |  | Which part of the mosaic sits at the reference position: 0 = mosaic centre, n = panel n. |
| `ref_action` | `''` |  | Set to `'update'` to make the mount's current position the reference position. Resets to `''`. |
| `ref` | `0` |  | Reference frame: 0 = Az/Alt/Roll, 1 = RA/Dec/PA, 2 = galactic l/b/GPA, 3 = M1/M2/M3 motor position. |
| `r1` | `90.0` |  | Reference position, first axis (Azimuth, RA, galactic longitude or M1). |
| `r2` | `5.0` |  | Reference position, second axis (Altitude, Dec, galactic latitude or M2). |
| `r3` | `0.0` |  | Reference position, third axis (Roll, PA, galactic PA or M3). |
| `panel` | `3` |  | Current panel: 0 = mosaic centre, n = panel n. |

## Control

The driver's motion control: alignment, tracking, guiding, Periodic Error Correction, the Kalman filter, the PID controller and the motor limits. See the [Control Reference](./control.md) and [Kinematics Reference](./kinematics.md) for how they work.

These settings are in the `[control]` section of `config.toml`.

| Setting | Default | Restart | Description |
|---|---|---|---|
| `advanced_control` | `true` |  | Turn on the driver's advanced control. Must be true for any of the advanced features below. |
| `advanced_kf` | `true` |  | Smooth the Polaris's position measurements with a Kalman filter. |
| `advanced_rotator` | `true` |  | Provide the ASCOM Alpaca Rotator, for framing by rotation (needs advanced_tracking). |
| `advanced_slewing` | `true` |  | The driver controls move-axis (jog) commands, instead of the Polaris. |
| `advanced_goto` | `true` |  | The driver controls gotos, instead of the Polaris. |
| `advanced_tracking` | `true` |  | The driver controls tracking, instead of the Polaris. |
| `advanced_pulse_guiding` | `true` |  | Accept ASCOM Alpaca pulse guiding, from applications such as PHD2 (needs advanced_tracking). |
| `advanced_pulse_pec_tuning` | `true` |  | Use pulse guiding corrections to tune the PEC model. |
| `pec_ignore_guider_calibration` | `true` |  | PEC ignores a guider's calibration (PHD2, CCDciel), recognised as 3 or more single-axis pulses, each the same as or 1.5x the last. |
| `advanced_sync_guiding` | `true` |  | Sync Guiding: treat a plate-solve sync without a slew as a guiding correction (needs advanced_tracking). |
| `advanced_alignment` | `true` |  | Use the Multi-Point Alignment (QUEST) model, instead of the Polaris's Single Point Alignment. |
| `advanced_scc_enabled` | `true` |  | Slew and Center Correction: reduce the number of Slew and Center cycles, using the method set by advanced_scc_choice. |
| `advanced_scc_choice` | `2` |  | Slew and Center Correction method: 0 = zero last residual, 1 = local Gaussian adjustment, 2 = sync guiding adjustment. |
| `advanced_align_mac` | `true` |  | Mechanical Alignment Correction: fit the M2/M3 offsets (and the M2 scale) with the alignment (false = rotation-only QUEST). |
| `advanced_eq_mode` | `false` |  | Beta, experimental: for a Polaris on an equatorial wedge, with the M1 axis aligned to the celestial pole. |
| `advanced_eq_mode_visible` | `false` |  | Beta, experimental: show the Equatorial Mode switch in Alpaca Pilot's settings. |
| `advanced_orbitals` | `true` |  | Track orbitals (the Sun, Moon, planets, satellites and comets) at their own, non-sidereal rates. |
| `orbital_lead_sec` | `0.3` |  | Aim this far ahead of an orbital (seconds), to make up for the control loop's delay (0.2-0.4 s). |
| `advanced_pec_drift` | `true` |  | PEC Drift Correction: learn the slow drift from guiding corrections and correct it. |
| `advanced_pec_worm` | `true` |  | PEC Worm Gear Correction: correct each motor's worm gear error, using data/worm_profile.json. |
| `coordinated_speed_control` | `true` |  | Coordinated speed control: shared motor speed control, planned gotos, acceleration-shaped jogs, and no PID integral build-up during gotos. |
| `advanced_backlash` | `true` |  | Backlash Compensation: take up the gear slack as a goto finishes (needs coordinated_speed_control; not applied to tracking reversals). |
| `backlash_deg` | `[0.04, 0.12, 0.08]` |  | Each motor's gear backlash (degrees, M1/M2/M3); worm profile tests measured about 125-160", 280-620" and 310". |
| `restore_tracking_on_restart` | `true` |  | After a driver restart, resume the tracking it was doing, if it was saved less than 10 minutes ago. |
| `pec_tau_sec` | `450` |  | Smoothing time constant of PEC's drift rate estimate (seconds): 450 = 7.5 minutes. |
| `pec_reversal_pause` | `true` |  | PEC pauses learning while a motor reverses its tracking direction (even with Backlash Compensation on). |
| `pec_reversal_lead_sec` | `120` |  | The PEC pause starts this long before the motor's turning point (seconds), as its gear unloads while it slows. |
| `pec_reversal_backlash_deg` | `0.2` |  | The PEC pause ends once the motor has turned this far past its turning point (degrees; backlash measured at 150-620"). |
| `kf_measure_noise` | `[0.00316, 0.00631, 0.0158, 0.00158, 0.00316, 0.255]` |  | Kalman filter measurement noise: position M1/M2/M3, then velocity M1/M2/M3. |
| `kf_goto_noise_scale` | `0.1` |  | During a goto or rotate, the Kalman filter's position measurement noise is multiplied by this (tracking keeps kf_measure_noise). |
| `kf_process_noise` | `[5.01e-05, 7.94e-05, 0.000126, 0.0001, 0.0001, 0.0001]` |  | Kalman filter process noise: position M1/M2/M3, then velocity M1/M2/M3. |
| `measurement_dt` | `0.2` |  | Interval between the Polaris's position (518) messages, fixed by its hardware (seconds). |
| `measurement_catchup_max_dt` | `2.0` |  | Longest gap between position (518) messages before it's treated as an outage (seconds). |
| `pid_Kp` | `[1, 1, 1]` |  | PID proportional gain, M1/M2/M3: more control in proportion to the position error. |
| `pid_Ki` | `[0.07, 0.07, 0.07]` |  | PID integral gain, M1/M2/M3: more control while an error persists. |
| `pid_Kd` | `[0.5, 0.5, 0.8]` |  | PID derivative gain, M1/M2/M3: damping, with less control when moving fast. |
| `pid_Ke` | `0.4` |  | PID output smoothing (0 = none, 0.4 = mix in 40% of the previous output). |
| `pid_Kc` | `0.75` |  | PID tolerance treated as on target (arc minutes). |
| `pid_Ka` | `0.0` |  | PID maximum acceleration on any motor (0.5-5.0 deg/s²; 0.0 = the default of 5). Must be a decimal. |
| `pid_Kv` | `0.0` |  | PID maximum slew rate on any motor (0.0-8.5 deg/s; 0.0 = the calibrated maximum). Must be a decimal. |
| `pid_Kt` | `0.2` |  | PID dead time (seconds): how late measurements show a motor's response. |
| `pid_Kl` | `0.15` |  | PID motor lag (seconds): the time constant with which a motor eases to a new speed. Goto plans allow for both (0.2-0.4 s in all on the mount). |
| `zeta_safety_margin` | `10` |  | Safety margin inside the motor limits below, to prevent cable wind-up (degrees). |
| `z1_min_limit` | `-270` |  | M1 motor limit, minimum (degrees). |
| `z1_max_limit` | `270` |  | M1 motor limit, maximum (degrees). |
| `z2_min_limit` | `-55` |  | M2 motor limit, minimum (degrees). |
| `z2_max_limit` | `37` |  | M2 motor limit, maximum (degrees). |
| `z3_min_limit` | `-270` |  | M3 motor limit, minimum (degrees). |
| `z3_max_limit` | `270` |  | M3 motor limit, maximum (degrees). |
| `m1_park` | `0.0` |  | M1 motor angle of the saved park position (degrees). |
| `m2_park` | `0.0` |  | M2 motor angle of the saved park position (degrees). |
| `m3_park` | `0.0` |  | M3 motor angle of the saved park position (degrees). |
| `guide_rate_ra` | `1.0` |  | Right Ascension guide rate, as a multiple of the sidereal rate. |
| `guide_rate_dec` | `1.0` |  | Declination guide rate, as a multiple of the sidereal rate. |

## Models

Alignment model (Mechanical Alignment Correction, advanced_align_mac): the M2/M3 zero offsets are fitted at every sync; the M2 scale (+0.3-2.2% on every Polaris measured) starts here and is refitted at each sync when significantly better.

These settings are in the `[models]` section of `config.toml`.

| Setting | Default | Restart | Description |
|---|---|---|---|
| `align_m2_scale` | `1.0` |  | Starting M2 scale (%): M2 turns this much further than its reported angle (at about 45°). |

## Aiming

Small aiming adjustments.

These settings are in the `[device]` section of `config.toml`.

| Setting | Default | Restart | Description |
|---|---|---|---|
| `tracking_settle_time` | `16` |  | Time to wait after sidereal tracking restarts, before a slew is reported complete (seconds). |
| `aiming_adjustment_enabled` | `false` |  | Make small adjustments to improve aiming. |
| `aiming_adjustment_time` | `2` |  | How far ahead to convert RA/Dec to Az/Alt, allowing for tracking to settle (seconds). |
| `aim_max_error_correction` | `0.5` |  | Largest aiming error the driver corrects when aiming at Az/Alt (degrees). |
| `aiming_adjustment_az` | `-0.0300750663` |  | Starting azimuth aiming adjustment (degrees); set to 0 for none. |
| `aiming_adjustment_alt` | `0.0195474932` |  | Starting altitude aiming adjustment (degrees); set to 0 for none. |

## Logging

What the driver writes to its log. Most switches are for diagnosing problems, and can be left as they are.

These settings are in the `[logging]` section of `config.toml`.

| Setting | Default | Restart | Description |
|---|---|---|---|
| `log_dir` | `''` |  | Folder for log files (`''` = the logs folder next to the driver). |
| `log_level` | `'INFO'` |  | Lowest level of message to log, for example `'INFO'`. |
| `log_to_file` | `true` |  | Write the log to alpaca.log, keeping older logs as alpaca.1, alpaca.2 and so on (see num_keep_logs). |
| `log_to_stdout` | `true` |  | Also write the log to the console. |
| `log_alpaca_protocol` | `true` |  | Log ASCOM Alpaca Telescope messages sent and received. |
| `log_rotator_protocol` | `true` |  | Log ASCOM Alpaca Rotator messages sent and received. |
| `log_alpaca_discovery` | `false` |  | Log Alpaca discovery and management messages, and WebSocket subscribe, unsubscribe and timeout activity. |
| `log_synscan_protocol` | `true` |  | Log Stellarium SynScan and binary protocol messages sent and received. |
| `log_alpaca_actions` | `true` |  | Log Alpaca Device Actions (frequently polled actions, such as Polaris:ConfigFetch, follow log_alpaca_polling instead). |
| `log_polaris_ble` | `false` |  | Log Benro Polaris Bluetooth Low Energy messages sent and received. |
| `log_polaris_protocol` | `false` |  | Log Benro Polaris protocol messages sent and received. |
| `log_pulse_guiding` | `false` |  | Log ASCOM Alpaca pulse guiding messages. |
| `log_alpaca_polling` | `false` |  | Log frequent polling from Alpaca applications (for example NINA). |
| `log_synscan_polling` | `false` |  | Log frequent polling from SynScan applications (for example Stellarium). |
| `log_polaris_polling` | `false` |  | Log frequent polling of the Benro Polaris. |
| `log_quest_model` | `true` |  | Log the Multi-Point Alignment (QUEST) model's sync point weights. |
| `log_orbital_queries` | `true` |  | Log JPL Horizons and CelesTrak orbit queries. |
| `log_gps_receiver` | `false` |  | Log what the GPS receiver sends (NMEA, UBX, GPSD), and each Locate attempt's fix. |
| `log_pec` | `true` |  | Log Periodic Error Correction. |
| `log_heartbeat` | `false` |  | Log a stack trace whenever a heartbeat is skipped, and garbage collections over 100 ms. |
| `log_position` | `false` |  | Log full Kalman filter (KFLOG) and PID (PIDLOG) telemetry every control tick (about 200 ms while tracking). |
| `log_hardware_unit_tests` | `false` |  | Allow unit tests that send real commands to the Polaris (they move the mount). |
| `max_size_mb` | `20` |  | Maximum log file size (MB). |
| `num_keep_logs` | `20` |  | Number of old log files to keep. |
