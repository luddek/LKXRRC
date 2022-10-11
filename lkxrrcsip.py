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
# Here I've gathered all the necessary methods for generating and parsing the sip messages
#
import time
import uuid

import hashlib #for md5

def gethash(msg):
    return hashlib.md5(msg.encode()).hexdigest()

def current_time_millis():
    return round(time.time() * 1000)

def calculate_cnonce():
     msg = str(current_time_millis())
     return gethash(msg)

def calculate_response(username, realm, pwd, uri, nonce):
    """
    Used to authenticate
    """
    msg = "{}:{}:x5atd{}".format(username,realm,pwd)
    md5_1 = gethash(msg)
    msg2 = "INVITE:{}".format(uri)
    md5_2 = gethash(msg2)
    msg3 = "{}:{}:{}".format(md5_1,nonce,md5_2)
    return gethash(msg3)

def CreateSIPAuthorization(realm,username,nonce,response,uri):
    msg = "Authorization: digest realm=\"{}\",".format(realm)
    msg += "username=\"{}\",".format(username)
    msg += "nonce=\"{}\",".format(nonce)
    msg += "uri=\"{}\",".format(uri)
    msg += "cnonce=\"{}\",".format(calculate_cnonce())
    msg += "response=\"{}\",".format(response)
    msg += "\r\n"
    return msg


def CreateRequestHeader(to_ip, sip_port, from_ip, from_port, requesttype, cseq, fromtag, totag, callid, device_id=None):
    msg = ""
    msg += "{} sip:{} SIP/2.0\r\n".format(requesttype, to_ip)
    msg += "Via: SIP/2.0/UDP {}:{};rport\r\n".format(from_ip, from_port) # Branch??
    msg += "To: <sip:{}>".format(to_ip)
    if fromtag is not None:
         msg += ';tag={}'.format(fromtag)
    msg += "\r\n"
    msg += 'From: "microbit" <sip:{}>;tag={}\r\n'.format(from_ip, totag)
    msg += "Call-ID: {}\r\n".format(callid)
    msg += "CSeq: {} {}\r\n".format(cseq, requesttype)
    #msg += "Contact: <sip:@{}:{}>\r\n".format(from_ip,sip_port)
    if requesttype != "INVITE":
        if device_id is None:
            raise Exception("Device_id parameter was not set")
        msg += "Allow: INVITE,ACK,CANCEL,BYE,MESSAGE\r\n"
        msg += "User-Agent: Microbit-1274-{}\r\n".format(device_id)
    return msg


def CreateResponseHeader(to_ip, sip_port, from_ip, responsetype, responsenr, cseq, tag, callid, device_id=None):
    msg = ""
    msg += "SIP/2.0 {} {}\r\n".format(responsenr, responsetype)
    msg += "Via: SIP/2.0/UDP {}:{};rport\r\n".format(to_ip, sip_port)
    msg += "From: \"1258\" <sip:{}>;tag={}\r\n".format(from_ip, tag)
    msg += "To: \"microbit\" <sip:{}>\r\n".format(to_ip)
    msg += "Call-ID: {}\r\n".format(callid)
    msg += "CSeq: {} {}\r\n".format(cseq, responsetype)
    if responsetype != "INVITE":
        if device_id is None:
            raise Exception("Device_id parameter was not set")
        msg += "Allow: INVITE,ACK,CANCEL,BYE,MESSAGE\r\n"
        msg += "User-Agent: Microbit-1274-{}\r\n".format(device_id)
    return msg


def CreateCallMessage(to_ip, sip_port, from_ip, rtp_port, com_port, force_codec):
    callsign = "TESTCALLSIGN"
    msg = "Content-Type: application/sdp\r\n"
    msg += "Contact: <sip:@{}:{}>\r\n".format(to_ip, sip_port)
    msg += "Content-Length: %4d\r\n" # Replace %4d at end with msg length
    msg += "\r\n"
    headlen = len(msg)
    msg += "v=0\r\n"
    msg += "s=SIP CALL\r\n"
    msg += "o=- {} 0 IN IP4 {}\r\n".format(current_time_millis(), callsign)
    msg += "m=audio {} RTP/AVP 100 102\r\n".format(rtp_port)
    msg += "m=data {} UDP\r\n".format(com_port)
    msg += "c=IN IP4 {}:{}\r\n".format(from_ip, rtp_port)
    msg += "a=rtpmap:100 PCMAMB/8000\r\n"
    msg += "a=rtpmap:101 L12MB/8000\r\n"
    msg += "a=rtpmap:102 L16MB/8000\r\n"
    if force_codec:
        msg += "a=ptime:40\r\n"
        msg += "a=jittersize:7\r\n"
        msg += "a=jitterdelay:5\r\n"
        msg += "a=dualrx:0\r\n"
    msg = msg.replace("%4d",str(len(msg)-headlen))
    return msg
    

