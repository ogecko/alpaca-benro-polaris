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
import os
import mimetypes
import aiofiles
import inspect
import uvicorn
from falcon import App, asgi
import management
import setup
from config import Config
from pathlib import Path

#########################
# FOR EACH ASCOM DEVICE #
#########################
import telescope
import rotator

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


SCRIPT_DIR = Path(__file__).resolve().parent    # Get the path to the current script
QUASAR_DIST = SCRIPT_DIR.parent / 'pilot' / 'dist' / 'spa'   

class StaticResource:
    async def on_get(self, req, resp, path=None):
        requested_path = path or 'index.html'
#        file_path = os.path.join(QUASAR_DIST, requested_path)
        file_path = QUASAR_DIST / requested_path
        if not os.path.isfile(file_path):
            file_path = QUASAR_DIST / 'index.html'  # fallback for SPA routing

        resp.content_type = mimetypes.guess_type(file_path)[0] or 'text/html'
        async with aiofiles.open(file_path, 'rb') as f:
            resp.data = await f.read()


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
    init_routes(falc_app, 'rotator', rotator)
    #
    # Initialize routes for Alpaca support endpoints
    falc_app.add_route('/management/apiversions', management.apiversions())
    falc_app.add_route(f'/management/v{API_VERSION}/description', management.description())
    falc_app.add_route(f'/management/v{API_VERSION}/configureddevices', management.configureddevices())
    falc_app.add_route(f'/management/v{API_VERSION}/discoveralpaca', management.discoveralpaca())
    falc_app.add_route(f'/management/v{API_VERSION}/discoverpolaris', management.discoverpolaris())
    falc_app.add_route(f'/management/v{API_VERSION}/blepolaris', management.blepolaris())
    falc_app.add_route('/setup', setup.svrsetup())
    falc_app.add_route(f'/setup/v{API_VERSION}/telescope/{{devnum}}/setup', setup.devsetup())

    # add the Pilot Static routes
    falc_app.add_static_route('/icons', QUASAR_DIST / 'icons')      # icons resources (note /{path} does serve subdirecties)
    falc_app.add_static_route('/assets', QUASAR_DIST / 'assets')    # assets resources
    falc_app.add_route('/{path}', StaticResource())                 # root resources, fallback to index.html when not found
    falc_app.add_route('/', StaticResource())                       # root, fallback to index.html when nothing provided

    # Create a http server
    alpaca_config = uvicorn.Config(falc_app, host=Config.alpaca_ip_address, port=Config.alpaca_port, log_level="error")
    alpaca_server = uvicorn.Server(alpaca_config)
    logger.info(f'==STARTUP== Serving ASCOM Alpaca on {Config.alpaca_ip_address}:{Config.alpaca_port}. Time stamps are UTC.')

    # Serve the application
    try:
        await alpaca_server.serve()
    except KeyboardInterrupt:
        raise ValueError('Keyboard interrupt.')


