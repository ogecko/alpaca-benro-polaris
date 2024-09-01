# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# main.py - Main Application module
#
# Applications like Stellarium and Nina, can use this Alpaca Polaris Driver to control the Benro Polaris Tripod Head. 
# The Driver proves a REST API based on the ASCOM ITelescopeV3 standard. It manages all comunications with the Benro Polaris over Wifi. 
# The Driver supports features like reat-time position and state updates, slewing to Deep Sky Targets, control of sidereal tracking, and exception handling.
# With applications like Nina you can now use the Benro Polaris with automated focusing, astronomy sky atlas, plate solving, star detection and much more.
#
# Python Compatibility: Requires Python 3.7 or later
# GitHub: https://github.com/ASCOMInitiative/AlpycaDevice
#
# -----------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2024
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
#
import asyncio
import discovery
import exceptions
import shr
import log
from config import Config
from discovery import DiscoveryResponder
import telescope
import app

# ===========
# APP STARTUP
# ===========
async def main():

    logger = log.init_logging()
    # Share this logger throughout
    log.logger = logger
    exceptions.logger = logger
    discovery.logger = logger
    telescope.logger = logger
    shr.logger = logger
    
    # Initialize the ASCOM devices
    telescope.start_polaris(logger)

    # Create a separate thread for ASCOM Discovery
    _DSC = DiscoveryResponder(Config.alpaca_ip_address, Config.alpaca_port)

    tasks = [
            app.alpaca_httpd(logger),
            telescope.polaris.client(logger)
    ]
    await asyncio.gather(*tasks)

    logger.info(f'==SHUTDOWN== Time stamps are UTC.')




# ==================================================================
if __name__ == '__main__':
    asyncio.run(main())
# ==================================================================
