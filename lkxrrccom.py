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

from faster_fifo import Queue
import serial
import threading
import time


class ComHandler():
    ser = None
    
    def __init__(self, serialport=None):
        self.serialqueue = Queue()
        
        if serialport == "None":
            serialport = None
        if serialport is not None:
            dev = serialport
            self.ser = serial.Serial(dev, write_timeout=0)

            self.thread = threading.Thread(target=self.SerialListener)
            self.thread.start()

        
    def HandleComData(self, data):
        #self.serialoutqueue.put(data)
        if self.ser is not None:
            self.ser.write(data)
        
    def SerialListener(self):
        while True:
            data = self.ser.read_until(b';')
            self.serialqueue.put(data.decode('utf-8'))


if __name__ == "__main__":
    ch = ComHandler()
    while True:
        pass
