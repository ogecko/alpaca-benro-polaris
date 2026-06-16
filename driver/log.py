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


def init_logging():
    try:
        logging.basicConfig(level=Config.log_level)
        root_logger = logging.getLogger()
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s %(message)s', '%Y-%m-%dT%H:%M:%S')
        formatter.converter = time.gmtime

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
                backupCount=Config.num_keep_logs
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
            global _log_queue_listener
            _log_queue_listener = logging.handlers.QueueListener(
                log_queue,
                *blocking_handlers,
                respect_handler_level=True
            )
            _log_queue_listener.start()

        root_logger.setLevel(Config.log_level)
        return root_logger

    except Exception as e:
        print("\n==ERROR== Unable to start the Alpaca Driver.\n")
        print("The log file is currently in use by another program:")
        print(f"{logpath}\n")
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
    global _log_queue_listener
    if _log_queue_listener:
        _log_queue_listener.stop()
        _log_queue_listener = None


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