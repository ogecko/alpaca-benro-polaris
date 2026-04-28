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
import app_socket
import threading
import time
import traceback
from pathlib import Path
import os
import sys
from polaris import Polaris
from shr import LifecycleController, LifecycleEvent, system_stats
import signal
polaris: Polaris = None

# ===================================
# MAIN LOOP RESPONSIBLE FOR RETARTS
# ===================================
async def main():
    Config.load()

    if not Config.log_dir:
        # Set the default log directory if not provided    
        script_dir = Path(__file__).resolve().parent             # Get the path to the current script (main.py)
        default_log_dir = str(script_dir.parent / 'logs')        # Default log directory: ../logs relative to main.py
        Config.apply_changes({ "log_dir": default_log_dir })

    # Ensure the directory exists and initialise
    os.makedirs(Config.log_dir, exist_ok=True)
    logger = log.init_logging()
    log.logger = exceptions.logger = discovery.logger = telescope.logger = rotator.logger = shr.logger = logger


    while True:
        # Create a new LifeCycle Controller and install SIGINT handler
        lifecycle = LifecycleController()
        def handle_sigint(signum, frame):
            lifecycle.signal_sync(LifecycleEvent.INTERRUPT)
        signal.signal(signal.SIGINT, handle_sigint)

        # Try running all tasks
        try:
            await run_all(logger, lifecycle)
        except KeyboardInterrupt:
            logger.info("==MAIN== Keyboard Interrupt received. Exiting.")
            break
        except asyncio.CancelledError:
            logger.info("==MAIN== Main loop cancel received. Exiting.")
            break
        except Exception as e:
            logger.exception(f"==MAIN== Fatal error in main loop: {e}")
            break
        else:
            if lifecycle._event == LifecycleEvent.RESTART:
                logger.info("==MAIN== Restarting driver stack...in 2 sec")
                await asyncio.sleep(2)
                logger.info("==MAIN== Restarting now...")
                log.shutdown_logging()
                os.execv(sys.executable, [sys.executable] + sys.argv)
                continue
            elif lifecycle._event == LifecycleEvent.INTERRUPT:
                logger.info("==MAIN== Interrupt. Exiting.")
                break
            else:
                logger.info("==MAIN== Shutdown requested. Exiting.")
                break

    log.shutdown_logging()


# ===================
# RUN ALL TASKS
# ===================
async def run_all(logger, lifecycle: LifecycleController):
    # Output Alpaca Driver version
    logger.info(f'==STARTUP== ALPACA BENRO POLARIS DRIVER v{shr.DeviceMetadata.Version} =========== ') 

    # Start heartbeat event loop watchdog thread
    loop = asyncio.get_running_loop()
    _start_eventloop_watchdog(loop, logger)

    # Create the Polaris master object and startup each ASCOM device
    global polaris
    polaris = Polaris(logger, lifecycle)
    telescope.start_telescope(polaris, lifecycle)
    rotator.start_rotator(polaris, lifecycle)

    tasks = [
        lifecycle.create_task(polaris.client(logger), name='Polaris'),
        lifecycle.create_task(app_api.alpaca_rest_httpd(logger, lifecycle), name='RestAPI'),
        lifecycle.create_task(app_socket.alpaca_socket_httpd(logger, lifecycle, polaris), name='Sockets'),
        lifecycle.create_task(app_web.alpaca_pilot_httpd(logger, lifecycle), name='Pilot'),
        lifecycle.create_task(discovery.socket_client(logger, lifecycle), name='Discovery'),
        lifecycle.create_task(stellarium.synscan_api(logger, lifecycle), name='SynscanAPI')
    ]

    event = await lifecycle.wait_for_event()

    logger.info(f'==SHUTDOWN== Shutting down all tasks...for {event}')
    await lifecycle.shutdown_tasks()
    await polaris.shutdown()


# ==================================================================

def _start_eventloop_watchdog(loop, logger, heartbeat_sec=0.1, threshold_sec=0.2, monitor_sec=0.3, monitor_delay_sec=1.0):

    last_seen = time.monotonic()

    async def heartbeat():
        nonlocal last_seen
        while True:
            last_seen = time.monotonic()
            await asyncio.sleep(heartbeat_sec)

    async def _start_heartbeat():
        asyncio.create_task(heartbeat(), name='loop_watchdog_heartbeat')
    
    def monitor():
        time.sleep(monitor_delay_sec)
        last_logged = 0
        while True:
            time.sleep(monitor_sec)
            now = time.monotonic()
            lag = now - last_seen
            if lag > threshold_sec and (now - last_logged) > 2.0:
                last_logged = now
                logger.warning(f'->> Heartbeat lag detected:   pulse {lag:.3f}s (expected {heartbeat_sec:.3f}s) {system_stats()}')
                if Config.log_heartbeat:
                    frames = sys._current_frames()
                    lines = [f'->> Heartbeat Stack Trace:']
                    for tid, frame in frames.items():
                        stack = ''.join(traceback.format_stack(frame))
                        if ('_worker' in stack and 'work_item' not in stack) or \
                            'work_queue.get' in stack or \
                            'traceback.format_stack' in stack or \
                            '_blocking_recvfrom' in stack:
                            continue
                        lines.append(f'  Thread {tid}:\n{stack}')
                    logger.warning('\n'.join(lines))


    asyncio.run_coroutine_threadsafe(_start_heartbeat(), loop)
    t = threading.Thread(target=monitor, name='loop_watchdog_monitor', daemon=True)
    t.start()
    logger.info('==STARTUP== Heartbeat watchdog thread started.')


# ==================================================================
if __name__ == '__main__':

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
