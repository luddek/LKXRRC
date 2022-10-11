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
import enum
import socket
import logging
import configparser
from lkxrrcsockets import LKXSocketHandler
from lkxrrcsip import SipHandler, SipResponse
import lkxrrcrtp
from lkxrrcrtp import RtpHandler
from lkxrrccom import ComHandler
import lkxrrccw

logging.basicConfig(level=logging.DEBUG)

class ConnectionState(enum.Enum):
    Disconnected = 0
    Connecting = 1
    Authorizing = 2
    Ringing = 3
    Connected = 4

class LKXRRC():
    """
    The main class that keeps track of the communication with the remoterig.
    """
    waitingforsipresponse = False
    packetnumber = 0 # Just to keep track of number of packets receivec
    ptt = False # Current state of the ptt, set to True and lkxrrc will start transmitting and trigger the remote site
    lastconnectstarted = 0 # Timestamp for when we tried to connect
    connecttimeout = 5 # Number of seconds before trying again
    connecttryno = 0
    connectretries = 3 # Number of times to retry conecntion
    
    def __init__(self):
        self.state = ConnectionState.Disconnected
        config = configparser.ConfigParser()
        config.read('settings.cfg')
        host = config['RRC']['Host']
        sipport = int(config['RRC']['SipPort'])
        comport = int(config['RRC']['ComPort'])
        rtpport = int(config['RRC']['RtpPort'])
        realm = config['RRC']['Realm']
        username = config['RRC']['Username']
        password = config['RRC']['Password']
        deviceid = config['RRC']['Deviceid']
        deviceid = config['RRC']['Deviceid']
        toip = socket.gethostbyname(host)
        fromip = "127.0.0.1" #urllib.request.urlopen('https://ident.me').read().decode('utf8')

        forcecodeczero = config.getboolean('CODEC', 'ForceCodecZero')
        remotecodec = int(config['CODEC']['RemoteCodec'])
        localcodec = int(config['CODEC']['LocalCodec'])

        serialport = config['SERIAL']['VirtualSerial']

        cwserialport = config['CW']['CWSerialPort']
        cwstonefreq = int(config['CW']['SideToneFrequency'])
        
        self.sockethandler = LKXSocketHandler(host,sipport,comport,rtpport)
        self.siphandler = SipHandler(host,toip,fromip,username,password,realm,sipport,rtpport,deviceid, comport, forcecodeczero)
        self.rtphandler = RtpHandler(remotecodec,localcodec)
        self.comhandler = ComHandler(serialport)
        # First a handler that creates appropriate packages
        self.cwhandler = lkxrrccw.CWHandler()
        # Then a handler that creates sidetone and talks
        # to my straight key
        self.cwserialhandler = lkxrrccw.CWSerialHandler(cwserialport, self.CWCallback, cwstonefreq)

    def Connect(self):
        """
        Initiate the sip socket and send first invite package
        """
        self.lastconnectstarted = time.time()
        self.connecttryno += 1
        if self.connecttryno > self.connectretries:
            self.Disconnect()
            raise Exception("Could not connect")
        self.state = ConnectionState.Connecting
        self.sockethandler.ConnectSip()
        inviterequest = self.siphandler.CreateInviteRequest()
        self.waitingforsipresponse = True
        self.sockethandler.SendSipmsg(inviterequest)

    def Disconnect(self):
        """
        Send bye message, then close sockets
        """
        byemsg = self.siphandler.CreateByeMsg()
        print("Sending bye msg to the remote site")
        self.sockethandler.SendSipmsg(byemsg)
        self.rtphandler.CloseAudio()

    def AnswerCall(self):
        """
        Invoke this method when the remote site is calling us,
        open the other sockets and send initial messages.
        """
        self.rtphandler.OpenAudio()
        self.sockethandler.ConnectCom()
        self.sockethandler.ConnectRtp()
        startmsg = "\x06AI0;PS;"
        self.sockethandler.SendCommsg(startmsg)
        rtpmsg = self.rtphandler.CreateRtpMsg(False)
        self.sockethandler.SendRtpmsg(rtpmsg)

    def HandleData(self):
        """
        Check if we got any udp messaeges, and handle them accordingly
        """
        # Handle the data in the queues incoming and outgoing
        # Note some messages are written directly, no through the queues here
        # For example the CW messages
        if self.state != ConnectionState.Connected:
            # See if we need to try to reconnect
            if time.time() - self.lastconnectstarted > self.connecttimeout:
                print("Well it seems we didn't manage to connect, let's try again")
                self.Connect()
        if not self.sockethandler.sipqueue.empty():
            data = self.sockethandler.sipqueue.get()
            self.HandleSipData(data)
        if not self.sockethandler.comqueue.empty():
            data = self.sockethandler.comqueue.get()
            if self.sockethandler.comqueue.qsize() > 5:
                print("Com queue is large",self.sockethandler.comqueue.qsize())
            self.comhandler.HandleComData(data)
        if not self.sockethandler.rtpqueue.empty():
            self.packetnumber += 1
            data = self.sockethandler.rtpqueue.get()
            self.rtphandler.HandleRtpData(data)
            self.state = ConnectionState.Connected
            # Hacking a bit to keep the connection alive
            if self.packetnumber % 500 == 0:
                self.sockethandler.SendCommsg("\x06PS;")
                if not self.ptt:
                    # keep alive message, sending some empty data
                    rtpmsg = self.rtphandler.CreateRtpMsg(self.ptt)
                    self.sockethandler.SendRtpmsg(rtpmsg)
        if not self.comhandler.serialqueue.empty() and self.state == ConnectionState.Connected:
            data = self.comhandler.serialqueue.get()
            self.sockethandler.SendCommsg("\x06"+data)
        if not self.rtphandler.micqueue.empty() and self.state == ConnectionState.Connected:
            # We got packages in the micqueue, that means we are recording
            # Lets transmit them!!
            rtpmsg = self.rtphandler.CreateRtpMsg(self.ptt)
            self.sockethandler.SendRtpmsg(rtpmsg)

    def PttOn(self):
        # Before setting PTT on, we shoudl create on
        # RTP message with PTT off
        self.rtphandler.StartRecording()
        rtpmsg = self.rtphandler.CreateRtpMsg(self.ptt)
        self.sockethandler.SendRtpmsg(rtpmsg)
        self.ptt = True


    def PttOff(self):
        self.ptt = False
        rtpmsg = self.rtphandler.CreateRtpMsg(False)
        self.sockethandler.SendRtpmsg(rtpmsg)
        self.rtphandler.StopRecording()

    def HandleSipData(self, data):
        """
        Got new sipdata, handle requests and responses
        make the authorization etc.
        """
        if self.waitingforsipresponse:
            self.waitingforsipresponse = False
            response = SipResponse(data)
            if self.state == ConnectionState.Connecting:
                if response.code == 401:
                    # We expect our first answer to be a 401
                    ackmsg = self.siphandler.CreateACK()
                    self.sockethandler.SendSipmsg(ackmsg)
                    self.siphandler.nonce = response.nonce
                    self.siphandler.uri = response.uri
                    self.siphandler.fromtag = response.totag
                    logging.info("Not authorized, got nonce, making a new request.")
                    # Got the nonce, now we can create an autorization request
                    self.state = ConnectionState.Authorizing
                    authorizationmsg = self.siphandler.CreateAuthorizationRequest()
                    self.sockethandler.SendSipmsg(authorizationmsg)
                    self.waitingforsipresponse = True
            elif self.state == ConnectionState.Authorizing:
                if response.code == 403:
                    logging.error("Error 403 when trying to authorize")
                    self.disconnect()
                if response.code == 180:
                    ackmsg = self.siphandler.CreateACK()
                    self.sockethandler.SendSipmsg(ackmsg)
                    self.state = ConnectionState.Ringing
                    logging.debug("The remote site is ringing me")
                    self.AnswerCall()
        else:
            # TODO Handle requests from the remote site
            if data[:4] == b"INFO":
                #print("Got info request, maybe at least, pretending and sending an answer...")
                statusmsg = self.siphandler.CreateStatusMsg()
                self.sockethandler.SendSipmsg(statusmsg)
            elif data[:3] == b"BYE":
                print("Got a BYE, disconnecting")
                self.Disconnect()
            elif data == b"\r\n\r\n":
                # Perhaps this is some kinde of keepalive?
                # It's always nice to answer at least
                #print("Got rnrn, let's answer with an rn")
                self.sockethandler.SendSipmsg("\r\n")
            else:
                print("Got unhandled data on sip channel:")
                print(data)

    def CWCallback(self, cwtone):
        """
        Callback fron the CW Serial handler, it
        wants to write on the com channel. TODO solve it in some other way
        # Can be used with True/False to bloop the cw key
        """
        msg = self.cwhandler.CreateCWPackage(cwtone)
        self.sockethandler.SendCommsg(msg, raw=True)

    def PrintQueueSizes(self):
        audosize = self.rtphandler.audioqueue.qsize()
        micsize  = self.rtphandler.micqueue.qsize()
        print("Out: {}, In: {}".format(audosize,micsize))

# Examples of how to use this is in either lkxrrccli.py for a commandline version
# or in lkxrrcgui.py for a graphical userinterface
if __name__=="__main__":
    print("Don't launch this directly, try lkxrrccli.py")


