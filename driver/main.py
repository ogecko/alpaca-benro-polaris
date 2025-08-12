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
import stellarium
import app
import argparse
from pathlib import Path
import os
from polaris import Polaris

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

    # Create the Polaris master object and startup each ASCOM device
    polaris = Polaris(logger)
    telescope.start_telescope(polaris)


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

    # Output Alpaca Driver version
    logger.info(f'==STARTUP== ALPACA BENRO POLARIS DRIVER v{shr.DeviceMetadata.Version} =========== ') 




    # Create a separate thread for ASCOM Discovery
    _DSC = DiscoveryResponder(Config.alpaca_ip_address, Config.alpaca_port)

    # Create a native stellarium telescope service
    if Config.stellarium_telescope_port > 0:
        await stellarium.stellarium_telescope(logger, 
                                              Config.stellarium_telescope_ip_address, 
                                              Config.stellarium_telescope_port)
    
    tasks = [
            app.alpaca_httpd(logger),
            telescope.polaris.client(logger)
    ]
    await asyncio.gather(*tasks)
    await telescope.polaris.shutdown()




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
        asyncio.run(telescope.polaris.shutdown())

    except Exception as error:
        print(f"Error {error}, quit.")
        asyncio.run(telescope.polaris.shutdown())

    except KeyboardInterrupt:
        print("Keyboard interrupt.")
        asyncio.run(telescope.polaris.shutdown())
   




# ==================================================================