class SipResponse(object):
    def __init__(self, data):
        self.code = None
        self.text = None
        self.nonce = None
        self.cseq = None
        self.via = None
        self.to = None
        self.callid = None
        self.useragent = None
        self.nonce = None
        self.uri = None
        self.totag = None
        self.contentlength = None
        self.data = data
        self.parse(data)
        
    def parse(self, data):
        lines = data.split(b"\r\n")
        for line in lines:
            if line.startswith(b"SIP/2.0"):
                splat = line.split(b' ')
                self.code = int(splat[1])
                self.text = splat[2]
            if line.startswith(b"Via: SIP/2.0"):
                splat = line.split(b' ')
                self.via = splat[2]
            if line.startswith(b"To:"):
                splat = line.split(b' ')
                self.to = splat[1]
                # The uri is between the <>
                u = self.to.split(b'>')
                u = u[0][1:]
                self.uri = u.decode()
                u = self.to.split(b'tag=')
                u = u[1].strip(b"'")
                self.totag = u.decode()
            if line.startswith(b"Call-ID:"):
                splat = line.split(b' ')
                self.callid = splat[1]
            if line.startswith(b"CSeq:"):
                splat = line.split(b' ')
                self.cseq = splat[1]
            if line.startswith(b"User-Agent:"):
                splat = line.split(b' ')
                self.useragent = splat[1]
            if line.startswith(b"WWW-Authenticate:"):
                splat = line.split(b',')
                for s in splat:
                    s = s.strip(b' ')
                    if s.startswith(b'nonce="'):
                        self.nonce = s[7:-1]
                        self.nonce = self.nonce.decode()
            if line.startswith(b"Content-Length:"):
                splat = line.split(b' ')
                self.contentlength = splat[1]

                             
    def __str__(self):
        return("Response code: {}\nText: {}\n".format(self.code, self.text)+
               "Cseq: {}\n".format(self.cseq)+
               "Via: {}\n".format(self.via)+
               "To: {}\n".format(self.to)+
               "Uri: {}\n".format(self.uri)+
               "To-tag: {}\n".format(self.totag)+
               "Callid: {}\n".format(self.callid)+
               "User-Agent: {}\n".format(self.useragent)+
               "Nonce: {}\n".format(self.nonce)+
               "Content-Length: {}\n".format(self.contentlength)+
               ""
               "\n{}".format(self.data))



class SipHandler():
    """
    Class to keep track of cseq numbers and other relevant data for the SIP communication
    """
    acqcseq = 0
    invitecseq = 0
    infocseq = 0
    
    fromtag = None
    totag = uuid.uuid1().hex
    callid = uuid.uuid1().hex
    
    uri = None # get from first response
    nonce = None # We get nonce from server after first invite
    
    def __init__(self, host, toip, fromip, username, password, realm, sipport, rtpport, deviceid, comport, forcecodeczero):
        self.host = host
        self.toip = toip
        self.fromip = fromip
        self.username = username
        self.password = password
        self.realm = realm
        self.sipport = sipport
        self.rtpport = rtpport
        self.comport = comport
        self.fromport = self.sipport
        self.deviceid = deviceid
        self.forcecodeczero = forcecodeczero
    
    def CreateInviteRequest(self):
        """
        Create initial invite request, used to get the nonce for authorization
        """
        self.invitecseq += 1
        msg = CreateRequestHeader(self.toip, self.sipport, self.fromip, self.fromport, "INVITE", self.invitecseq, self.fromtag, self.totag, self.callid)
        msg += CreateCallMessage(self.toip, self.sipport, self.fromip, self.rtpport, self.comport, self.forcecodeczero)
        return msg

    def CreateAuthorizationRequest(self):
        """
        Create message to login, this time we use username and passowrd hashed in "response"
        """
        self.invitecseq += 1
        msg = CreateRequestHeader(self.toip, self.sipport, self.fromip, self.fromport, "INVITE", self.invitecseq, self.fromtag, self.totag, self.callid)
        authresponse = calculate_response(self.username, self.realm, self.password, self.uri, self.nonce)
        msg += CreateSIPAuthorization(self.realm,self.username,self.nonce,authresponse,self.uri)
        msg += CreateCallMessage(self.toip, self.sipport, self.fromip, self.rtpport, self.comport, self.forcecodeczero)
        return msg

    def CreateACK(self):
        """
        Create an acknoledgment package
        """
        msg = CreateRequestHeader(self.toip, self.sipport, self.fromip, self.fromport, "ACK", self.acqcseq, self.fromtag, self.totag, self.callid, self.deviceid)
        msg += "\r\n"
        return msg

    def CreateStatusMsg(self):
        """
        Create a status message after the ringing has begun
        """
        msg = CreateResponseHeader(self.toip, self.sipport, self.fromip, "OK", 200, self.infocseq, self.fromtag, self.callid, self.deviceid)
        msg += "\r\n"
        return msg
        
    def CreateByeMsg(self):
        """
        Send a bye message when we quit, I believe this will make the remote site close the transmission.
        """
        msg = CreateRequestHeader(self.toip, self.sipport, self.fromip, self.fromport, "BYE", self.acqcseq, self.fromtag, self.totag, self.callid, self.deviceid)
        msg += "\r\n"
        return msg

