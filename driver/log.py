# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# logging.py - Shared global logging object
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
# 01-Jan-2023   rbd 0.1 Initial edit, moved from config.py
# 15-Jan-2023   rbd 0.1 Documentation. No logic changes.
# 08-Nov-2023   rbd 0.4 Log name is now 'alpyca'

import logging
import logging.handlers
import time
from config import Config
import os

global logger
#logger: logging.Logger = None  # Master copy (root) of the logger
logger = None                   # Safe on Python 3.7 but no intellisense in VSCode etc.

def init_logging():
    """ Create the logger - called at app startup

        **MASTER LOGGER**

        This single logger is used throughout. The module name (the param for get_logger())
        isn't needed and would be 'root' anyway, sort of useless. Also the default date-time
        is local time, and not ISO-8601. We log in UTC/ISO format, and with fractional seconds.
        Finally our config options allow for suppression of logging to stdout, and for this
        we remove the default stdout handler. Thank heaven that Python logging is thread-safe!

        This logger is passed around throughout the app and may be used throughout. The
        :py:class:`config.Config` class has options to control the number of back generations
        of logs to keep, as well as the max size (at which point the log will be rotated).
        A new log is started each time the app is started.

    Returns:
        Customized Python logger.

    """

    logging.basicConfig(level=Config.log_level)
    logger = logging.getLogger()                # Root logger, see above
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s %(message)s', '%Y-%m-%dT%H:%M:%S')
    formatter.converter = time.gmtime           # UTC time
    logger.handlers[0].setFormatter(formatter)  # This is the stdout handler, level set above
    # Add a logfile handler, same formatter and level
    if Config.log_to_file or Config.log_performance_data:
        logfile = 'alpaca.log' if (not Config.log_performance_data) else 'alpaca.csv'
        logdir = Config.log_dir if Config.log_dir else '.'
        logpath = os.path.join(logdir, logfile)
        handler = logging.handlers.RotatingFileHandler(logpath,
                                                        mode='w',
                                                        delay=False,     # True to Prevent creation of empty logs
                                                        maxBytes=Config.max_size_mb * 1000000,
                                                        backupCount=Config.num_keep_logs)
        handler.setLevel(Config.log_level)
        handler.setFormatter(formatter)
        handler.doRollover()                                            # Always start with fresh log
        logger.addHandler(handler)
    if not Config.log_to_stdout:
        """
            This allows control of logging to stdout by simply
            removing the stdout handler from the logger's
            handler list. It's always handler[0] as created
            by logging.basicConfig()
        """
        logger.debug('Logging to stdout disabled in settings')
        logger.removeHandler(logger.handlers[0])    # This is the stdout handler
    
    # Output performance data log headers if enabled
    if Config.log_performance_data == 1:        # Aim data
        logger.info(f",Dataset,Time,AimAz,AimAlt,OffsetAz,OffsetAlt,AimErrorAz,AimErrorAlt")
        logger.info(f",DATA1,{0:.3f},{0:.2f},{0:.2f},{0:.2f},{0:.2f},{0:.2f},{0:.2f}")

    elif Config.log_performance_data == 2:      # Drift data
        logger.info(f",Dataset,Time,TrackingT0,TrackingT1,TargetRA,TargetDec,DriftErrRA,DriftErrDec")
        logger.info(f",DATA2,{0:.3f},{False},{False},{0:.7f},{0:.7f},{0:.3f},{0:.3f}")

    elif Config.log_performance_data == 3:      # Speed data
        logger.info(f",Dataset,Time,Interval,Constant,RateAz,SpeedAz,RateAlt,SpeedAlt,SpeedRA,SpeedDec,SpeedTotal")
        logger.info(f",DATA3,{0:.3f},{0:.2f},{False},{0:.2f},{0:.7f},{0:.2f},{0:.7f},{0:.7f},{0:.7f},'00:00:00.000'")

    elif Config.log_performance_data == 4:      # Position data (heavy logging)
        logger.info(f",Dataset,Time,Tracking,Slewing,Gotoing,TargetRA,TargetDEC,AscomRA,AscomDEC,AscomAz,AscomAlt,ErrorRA,ErrorDec")
        logger.info(f",DATA4,{0:.3f},{False},{False},{False},{0:.7f},{0:.7f},{0:.7f},{0:.7f},{0:.7f},{0:.7f},{0:.3f},{0:.3f}")

    elif Config.log_performance_data == 5:      # Rotator data (heavy logging)
        logger.info(f",Dataset,Time,  w1,x1,y1,z1, az,alt,roll,  theta1,theta2,theta3,  state1,state2,state3,  omega1,omega2,omega3,  state4,state5,state6,  oref1,oref2,oref3")

    elif Config.log_performance_data == 6:      # PID data (heavy logging)
        logger.info(f",Dataset,  Mode,  DRef1,DRef2,DRef3, ARef1,ARef2,ARef3, TRef1,TRef2,TRef3, TMeas,TMeas2,TMeas3, ORef1,ORef2,ORef3, OP1,OP2,OP3")
    
    return logger

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