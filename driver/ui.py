# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# gui.py - Alpaca Application module
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

import sys
import asyncio

from qasync import QEventLoop, QApplication, asyncSlot, asyncClose
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QMessageBox

app_close_event = None

class MainWindow(QWidget):    
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.setLayout(QVBoxLayout())
        self.lbl_status = QLabel("ABP is running...", self)
        self.layout().addWidget(self.lbl_status)
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.on_btn_clicked)
        self.layout().addWidget(self.quit_button)
     
    @asyncClose   
    async def closeEvent(self, event):
        pass
        
    @asyncSlot()
    async def on_btn_clicked(self):
        global app_close_event
        reply = QMessageBox.question(self, 'Window Close', 'Are you sure you want to quit?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.logger.info("==CLOSING== Quit button pressed")
            # doesn't work properly because other asyncio tasks are not terminated
            #app_close_event.set()
        else:
            pass


async def ui_task(logger):
    global app_close_event
    
    app = QApplication(sys.argv)
    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)
    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)

    main_window = MainWindow(logger)
    main_window.show()
        
    while app_close_event.is_set() == False:
        await asyncio.sleep(0.05)
        app.processEvents()

