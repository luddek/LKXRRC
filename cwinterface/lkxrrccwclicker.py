#!/usr/bin/python3
#-*- coding: utf-8 -*-
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#


#
# A small QT-widget that sends the same signal as the straight key adapter
# Allows you to use your computer mouse as a "straight key"
#
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
import sys

import serial

class CWClicker(QWidget):
    ser = None
    def __init__(self, serialport=None):
        if serialport is not None:
            self.ser = serial.Serial(serialport)
        QWidget.__init__(self)
        self.initUI()
        self.cwButton.pressed.connect(self.on_cwButton_pressed)
        self.cwButton.released.connect(self.on_cwButton_released)
        
    def initUI(self):
        self.setWindowTitle("PushButton")
        self.setGeometry(400,400,300,260)
        self.cwButton = QPushButton(self)
        self.cwButton.setText("CW")

    def setSerialPort(self, serialport):
        try:
            if serialport is not None:
                self.ser = serial.Serial(serialport)
        except Exception as e:
            print("Couldn't connect to cw serial")
            print(e)

    def on_cwButton_pressed(self):
        if self.ser is None:
            print("CW clicker not connected to lkxrrc")
            return
        data = b"1\r\n"
        self.ser.write(data)

    def on_cwButton_released(self):
        if self.ser is None:
            print("CW clicker not connected to lkxrrc")
            return
        data = b"0\r\n"
        self.ser.write(data)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    wid = CWClicker("../ttyS26")
    wid.show()
    sys.exit(app.exec_()) 
