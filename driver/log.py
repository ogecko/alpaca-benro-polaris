import logging
import logging.handlers
import queue
import time
import sys
from config import Config
import os

# At the module level, no need for - global logger
logger = None

_log_queue_listener: logging.handlers.QueueListener = None  # keep reference for shutdown
_blocking_handlers: list = []  # stdout/file handlers owned by the queue listener -- closed in shutdown_logging()


class _SuppressBenignUvicornShutdown(logging.Filter):
    """
    uvicorn's Server.shutdown() logs "Cancel %s running task(s), timeout graceful
    shutdown exceeded" whenever its bounded timeout_graceful_shutdown elapses --
    including the common, harmless case where the count is 0 (all connections had
    already finished by the time the timeout's polling loop noticed). That's an
    expected side effect of bounding the shutdown wait, not a real problem, so it's
    suppressed here. A count > 0 (something genuinely had to be force-cancelled)
    still logs normally.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == 'uvicorn.error' and record.msg == 'Cancel %s running task(s), timeout graceful shutdown exceeded':
            count = record.args[0] if record.args else None
            return count != 0
        return True


class _SuppressBenignZeroconfSocketError(logging.Filter):
    """
    zeroconf's DatagramProtocol.error_received() (zeroconf/_listener.py) logs
    "Error with socket ...): [WinError 59] An unexpected network error occurred"
    whenever a per-interface mDNS socket's underlying network interface changes
    state -- a WiFi disconnect/reconnect, a new adapter (eg. a VPN) appearing,
    etc. zeroconf's own docstring for this callback says "Likely socket closed
    or IPv6", ie. an anticipated condition, not a crash -- the exception never
    propagates out of zeroconf, so there's nothing for driver code to catch or
    retry. Suppressed here the same way as _SuppressBenignUvicornShutdown above,
    scoped narrowly to this exact WinError so any other, less expected zeroconf
    socket error (the "or IPv6" half of that docstring, or anything else) still
    logs normally.

    Same story on macOS, different errno: on the very first run, until the
    user answers the OS's "allow app to find devices on local networks?"
    prompt, outbound multicast sendto() on the mDNS socket fails with
    "[Errno 65] No route to host" (EHOSTUNREACH). mDNS's own poll loop
    (discovery_mdns.mdns_client) already retries every MDNS_POLL_INTERVAL_SEC
    and succeeds as soon as the user grants -- or the OS silently grants --
    local network access, so this is a one-time, self-healing startup
    artefact rather than a real problem.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != 'zeroconf' or 'Error with socket' not in record.getMessage():
            return True
        message = record.getMessage()
        if 'WinError 59' in message:
            return False
        if 'Errno 65' in message and 'No route to host' in message:
            return False
        return True


def init_logging():
    logpath = None
    try:
        logging.basicConfig(level=Config.log_level)
        root_logger = logging.getLogger()
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s %(message)s', '%Y-%m-%dT%H:%M:%S')
        formatter.converter = time.gmtime

        # uvicorn.Config(log_config=None) leaves this logger unconfigured by uvicorn,
        # so its records propagate up to root and pick up our formatting/handlers
        # like everything else -- see _SuppressBenignUvicornShutdown above.
        logging.getLogger('uvicorn.error').addFilter(_SuppressBenignUvicornShutdown())

        # zeroconf's own logger, propagates to root the same way -- see
        # _SuppressBenignZeroconfSocketError above.
        logging.getLogger('zeroconf').addFilter(_SuppressBenignZeroconfSocketError())

        # Collect all the blocking handlers (stdout, file)
        blocking_handlers = []

        # Stdout handler
        if Config.log_to_stdout:
            stdout_handler = root_logger.handlers[0]
            stdout_handler.setFormatter(formatter)
            blocking_handlers.append(stdout_handler)

        # File handler
        if Config.log_to_file:
            logfile = 'alpaca.log'
            logdir = Config.log_dir if Config.log_dir else '.'
            logpath = os.path.join(logdir, logfile)
            file_handler = logging.handlers.RotatingFileHandler(
                logpath,
                mode='w',
                delay=False,
                maxBytes=Config.max_size_mb * 1000000,
                backupCount=Config.num_keep_logs,
                encoding='utf-8'
            )
            file_handler.setLevel(Config.log_level)
            file_handler.setFormatter(formatter)
            file_handler.doRollover()
            blocking_handlers.append(file_handler)

        # Remove all existing handlers from root logger
        root_logger.handlers.clear()

        if blocking_handlers:
            # Wrap all blocking handlers in a single QueueHandler
            # This makes every logger.info/warning/etc non-blocking on the event loop
            log_queue = queue.Queue()
            queue_handler = logging.handlers.QueueHandler(log_queue)
            queue_handler.setLevel(Config.log_level)
            root_logger.addHandler(queue_handler)

            # QueueListener runs blocking handlers in a background thread
            global _log_queue_listener, _blocking_handlers
            _log_queue_listener = logging.handlers.QueueListener(
                log_queue,
                *blocking_handlers,
                respect_handler_level=True
            )
            _log_queue_listener.start()
            _blocking_handlers = blocking_handlers

        root_logger.setLevel(Config.log_level)
        return root_logger

    except Exception as e:
        print("\n==ERROR== Unable to start the Alpaca Driver.\n")
        print(f"The log file is currently in use by another program: {'None' if logpath is None else logpath}\n")
        print("This usually means:")
        print(" • Another instance of the Alpaca Driver is running, or")
        print(" • The log file is open in another program (such as Notepad).\n")
        print("Please close the other program or stop the running instance,")
        print("then try again.\n")
        print(f"Technical details:\n{e}\n")
        time.sleep(5)
        sys.exit(1)


def shutdown_logging():
    """Call this during app shutdown to flush and stop the queue listener."""
    global _log_queue_listener, _blocking_handlers
    if _log_queue_listener:
        _log_queue_listener.stop()
        _log_queue_listener = None
    for handler in _blocking_handlers:
        handler.close()   # stop() doesn't close its handlers itself -- release the file/stream here
    _blocking_handlers = []


def update_log_level(level_name: str):
    level = getattr(logging, level_name.upper(), None)
    if isinstance(level, int):
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)
        logger.info(f"Log level updated to {level_name}")
    else:
        logger.warning(f"Invalid log level: {level_name}")
    return logger.level