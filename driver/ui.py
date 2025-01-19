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
import re
import asyncio
import telescope
import shr

from qasync import QEventLoop, QApplication, asyncSlot, asyncClose
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QMessageBox

class MainWindow(QWidget):
    def __init__(self, logger, app_close_event):
        super().__init__()
        self.logger = logger
        self.app_close_event = app_close_event
        self.setLayout(QVBoxLayout())
        self.lbl_version = QLabel(f'{shr.DeviceMetadata.Description} {shr.DeviceMetadata.Version}', self)
        self.lbl_status = QLabel("", self)
        self.lbl_error = QLabel("", self)
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setMaximumWidth(280)
        self.connected = False
        self.layout().addWidget(self.lbl_version)
        self.layout().addWidget(self.lbl_status)
        self.layout().addWidget(self.lbl_error)
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.setMaximumWidth(60)
        self.quit_button.clicked.connect(self.on_btn_clicked)
        self.layout().addWidget(self.quit_button, alignment=QtCore.Qt.AlignHCenter)
        self.setGeometry(100, 100, 320, 240)
        self.setWindowTitle(f'{shr.DeviceMetadata.Description}')
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.timeout.connect(self.updateUI)
        self.updateTimerInterval = 1000 * 0.5
        self.updateTimer.setInterval(self.updateTimerInterval)
        self.updateTimer.start()
     
    @asyncSlot()
    async def updateUI(self):
        if self.lbl_status.text() == "" or self.connected != telescope.polaris.connected:
            self.connected = telescope.polaris.connected
            if telescope.polaris.connected:
                self.lbl_status.setText("Connected to Polaris")
            else:
                self.lbl_status.setText("Not connected to Polaris")
        errorstr = re.sub(r"^==[A-Z]*== ", "", telescope.polaris.errorstr)
        self.lbl_error.setText(errorstr)
    
    @asyncClose
    async def closeEvent(self, event):
        pass
        
    @asyncSlot()
    async def on_btn_clicked(self):
        global app_close_event
        reply = QMessageBox.question(self, 'Close Alpaca Benro Polaris', 'Are you sure you want to quit?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.logger.info("==CLOSING== Quit button pressed")
            self.app_close_event.set()
        else:
            pass

class UI:
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.app = QApplication(sys.argv)
        self.event_loop = QEventLoop(self.app)
        asyncio.set_event_loop(self.event_loop)
        self.app_close_event = asyncio.Event()
        self.app.aboutToQuit.connect(self.app_close_event.set)
        self.main_window = MainWindow(self.logger, self.app_close_event)
        self.main_window.show()
        
    async def run_event_loop(self):
        while self.app_close_event.is_set() == False:
            await asyncio.sleep(0.05)
            self.app.processEvents()
