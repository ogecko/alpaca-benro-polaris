# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# app_api.py - Alpaca REST API Application module
# -----------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2025 David Morrison
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
from falcon import App, asgi, HTTP_200, HTTPFound
import asyncio
import management
from config import Config
from shr import LifecycleController

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

class RedirectResource:
    async def on_get(self, req, resp):
        # Redirect to a different port (e.g. 8080)
        raise HTTPFound(f'http://{req.host}:{Config.alpaca_pilot_port}/?api={Config.alpaca_restapi_port}')

# ---------------------------------------------
# MAIN HTTP/REST API ENGINE (FALCON ASGI BASED)
# ---------------------------------------------
async def alpaca_rest_httpd(logger, lifecycle: LifecycleController):
    """Initialize Falcon app and start serving it
     
    Create an asgi Falcon app defining all routes. 
    Then create a httpd server based on the app and serve it.

    """
    # falcon.asgi.App instances are callable ASGI apps
    rest_app = asgi.App(middleware=[CORSMiddleware()])

    #########################
    # FOR EACH ASCOM DEVICE #
    #########################
    init_routes(rest_app, 'telescope', telescope)
    init_routes(rest_app, 'rotator', rotator)
    #
    # Initialize routes for Alpaca support endpoints
    rest_app.add_route('/management/apiversions', management.apiversions())
    rest_app.add_route(f'/management/v{API_VERSION}/description', management.description())
    rest_app.add_route(f'/management/v{API_VERSION}/configureddevices', management.configureddevices())
    # Custom Resources for Alpaca Benro Polaris Driver Management
    rest_app.add_route(f'/management/v{API_VERSION}/discoveralpaca', management.discoveralpaca())
    rest_app.add_route(f'/management/v{API_VERSION}/discoverpolaris', management.discoverpolaris())
    rest_app.add_route(f'/management/v{API_VERSION}/blepolaris', management.blepolaris())
    if (Config.enable_pilot):
        # Redirect Resources for Quasar Pilot App
        rest_app.add_route('/setup', RedirectResource())
        rest_app.add_route(f'/setup/v{API_VERSION}/telescope/0/setup', RedirectResource())
        rest_app.add_route(f'/setup/v{API_VERSION}/rotator/0/setup', RedirectResource())

    # Create a http server
    alpaca_config = uvicorn.Config(rest_app, host=Config.alpaca_restapi_ip_address, port=Config.alpaca_restapi_port, log_level="error")
    alpaca_server = uvicorn.Server(alpaca_config)
    logger.info(f'==STARTUP== Serving ASCOM Alpaca REST API on {Config.alpaca_restapi_ip_address}:{Config.alpaca_restapi_port}. Time stamps are UTC.')

    # Serve the application
    try:
        await asyncio.gather(
            alpaca_server.serve(),
            lifecycle.wait_for_event()
        )
    except asyncio.CancelledError:
        logger.info("==CANCELLED== Alpaca REST API cancelled.")
    except KeyboardInterrupt:
        logger.info("Alpaca REST API received KeyboardInterrupt. Shutting down.")
        raise
    finally:
        # shutdown the server
        await alpaca_server.shutdown()



class CORSMiddleware:
    async def process_request(self, req, resp):
        # No-op for most requests; CORS headers are added in process_response
        pass

    async def process_response(self, req, resp, resource, req_succeeded):
        origin = req.headers.get("origin", "*")
        resp.set_header("Access-Control-Allow-Origin", origin)
        resp.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        resp.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        resp.set_header("Access-Control-Allow-Credentials", "true")

        if req.method == "OPTIONS":
            resp.status = HTTP_200
            resp.complete = True
