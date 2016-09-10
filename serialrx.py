#!/usr/bin/env python
#
# The MIT License (MIT)
#
# Copyright (c) 2016 Matthias P. Braendli
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

from time import sleep
import serial
import threading
import collections

SERIALPORT="/dev/ttyACM0"
BAUDRATE=9600
LINES_TO_KEEP=200

class SerialRX(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        print("Open Serial on {} at {}".format(SERIALPORT, BAUDRATE))
        self.ser = serial.Serial(SERIALPORT, baudrate=BAUDRATE)

        self.event_stop = threading.Event()

        self.data_lock = threading.Lock()
        self.data_queue = collections.deque()

        self.line_accumulator = []

        print("Serial port ready")

    def run(self):
        print("Serial port starting reception")
        while not self.event_stop.is_set():
            databyte = self.ser.read()
            self.line_accumulator.append(databyte)

            if databyte == "\n":
                self.data_lock.acquire()
                try:
                    self.data_queue.append("".join(self.line_accumulator))

                    if len(self.data_queue) > LINES_TO_KEEP:
                        self.data_queue.popleft()
                except:
                    raise
                finally:
                    self.data_lock.release()
                self.line_accumulator = []


    def stop(self):
        self.event_stop.set()
        self.join()

    def get_line(self):
        try:
            return self.data_queue.popleft()
        except IndexError:
            return None

