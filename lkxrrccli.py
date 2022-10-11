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


### This is the commandline interface to start and use the lkxrrc
### Make sure to configure settings.cfg before you run

import time
import threading

from lkxrrc import LKXRRC
import sshkeyboard

lkx = LKXRRC()
lkx.Connect()
runloop = True


def press(key):
    # Handle keypresses
    global runloop
    global lkx
    print(f"'{key}' pressed")
    if key == 'q':
        lkx.Disconnect()
        runloop = False
    if key == 'a':
        msg = '\x06AI1;\r\n'
        lkx.sockethandler.SendCommsg(msg)
        print("Sendtit", msg)
    if key == 's':
        msg = '\x06AI0;\r\n'
        lkx.sockethandler.SendCommsg(msg)
        print("Sendtit", msg)
    if key == 'z' or key == 'space':
        lkx.PttOn()
        print("Ptt on")
    if key == 'x':
        lkx.PttOff()
        print("Ptt off")
    if key == 'b':
        print("CW")
        lkx.cwserialhandler.CWEvent(True)
    if key == 'p':
        msg = '\x06PS1;\r\n'
        print("Trying to power on")
        lkx.sockethandler.SendCommsg(msg)
    if key == 'l':
        msg = '\x06PS0;\r\n'
        print("Trying to power off")
        lkx.sockethandler.SendCommsg(msg)

def release(key):
    if key == 'b':
        print("CW")
        lkx.cwserialhandler.CWEvent(False)
    if key == 'space':
        lkx.PttOff()
        print("Ptt off")
    print(f"'{key}' released")

def keyboardwork():
    sshkeyboard.listen_keyboard(
        on_press=press,
        on_release=release,
        delay_second_char=0.3,
        delay_other_chars=0.3,
    )


keboardthread = threading.Thread(target=keyboardwork)
keboardthread.start()

lasttime = time.time()
while runloop:
    lkx.HandleData()
    if time.time() - lasttime > 5:
        lasttime = time.time()
        lkx.PrintQueueSizes()
    time.sleep(1e-3) # so much sleep...
time.sleep(1)
print("fin")
