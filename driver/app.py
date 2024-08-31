# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# app.py - Alpaca Application module
#
# Part of the AlpycaDevice Alpaca skeleton/template device driver
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

import inspect
import uvicorn
from falcon import App, asgi
import management
import setup
from config import Config

#########################
# FOR EACH ASCOM DEVICE #
#########################
import telescope

#--------------
API_VERSION = 1           
#--------------

#-----------------------
# Magic routing function
# ----------------------
def init_routes(app: App, devname: str, module):
    """Initialize Falcon routing from URI to responser classses

    Inspects a module and finds all classes, assuming they are Falcon
    responder classes, and calls Falcon to route the corresponding
    Alpaca URI to each responder. This is done by creating the
    URI template from the responder class name.

    Args:
        app (App): The instance of the Falcon processor app
        devname (str): The name of the device (e.g. 'rotator")
        module (module): Module object containing responder classes

    """
    memlist = inspect.getmembers(module, inspect.isclass)
    for cname,ctype in memlist:
        if ctype.__module__ == module.__name__:    # Only classes *defined* in the module
            app.add_route(f'/api/v{API_VERSION}/{devname}/{{devnum:int(min=0)}}/{cname.lower()}', ctype())  # type() creates instance!



# ---------------------------------------------
# MAIN HTTP/REST API ENGINE (FALCON ASGI BASED)
# ---------------------------------------------
async def alpaca_httpd(logger):
    """Initialize Falcon app and start serving it
     
    Create an asgi Falcon app defining all routes. 
    Then create a httpd server based on the app and serve it.

    """
    # falcon.asgi.App instances are callable ASGI apps
    falc_app = asgi.App()

    #########################
    # FOR EACH ASCOM DEVICE #
    #########################
    init_routes(falc_app, 'telescope', telescope)
    #
    # Initialize routes for Alpaca support endpoints
    falc_app.add_route('/management/apiversions', management.apiversions())
    falc_app.add_route(f'/management/v{API_VERSION}/description', management.description())
    falc_app.add_route(f'/management/v{API_VERSION}/configureddevices', management.configureddevices())
    falc_app.add_route('/setup', setup.svrsetup())
    falc_app.add_route(f'/setup/v{API_VERSION}/telescope/{{devnum}}/setup', setup.devsetup())

    # Create a http server
    alpaca_config = uvicorn.Config(falc_app, host=Config.alpaca_ip_address, port=Config.alpaca_port, log_level="error")
    alpaca_server = uvicorn.Server(alpaca_config)
    logger.info(f'==STARTUP== Serving ASCOM on {Config.alpaca_ip_address}:{Config.alpaca_port}. Time stamps are UTC.')

    # Serve the application
    await alpaca_server.serve()


