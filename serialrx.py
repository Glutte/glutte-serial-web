#!/usr/bin/env python
#
# The MIT License (MIT)
#
# Copyright (c) 2020 Matthias P. Braendli, Maximilien Cuony
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
import re
import time

import config

re_cc_capa = re.compile(r"\[\d+\] CC: CAPA,\d+,(\d+)")
re_cc_vbat_plus = re.compile(r"\[\d+\] CC: VBAT\+,\d+,(\d+)")
re_num_sv = re.compile(r"\[\d+\] T_GPS.+ (\d+) SV tracked")
re_alim = re.compile(r"\[\d+\] ALIM (\d+) mV")
re_temp = re.compile(r"\[\d+\] TEMP ([+-]?[0-9.]+)")
re_relay = re.compile(r"\[\d+\] CC: RELAY,\d+,(On|Off),(On|Off),(On|Off)")

class MessageParser:
    def __init__(self):
        self._lock = threading.Lock()

        self._last_cc_capa = 0
        self._last_cc_capa_time = 0
        self._last_vbat_plus = 0
        self._last_vbat_plus_time = 0
        self._last_num_sv = 0
        self._last_num_sv_time = 0
        self._last_alim = 0
        self._last_alim_time = 0
        self._last_temp = 0
        self._last_temp_time = 0
        self._last_relay = (False, False, False)
        self._last_relay_time = 0

    def parse_message(self, message):
        with self._lock:
            match = re_cc_capa.search(message)
            if match:
                self._last_cc_capa = int(match.group(1))
                self._last_cc_capa_time = time.time()

            match = re_cc_vbat_plus.search(message)
            if match:
                self._last_vbat_plus = int(match.group(1))
                self._last_vbat_plus_time = time.time()

            match = re_num_sv.search(message)
            if match:
                self._last_num_sv = int(match.group(1))
                self._last_num_sv_time = time.time()

            match = re_alim.search(message)
            if match:
                self._last_alim = int(match.group(1))
                self._last_alim_time = time.time()

            match = re_temp.search(message)
            if match:
                self._last_temp = float(match.group(1))
                self._last_temp_time = time.time()

            match = re_relay.search(message)
            if match:
                self._last_relay = (match.group(1) == "On", match.group(2) == "On", match.group(3) == "On")
                self._last_relay_time = time.time()

    def get_last_data(self):
        with self._lock:
            return {"capa": (self._last_cc_capa, self._last_cc_capa_time),
                    "vbat_plus": (self._last_vbat_plus, self._last_vbat_plus_time),
                    "alim": (self._last_alim, self._last_alim_time),
                    "num_sv": (self._last_num_sv, self._last_num_sv_time),
                    "temp": (self._last_temp, self._last_temp_time),
                    "relay": (self._last_relay, self._last_relay_time)}

class SerialRX(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        self._parser = MessageParser()

        print("Open Serial on {} at {}".format(config.SERIALPORT, config.BAUDRATE))
        self.ser = serial.Serial(config.SERIALPORT, baudrate=config.BAUDRATE)

        self.event_stop = threading.Event()

        self.data_lock = threading.Lock()
        self.clients = []

        self.line_accumulator = []
        self.last_lines = []

        print("Serial port ready")

    def get_parsed_values(self):
        return self._parser.get_last_data()

    def run(self):
        print("Serial port starting reception")
        while not self.event_stop.is_set():
            databyte = self.ser.read()
            self.line_accumulator.append(databyte)

            if databyte == "\n":
                line = "".join(self.line_accumulator)
                self._parser.parse_message(line)
                self.data_lock.acquire()
                try:
                    for queue in self.clients:
                        queue.append(line)

                        if len(queue) > config.LINES_TO_KEEP:
                            queue.popleft()

                    self.last_lines.append(line)

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
            self.clients = filter(lambda x: id(x) != id(queue), self.clients)
        except:
            raise
        finally:
            self.data_lock.release()

if __name__ == "__main__":
    test_set = """[193583144] CW: K
    [193583168] In cw_done change 0 0
    [193584056] FSM: FSM_ECOUTE
    [193585992] In SQ 1
    [193586008] FSM: FSM_QSO
    [193592816] CC: CAPA,148111,1632707
    [193605944] CC: CAPA,148121,1632682
    [193605944] CC: VBAT+,148121,12340
    [193605944] CC: VBAT-,148121,0
    [193612144] ALIM 11811 mV
    [193672600] T_GPS 2020-04-28 19:07:30 12 SV tracked
    [193672656] TIME  2020-04-28 21:07:30 [GPS]
    [233465736] TEMP 0.75
    [193692528] TEMP invalid
    [102976] CC: RELAY,721,On,Off,Off
    """
    test_should = { "capa": 1632682, "vbat_plus": 12340, "alim": 11811, "num_sv": 12, "temp" : 0.75,
            "relay" : (True, False, False)}

    mp = MessageParser()

    print("Testing parser")
    for message in test_set.split("\n"):
        print("Parse {}".format(message))
        mp.parse_message(message)

    test_measured = mp.get_last_data()

    for k in test_measured:
        if test_measured[k][1] == 0:
            print("Value {} has time 0".format(k))

    values = {k: test_measured[k][0] for k in test_measured}
    if values != test_should:
        print("invalid values {}".format(values))

    print("Test end")
