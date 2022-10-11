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


# Micro Python code
# Used with a Raspberry Pi Pico as a 
# Straight Key interface

#
# It outputs a serial 1 when the button is pressed
# And a 0 when it is released, nothing between...
#


import machine, utime

key_input = machine.Pin(28, machine.Pin.IN, machine.Pin.PULL_DOWN)
led = machine.Pin("LED", machine.Pin.OUT)

#debouncetime = 25 # 10 ms

lastvalue = 0
while True:
    value = key_input.value()
    if value != lastvalue:
        if value:
            led.on()
        else:
            led.off()
        lastvalue = value
        print(value)
        # Debounce
        #utime.sleep_ms(debouncetime)
