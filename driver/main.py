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
        lifecycle = shr.LifecycleController()
        def handle_sigint(signum, frame):
            lifecycle.signal_sync(shr.LifecycleEvent.INTERRUPT)
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
            if lifecycle._event == shr.LifecycleEvent.RESTART:
                logger.info("==MAIN== Restarting driver stack...in 2 sec")
                await asyncio.sleep(2)
                logger.info(f"==MAIN== Restarting now... {[sys.executable] + sys.argv}" )
                log.shutdown_logging()
                try:
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                except Exception as e:
                    logger.exception(f"==MAIN== Fatal error when restarting: {e}")
                continue
            elif lifecycle._event == shr.LifecycleEvent.INTERRUPT:
                logger.info("==MAIN== Interrupt. Exiting.")
                break
            else:
                logger.info("==MAIN== Shutdown requested. Exiting.")
                break

    log.shutdown_logging()



def install_asyncio_exception_handler(lifecycle, logger):
    
    def handle_exception(loop, context):
        message = context.get('message', '')
        exception = context.get('exception', None)
        exc_str = str(exception) if exception else ''
        
        # Suppress known harmless h11 protocol errors on connection close
        if 'can\'t handle event type Response' in exc_str:
            return
        
        # Suppress Windows Proactor pipe/socket errors on abrupt client disconnect.
        # WinError 10054 = ECONNRESET: browser dropped the TCP connection after a
        # redirect or TLS handshake rejection — completely normal, not a driver fault.
        # WinError 10053 = ECONNABORTED: similar aborted connection scenario.
        # WinError 995  = ERROR_OPERATION_ABORTED: I/O cancelled when connection closes.
        if '_ProactorBasePipeTransport' in message or '_ProactorReadPipeTransport' in message:
            return
        if 'WinError 10054' in exc_str or 'WinError 10053' in exc_str or 'WinError 995' in exc_str:
            return
        if 'CLOSED' in exc_str:
            return
            
        # Log everything else as a warning so it goes through our logging system
        logger.warning(f'==ASYNCIO== Unhandled exception: {message} | {exc_str}')
        if exception:
            logger.debug('==ASYNCIO== Exception detail:', exc_info=exception)
    
    lifecycle.loop.set_exception_handler(handle_exception)

# ===================
# RUN ALL TASKS
# ===================
async def run_all(logger, lifecycle: shr.LifecycleController):
    # Output Alpaca Driver version
    logger.info(f'==STARTUP== ALPACA BENRO POLARIS DRIVER v{shr.DeviceMetadata.Version} =========== ') 

    # Start heartbeat event loop watchdog thread and asyncio exception handler
    _start_eventloop_watchdog(lifecycle, logger)
    shr.system_vitals_init(lifecycle)
    install_asyncio_exception_handler(lifecycle, logger)

    # Attach socket publishers BEFORE creating Polaris so no early log lines are missed
    app_socket.attach_publisher_to_logger("log")   # general log
    app_socket.attach_publisher_to_logger("pid")   # pid controller
    app_socket.attach_publisher_to_logger("kf")    # kalman filter
    app_socket.attach_publisher_to_logger("cm")    # calibration manager
    app_socket.attach_publisher_to_logger("sm")    # sync manager
    app_socket.attach_publisher_to_logger("cfg")   # config change manager

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

    logger.info(f'==SHUTDOWN== Shutting down all {len(tasks)} tasks...for {event}')
    await lifecycle.shutdown_tasks()
    await polaris.shutdown()


# ==================================================================

def _start_eventloop_watchdog(lifecycle, logger, heartbeat_sec=0.1, threshold_sec=0.2, monitor_sec=0.3, monitor_delay_sec=1.0):
    """
    Starts a watchdog to detect asyncio event loop stalls.

    Schedules a lightweight heartbeat coroutine inside the event loop that
    timestamps itself every `heartbeat_sec` seconds. A separate daemon thread
    monitors the gap between timestamps from outside the loop; if the gap
    exceeds `threshold_sec` it logs a warning with current system vitals and,
    if Config.log_heartbeat is set, a filtered stack trace of all threads
    (excluding idle workers, blocking receives, and the monitor itself).

    Args:
        lifecycle:          The lifecycle amanager with running asyncio event loop to monitor.
        logger:             Logger instance for warnings and startup confirmation.
        heartbeat_sec:      How often the in-loop heartbeat coroutine ticks (seconds).
                            Default 0.1s.
        threshold_sec:      Lag above which a stall warning is emitted (seconds).
                            Should be greater than heartbeat_sec. Default 0.2s.
        monitor_sec:        How often the watchdog thread checks the heartbeat (seconds).
                            Default 0.3s.
        monitor_delay_sec:  Delay before the watchdog thread begins monitoring, allowing
                            the event loop to reach steady state before the first check.
                            Default 1.0s.

    Notes:
        - The monitor thread is a daemon and will not prevent process exit.
        - Stall warnings are rate-limited to at most one every 2 seconds.
        - Stack traces filter out threads with normal behavious.
    """
    _STACK_FILTERS = [
        '_blocking_recvfrom',           # blocking network socket recv — normal for network threads
        'traceback.format_stack',       # the watchdog's own stack capture — always present, skip
        'work_queue.get',               # thread pool worker waiting for work — idle, not stalled
        '_cpu_sampler_loop',            # thread to get top5 CPU% processes - only run when cpu>95
        'system_cpu_start_probe',       # starting separate thread for top 5 CPU% - can block
        f'logging{os.sep}handlers.py',  # async logging handler thread blocked on empty queue — normal
        f'psutil{os.sep}_pswindows.py', # psutil used in system vitals when problems detected - normal to block
        'windows_events.py',            # Windows IOCP proactor event loop polling — normal on Win
    ]
    last_seen = time.monotonic()

    async def heartbeat():
        nonlocal last_seen
        while True:
            last_seen = time.monotonic()
            await asyncio.sleep(heartbeat_sec)

    async def _start_heartbeat():
        asyncio.create_task(heartbeat(), name='loop_watchdog_heartbeat')
    
    def heatbeat_monitor():
        time.sleep(monitor_delay_sec)
        last_logged = 0
        while not lifecycle.should_shutdown():
            time.sleep(monitor_sec)
            now = time.monotonic()
            lag = now - last_seen
            if lag > threshold_sec and (now - last_logged) > 2.0:
                last_logged = now
                logger.warning(f'->> Heartbeat lag detected:   pulse {lag:.3f}s (expected {heartbeat_sec:.3f}s) {shr.system_vitals()}')
                if Config.log_heartbeat:
                    frames = sys._current_frames()
                    lines = [f'->> Heartbeat Stack Trace:']
                    for tid, frame in frames.items():
                        stack = ''.join(traceback.format_stack(frame))
                        if any(f in stack for f in _STACK_FILTERS) or ('_worker' in stack and 'work_item' not in stack):
                            continue    
                        lines.append(f'  Heartbeat Stack - Thread {tid}:\n{stack}')
                    logger.warning('\n'.join(lines))

            if (shr.system_cpu_report_available()):
                logger.warning(f'->> HIGH CPU LOAD breakdown:  {shr.system_cpu()}')



    # Currently executing outside the loop, please run _start_heatbeat in the asyncio loop
    asyncio.run_coroutine_threadsafe(_start_heartbeat(), lifecycle.loop)
    t = threading.Thread(target=heatbeat_monitor, name='loop_watchdog_monitor', daemon=True)
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
