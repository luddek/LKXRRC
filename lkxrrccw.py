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
import time
import struct
import threading

import serial
import sounddevice

import numpy as np

### CW Handler
### It appears pkg1 starts bloop
#pkg1 = b"\x05\xfe\xce\x38\x00\x01\xfa\x4b\x1d"
### And pkg2 stops bloop
#pkg2 = b"\x05\x63\xcf\x38\x00\x00\xfa\x4b\x1e"
### They are sent on the comms channel port 13002


# Is probably timestamp, then signal, then an iterating number

class CWHandler():
    pkgnumber = 0

    def CreateCWPackage(self, keydown):
        """
        Creates CW Package with keydown or keyup
        """
        pkg = b""
        pkg += b"\x05" # Seems like first byte is always a 5
        timestamp = round(time.time() * 1000) & 0xFFFF
        timestampbytes = struct.pack('<i', timestamp)
        # Can't figure it out now,
        # Let's just use these raw bytes for now
        #timestampbytes = b"\x05\x63\xcf\x38"
        pkg += timestampbytes
        # The first bit might be key-delay hmmm...
        if keydown is True:
            pkg += b"\x01"
        if keydown is False:
            pkg += b"\x00"
        # Adding something I don't understand
        pkg += b"\xfa\x4b"
        pkgnumberbytes = struct.pack('<i', self.pkgnumber)
        self.pkgnumber += 1
        pkgnumberbytes = pkgnumberbytes[:1] # Only one byte!
        pkg += pkgnumberbytes
        return pkg



## Now lets listen for my straight key on a serial port
class CWSerialHandler():
    serialport = None
    
    def __init__(self, serialport, cwcallback, sidetonefreq):
        self.serialport = serialport
        self.cwcallback = cwcallback
        self.sidetonefreq = sidetonefreq

        # Let's try to calculate samplerate and framesize such that
        # we fit complete sinus cycles
        n_cycles = 1
        samplerate = sidetonefreq*2*8 #Nyqvist * a lot extra
        framesize = samplerate/sidetonefreq*n_cycles

        print(framesize)
        framesize = int(framesize)

        self.samplerate = samplerate
        self.framesize = framesize

        print(samplerate)

        if serialport is not None and serialport != "None":
            self.ser = serial.Serial(self.serialport)
            self.thread = threading.Thread(target=self.CWListener)
            self.thread.start()

        self.sidetonestream = sounddevice.OutputStream(samplerate=samplerate, blocksize=framesize,
                                channels=1, dtype='float32', callback=self.tonecallback)



    def tonecallback(self, outdata, frames, timec, status):
        f = self.sidetonefreq
        fs = self.samplerate
        t = self.framesize/fs
        samples = np.arange(self.framesize) / fs
        tone = np.sin(2*np.pi*f*samples)
        tone = tone.astype(np.float32)/10
        tone = np.reshape(tone, (self.framesize,1))
        outdata[:] = tone

    def GetCWKeyStatus(self):
        ser_bytes = self.ser.readline()
        serstr = ser_bytes.decode('utf-8')
        serstr.strip('\r\n')
        cw = bool(int(serstr))
        return cw
    
    def CWListener(self):
        while True:
            try:
                cwtone = self.GetCWKeyStatus()
            except Exception as e:
                print(e)
                cwtone = False
            self.CWEvent(cwtone)

    def CWEvent(self, cwtone):
        if cwtone:
            self.sidetonestream.start()
        else:
            self.sidetonestream.stop()
        # Tell the mainhandler that we should send cw packages
        self.cwcallback(cwtone)


if __name__=="__main__":
    cwh = CWHandler()
    for i in range(512):
        time.sleep(1e-3)
        print(cwh.CreateCWPackage(True))
        print(cwh.CreateCWPackage(False))
    print(len(cwh.CreateCWPackage(False)))

    def printcb(msg):
        print(msg)

    #cwsh = CWSerialHandler("/dev/ttyACM1", printcb, 400)
    cwsh = CWSerialHandler("./ttyVA01", printcb, 400)
    while True:
        time.sleep(0.1)
        
    
