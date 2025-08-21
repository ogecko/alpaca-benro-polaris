# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# app_web.py - Alpaca Pilot Web Application module
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
import os
import mimetypes
import aiofiles
import uvicorn
from falcon import asgi, HTTP_200
from config import Config
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent    # Get the path to the current script
QUASAR_DIST = SCRIPT_DIR.parent / 'pilot' / 'dist' / 'spa'   

class QuasarStaticResource:
    async def on_get(self, req, resp, path=None):
        requested_path = path or 'index.html'
        file_path = QUASAR_DIST / requested_path
        if not os.path.isfile(file_path):
            file_path = QUASAR_DIST / 'index.html'  # fallback for SPA routing

        resp.content_type = mimetypes.guess_type(file_path)[0] or 'text/html'
        async with aiofiles.open(file_path, 'rb') as f:
            resp.data = await f.read()

# ---------------------------------------------
# MAIN HTTP ENGINE (FALCON ASGI BASED)
# ---------------------------------------------
async def alpaca_pilot_httpd(logger):
    """Initialize Falcon app and start serving it
     
    Create an asgi Falcon app defining all routes. 
    Then create a httpd server based on the app and serve it.

    """
    # falcon.asgi.App instances are callable ASGI apps
    web_app = asgi.App()

    if (Config.enable_pilot):
        # add the Pilot Static routes
        web_app.add_static_route('/icons', QUASAR_DIST / 'icons')      # icons resources (note /{path} does serve subdirecties)
        web_app.add_static_route('/assets', QUASAR_DIST / 'assets')    # assets resources
        web_app.add_route('/{path}', QuasarStaticResource())                 # root resources, fallback to index.html when not found
        web_app.add_route('/', QuasarStaticResource())                       # root, fallback to index.html when nothing provided

    # Create a http server
    pilot_config = uvicorn.Config(web_app, host=Config.alpaca_restapi_ip_address, port=Config.alpaca_pilot_port, log_level="error")
    pilot_server = uvicorn.Server(pilot_config)
    logger.info(f'==STARTUP== Serving Alpaca Pilot on {Config.alpaca_restapi_ip_address}:{Config.alpaca_pilot_port}.')

    # Serve the application
    try:
        await pilot_server.serve()
    except KeyboardInterrupt:
        raise ValueError('Keyboard interrupt.')


