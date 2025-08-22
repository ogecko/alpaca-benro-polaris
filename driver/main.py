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
import discovery
import telescope
import rotator
import stellarium
import app_api
import app_web
import argparse
from pathlib import Path
import os
from polaris import Polaris
from shr import LifecycleController, LifecycleEvent
import signal
polaris: Polaris = None

# ===================================
# MAIN LOOP RESPONSIBLE FOR RETARTS
# ===================================
async def main():
    logger = log.init_logging()
    log.logger = exceptions.logger = discovery.logger = telescope.logger = rotator.logger = shr.logger = logger

    while True:
        lifecycle = LifecycleController()
        def handle_sigint(signum, frame):
            lifecycle.signal_sync(LifecycleEvent.INTERRUPT)
        signal.signal(signal.SIGINT, handle_sigint)
        try:
            await run_all(logger, lifecycle)
        except KeyboardInterrupt:
            logger.info("Keyboard Interrupt received. Exiting.")
            break
        except asyncio.CancelledError:
            logger.info("Main loop cancelled.")
            break
        except Exception as e:
            logger.exception("Fatal error in main loop.")
            break
        else:
            if lifecycle._event == LifecycleEvent.RESTART:
                logger.info("Restarting driver stack...")
                continue
            elif lifecycle._event == LifecycleEvent.INTERRUPT:
                logger.info("SIGINT received. Shutting down.")
                break
            else:
                logger.info("Shutdown requested. Exiting.")
                break

# ===================
# RUN ALL TASKS
# ===================
async def run_all(logger, lifecycle: LifecycleController):
    # Output Alpaca Driver version
    logger.info(f'==STARTUP== ALPACA BENRO POLARIS DRIVER v{shr.DeviceMetadata.Version} =========== ') 

    # Create the Polaris master object and startup each ASCOM device
    global polaris
    polaris = Polaris(logger)
    telescope.start_telescope(polaris, lifecycle)
    rotator.start_rotator(polaris, lifecycle)

    async def wrap(task_coro, name: str = "UnnamedTask"):
        try:
            await task_coro
        except asyncio.CancelledError:
            logger.info(f"[{name}] Task cancelled.")
        except Exception:
            logger.exception(f"[{name}] Unhandled exception.")

    tasks = [
        asyncio.create_task(wrap(polaris.client(logger), name='Polaris')),
        asyncio.create_task(wrap(app_api.alpaca_rest_httpd(logger, lifecycle), name='RestAPI')),
        asyncio.create_task(wrap(app_web.alpaca_pilot_httpd(logger, lifecycle), name='Pilot')),
        asyncio.create_task(wrap(discovery.socket_client(logger, lifecycle), name='Discovery')),
        asyncio.create_task(wrap(stellarium.synscan_api(logger, lifecycle), name='SynscanAPI'))
    ]

    event = await lifecycle.wait_for_event()

    logger.info(f'==SHUTDOWN== Shutting down all tasks...for {event}')
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await polaris.shutdown()


# ==================================================================
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Alpaca Benro Polaris Driver.")

    # Add the arguments
    parser.add_argument('--lat', type=float, help='Site Latitude in decimal degrees')
    parser.add_argument('--lon', type=float, help='Site Longitude in decimal degrees')
    parser.add_argument('--elev', type=float, help='Site Elevation from sea level in meters')
    parser.add_argument('--logdir', type=str, help='Directory to store log file(s)')

    # Parse the arguments
    args = parser.parse_args()

    # Store any of the optional the arguments
    if args.lat:
        Config.site_latitude = args.lat
    if args.lon:
        Config.site_longitude = args.lon
    if args.elev:
        Config.site_elevation = args.elev

    # Set the default log directory if not provided    
    script_dir = Path(__file__).resolve().parent        # Get the path to the current script (main.py)
    default_log_dir = script_dir.parent / 'logs'        # Default log directory: ../logs relative to main.py
    Config.log_dir = Path(args.logdir).resolve() if args.logdir else default_log_dir

    # Ensure the directory exists
    os.makedirs(Config.log_dir, exist_ok=True)

    try:
        asyncio.run(main())
        
    except ValueError as value:
        print(f"{value}\nQuit.")
        asyncio.run(polaris.shutdown())

    except Exception as error:
        print(f"Error {error}, quit.")
        asyncio.run(polaris.shutdown())

    except KeyboardInterrupt:
        print("Keyboard interrupt.")
        asyncio.run(polaris.shutdown())
   




# ==================================================================
