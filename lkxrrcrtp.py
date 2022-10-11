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
#from queue import Queue
# faster_fifo is probably not needed
from faster_fifo import Queue
import logging
import struct

import numpy as np

import g711
import sounddevice

DEBUG = False

def ParseRtpHeader(data):
    """
    This can be pretty much decoded by looking at the
    information in wireshark, but I'm not sure how to use
    it right now anyway...
    """
    header = struct.unpack('>bbhiihh',data)
    firstbyte = header[0]
    secondbyte = header[1]
    sequence = header[2] # This keeps iterating to higher numbers
    sequence2 = header[3] # Maybe a timestamp??
    something0 = header[4]
    something1 = header[5]
    something2 = header[6]
    #print(header) # Print to look at it, but who knows what to do with it?




def CreateRtpHeader(ptt,sequencenr, codec):
    header = b""
    # Lots of RFC things goes into first bytes
    # Check wireshark for more
    header += b"\x80" # First byte
    if codec == 0:
        header += b"\x64" # Marker and payload type
    if codec == 2:
        header += b"\x66" # Aaah seems to be condec number here
    sequence = struct.pack('>h',sequencenr)
    header += sequence
    # Figure out RFC timestaamp, what should we put?
    timestamp = struct.pack('>i', sequencenr*324)
    header += timestamp
    # Now we add the synchronization source identifier
    # No clue what that is
    header += b"\x28\x0e\x5c\x1b"
    # Finally the real RTP header is done
    # Now comes the RFC 2833 RTP Event
    # Add event id dtmf zero 0
    header += b"\x00"
    if ptt is True:
        # This is really important!
        header += b"\x82"
    else:
        header += b"\x80"
    # Lets add event duration
    header += b"\x40\x01"
    return header
    

class RtpHandler():
    """
    Class that takes care of everything relevant to the rtp messages
    """
    samplerate = 8000
    remoteframesize = 320
    localframesize = 320
    rtpsequencenumber = 0
    audioqueue = Queue()
    micqueue = Queue()
    outputstarted = False
    currentlyrecording = False

    def __init__(self, remotecodec, localcodec):
        self.remotecodec = remotecodec
        self.localcodec = localcodec
        if localcodec == 2:
            self.localframesize = 160
        if remotecodec == 2:
            self.remoteframesize = 160

    def OpenAudio(self):
        """
        Create the audio streams so that we can read/write later
        """
        logging.debug("Opening audio")
        #self.audiostream = sounddevice.OutputStream(samplerate=self.samplerate, blocksize=self.remoteframesize,
        #                                    channels=1, dtype='float32', callback=self.audiocallback)
        #self.recordstream = sounddevice.InputStream(samplerate=self.samplerate, blocksize=self.localframesize,
        #                                    channels=1, dtype='float32', callback=self.recordcallback)
        self.audiostream = sounddevice.Stream(samplerate=self.samplerate, blocksize=self.remoteframesize, channels=1, dtype='float32', callback=self.audiocallback)

        logging.debug("Audio stream are created")


    def StartRecording(self):
        """
        Grab sound from the microphone
        """
        #self.audiostream.abort()
        #self.recordstream.start()
        self.currentlyrecording = True

    def StopRecording(self):
        """
        Stop grabbing sound from the microphone
        """
        #self.recordstream.abort()
        #self.audiostream.start()
        self.currentlyrecording = False

    def CloseAudio(self):
        """
        Properly close the audio
        """
        logging.debug("Closing audio")
        self.audiostream.stop()
        self.audiostream.close()
        #self.recordstream.stop()
        #self.recordstream.close()

    def DecodeAudio(self, audiobytes):
        if self.remotecodec == 0:
            decoded = g711.decode_alaw(audiobytes)
        elif self.remotecodec == 2:
            # This is linear 16 pcm 8KHz
            decoded = np.frombuffer(audiobytes, dtype=np.int16)
            decoded = decoded.astype(np.float32)/32767
        else:
            raise NotImplementedError("The selected codec is not implemented")
        return decoded

    def EncodeAudio(self, audionumbers):
        if self.localcodec == 0:
            encoded = g711.encode_alaw(audionumbers)
        elif self.localcodec == 2:
            encoded =  (audionumbers * 32767).astype(np.int16)
            encoded = encoded.tobytes()
        else:
            raise NotImplementedError("The selected codec is not implemented")
        return encoded

    def HandleRtpData(self, data):
        """
        Incoming RTP packets from remote site,
        take care of them properly
        """
        header = data[:16]
        # Well i'm not using the header, so no need to parse it right now
        #ParseRtpHeader(header)
        audiodata = self.DecodeAudio(data[16:]) # 16 first bytes is not audio
        # Reshape it to fit sounddeviec
        audiodata = np.reshape(audiodata, (self.remoteframesize,1))
        #if not self.currentlyrecording:
        #    # Todo maybe add this back later
        #    # Don't put on queue if we are recording
        #    # Then we just skip the data
        self.audioqueue.put(audiodata)
        if self.outputstarted == False:
            # Don't start playing audio before we get the first package
            self.audiostream.start()
            #self.recordstream.start()
            self.outputstarted = True

    def CreateRtpMsg(self, ptt):
        # When switching to PTT on,
        # The remoterig hardware first sends one packaccge with PTT off
        # Perhaps this is the help get som data into the buffer on the
        # remote side, before starting transmission.
        startbytes = CreateRtpHeader(ptt,self.rtpsequencenumber, self.localcodec)
        self.rtpsequencenumber += 1
        if self.rtpsequencenumber > 32767:
            self.rtpsequencenumber = 0
        if not self.micqueue.empty():
            voice = self.micqueue.get()
        else:
            print("Creating an empty voice message")
            voice = np.zeros(self.localframesize, dtype=np.float32)
        encoded = self.EncodeAudio(voice)
        return startbytes+encoded
    
    def audiocallback(self, indata, outdata, frames, timec, status):
        """
        This is called from pyaudio, feed it new data if we have
        """
        if self.currentlyrecording:
            self.micqueue.put(np.copy(indata))
        if not self.currentlyrecording:
            while not self.micqueue.empty():# self.micqueue.qsize() > 4:
                # Let's the last 4 packages in memory, ready to send
                self.micqueue.get()
        #self.micqueue.put(np.copy(indata))
        while self.audioqueue.qsize() > 4 and not DEBUG:
            # let's empty it a bit
            self.audioqueue.get()
        if self.audioqueue.empty():
            # No data is ready
            # Send some zeroes to the audio output, otherwise it
            # Creates a horrible noise
            outdata[:] = np.zeros((self.remoteframesize,1), dtype=np.float32)
        else:
            # Give the data to soundcard
            outdata[:] = self.audioqueue.get()



        
if __name__ == "__main__":
    # Simple test that records a few seconds and then plays them back...
    # Note we drop buffer in audiocallback, so need to change that again
    # to test it
    DEBUG = True
    r = RtpHandler(2,2)
    r.OpenAudio()
    r.audiostream.start()
    r.CreateRtpMsg(True)
    r.StartRecording()
    print("Start speaking now")
    starttime = time.time()
    while time.time() < starttime+5:
        pass
    print("Recording stopped, starting playback")
    print(r.micqueue.qsize())
    r.StopRecording()
    starttime = time.time()
    r.audiostream.start()
    while time.time() < starttime+5:
        time.sleep(5e-3)
        dat = r.micqueue.get()
        encoded = r.EncodeAudio(dat)
        decoded = r.DecodeAudio(encoded)  
        decoded = np.reshape(decoded, (r.remoteframesize,1)) 
        r.audioqueue.put(decoded)
    print(encoded)

