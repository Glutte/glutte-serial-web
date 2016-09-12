#!/usr/bin/env python
#
# The MIT License (MIT)
#
# Copyright (c) 2016 Matthias P. Braendli, Maximilien Cuony
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

import serial
import threading
import collections

import config


class SerialRX(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

        print("Open Serial on {} at {}".format(config.SERIALPORT, config.BAUDRATE))
        self.ser = serial.Serial(config.SERIALPORT, baudrate=config.BAUDRATE)

        self.event_stop = threading.Event()

        self.data_lock = threading.Lock()
        self.clients = []

        self.line_accumulator = []
        self.last_lines = []

        print("Serial port ready")

    def run(self):
        print("Serial port starting reception")
        while not self.event_stop.is_set():
            databyte = self.ser.read()
            self.line_accumulator.append(databyte)

            if databyte == "\n":
                self.data_lock.acquire()
                try:

                    for queue in self.clients:
                        queue.append("".join(self.line_accumulator))

                        if len(queue) > config.LINES_TO_KEEP:
                            queue.popleft()

                    self.last_lines.append("".join(self.line_accumulator))

                    if len(self.last_lines) > config.LAST_LINE_TO_KEEP:
                        self.last_lines.pop(0)

                except:
                    raise
                finally:
                    self.data_lock.release()
                self.line_accumulator = []

    def stop(self):
        self.event_stop.set()
        self.join()

    def get_last_lines(self):
        return self.last_lines

    def register_client(self):
        self.data_lock.acquire()
        try:
            new_queue = collections.deque()
            self.clients.append(new_queue)
        except:
            raise
        finally:
            self.data_lock.release()

        return new_queue

    def unregister_client(self, queue):
        self.data_lock.acquire()
        try:
            self.clients.remove(queue)
        except:
            raise
        finally:
            self.data_lock.release()
