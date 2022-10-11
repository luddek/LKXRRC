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
import socket
import select
import logging
import threading

class LKXSocketHandler(object):
    """
    Hanldes the three sockets needed for communicating with the remoterig.
    Uses non-blocking sockets, and one thread for using them all
    """
    sipsocket = None
    comsocket = None
    rtpsocket = None
    runthread = False
    
    def __init__(self, host, sipport, comport, rtpport):
        self.host = host
        self.sipport = sipport
        self.comport = comport
        self.rtpport = rtpport
        self.sipqueue = Queue()
        self.comqueue = Queue()
        self.rtpqueue = Queue()
        self.sockets = []
        self.timeout = 60
        
    def ConnectSip(self):
        """
        Connect the sipsocket
        """
        self.sipsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.sipsocket.settimeout(self.timeout)
        self.sipsocket.setblocking(False)
        self.sipsocket.connect((self.host, self.sipport))
        logging.debug("Connected socket to SIP")
        self.sockets.append(self.sipsocket)
        self.start_listening_thread()

    def ConnectCom(self):
        """
        Connect the comsocket
        """
        self.comsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.comsocket.setblocking(False)
        self.comsocket.connect((self.host, self.comport))
        logging.debug("Connected socket to COM")
        self.sockets.append(self.comsocket)

    def ConnectRtp(self):
        """
        Connect the rtpsocket
        """
        self.rtpsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpsocket.setblocking(False)
        self.rtpsocket.connect((self.host, self.rtpport))
        logging.debug("Connected socket to RTP")
        self.sockets.append(self.rtpsocket)

    def Disconnect(self):
        """
        Stop thread and close sockets
        """
        self.runthread = False
        for s in self.sockets:
            s.close()
            s.shutdown()

    def _send(self, socket, msg, msglen):
        """
        Write msg with msglen to socket.
        """
        totalsent = 0
        while totalsent < msglen:
            sent = socket.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent
    
    def _recieve(self, socket, msglen):
        """
        Read message with len msglen from socket.
        """
        raise Exception("Remove this method")
        chunks = []
        bytes_recd = 0
        while bytes_recd < msglen:
            chunk = socket.recv(min(msglen - bytes_recd, 2048))
            if chunk == '':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        return ''.join(chunks)
    
    def Readpackage(self, socket):
        """
        Read everything that is in the socket
        """
        data, addr = socket.recvfrom(1024)
        return data

    def SendSipmsg(self, msg):
        """
        Send a msg to the sipsocket
        """
        msgbytes = str.encode(msg)
        self._send(self.sipsocket, msgbytes, len(msgbytes))

    def SendCommsg(self, msg, raw=False):
        """
        Send a msg to the comsocket
        """
        if raw:
            msgbytes = msg
        if not raw:
            msgbytes = str.encode(msg)
        self._send(self.comsocket, msgbytes, len(msgbytes))

    def SendRtpmsg(self, msg):
        """
        Send a msg to the rtpsocket
        """
        #msgbytes = str.encode(msg)
        msgbytes = msg
        self._send(self.rtpsocket, msgbytes, len(msgbytes))

    def listening_thread(self):
        """
        Endless thread that looks for data in the sockets then reads it
        """
        while self.runthread:
            read_sockets, write_sockets, error_sockets = select.select(
                self.sockets, [], [], self.timeout)
            if self.sipsocket is not None:
                if self.sipsocket in read_sockets:
                    data = self.Readpackage(self.sipsocket)
                    self.sipqueue.put(data)
            if self.comsocket is not None:
                if self.comsocket in read_sockets:
                    data = self.Readpackage(self.comsocket)
                    self.comqueue.put(data)
            if self.rtpsocket is not None:
                if self.rtpsocket in read_sockets:
                    data = self.Readpackage(self.rtpsocket)
                    self.rtpqueue.put(data)

    def start_listening_thread(self):
        self.thread = threading.Thread(target=self.listening_thread)
        self.runthread = True
        self.thread.start()

    
