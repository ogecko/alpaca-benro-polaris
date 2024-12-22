# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# conf.py - Device configuration file and shared logger construction
# Part of the AlpycaDevice Alpaca skeleton/template device driver
#
# Author:   Robert B. Denny <rdenny@dc3.com> (rbd)
#
# Python Compatibility: Requires Python 3.7 or later
# GitHub: https://github.com/ASCOMInitiative/AlpycaDevice
#
# -----------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2022 Bob Denny
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -----------------------------------------------------------------------------
# Edit History:
# 24-Dec-2022   rbd 0.1 Logging
# 25-Dec-2022   rbd 0.1 More config items, separate logging section
# 27-Dec-2022   rbd 0.1 Move shared logger construction and global
#               var here. MIT license and module header. No mcast.
#
import sys
import toml
import logging

#
# This slimy hack is for Sphinx which, despite the toml.load() being
# run only once on the first import, it can't deal with _dict not being
# initialized or ?!?!?!?!? If you try to use getcwd() in the file name
# here, it will also choke Sphinx. This cost me a day.
#
_dict = {}
_dict = toml.load(f'{sys.path[0]}/config.toml')    # Errors here are fatal.
def get_toml(sect: str, item: str):
    if not _dict is {}:
        return _dict[sect][item]
    else:
        return ''

class Config:
    """Device configuration in ``config.toml``"""
    # ---------------
    # Network Section
    # ---------------
    alpaca_ip_address: str = get_toml('network', 'alpaca_ip_address')
    alpaca_port: int = get_toml('network', 'alpaca_port')
    polaris_ip_address: str = get_toml('network', 'polaris_ip_address')
    polaris_port: int = get_toml('network', 'polaris_port')
    stellarium_telescope_ip_address: int = get_toml('network', 'stellarium_telescope_ip_address')
    stellarium_telescope_port: int = get_toml('network', 'stellarium_telescope_port')
    # --------------
    # Server Section
    # --------------
    location: str = get_toml('server', 'location')
    site_latitude: float = get_toml('server', 'site_latitude')
    site_longitude: float = get_toml('server', 'site_longitude')
    site_elevation: float = get_toml('server', 'site_elevation')
    site_pressure: float = get_toml('server', 'site_pressure')
    focal_length: float = get_toml('server', 'focal_length')
    focal_ratio: float = get_toml('server', 'focal_ratio')
    verbose_driver_exceptions: bool = get_toml('server', 'verbose_driver_exceptions')
    # --------------
    # Device Section
    # --------------
    tracking_settle_time: float = get_toml('device', 'tracking_settle_time')
    aiming_adjustment_enabled: bool = get_toml('device', 'aiming_adjustment_enabled')
    aiming_adjustment_time: float = get_toml('device', 'aiming_adjustment_time')
    aiming_adjustment_az: float = get_toml('device', 'aiming_adjustment_az')
    aiming_adjustment_alt: float = get_toml('device', 'aiming_adjustment_alt')
    aim_max_error_correction: float = get_toml('device', 'aim_max_error_correction')
    sync_pointing_model: int = get_toml('device', 'sync_pointing_model')
    sync_N_point_alignment: int = get_toml('device', 'sync_N_point_alignment')
    # ---------------
    # Logging Section
    # ---------------
    log_dir: str = get_toml('logging', 'log_dir')
    log_level: int = logging.getLevelName(get_toml('logging', 'log_level'))  # Not documented but works (!!!!)
    log_to_file: str = get_toml('logging', 'log_to_file')
    log_to_stdout: str = get_toml('logging', 'log_to_stdout')
    log_polaris: bool = get_toml('logging', 'log_polaris')
    log_performance_data: int = get_toml('logging', 'log_performance_data')
    log_performance_data_test: int = get_toml('logging', 'log_performance_data_test')
    log_perf_speed_interval: int = get_toml('logging', 'log_perf_speed_interval')
    log_polaris_protocol: bool = get_toml('logging', 'log_polaris_protocol')
    log_stellarium_protocol: bool = get_toml('logging', 'log_stellarium_protocol')
    supress_polaris_frequent_msgs: bool = get_toml('logging', 'supress_polaris_frequent_msgs')
    supress_alpaca_polling_msgs: bool = get_toml('logging', 'supress_alpaca_polling_msgs')
    supress_stellarium_polling_msgs: bool = get_toml('logging', 'supress_stellarium_polling_msgs')
    max_size_mb: int = get_toml('logging', 'max_size_mb')
    num_keep_logs: int = get_toml('logging', 'num_keep_logs')
