#!/usr/bin/env python
#
# The MIT License (MIT)
#
# Copyright (c) 2019 Matthias P. Braendli, Maximilien Cuony
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


from twx.botapi import TelegramBot
import threading
import time
import os
import datetime


import config


class Monitor(threading.Thread):

    def __init__(self, ser):
        threading.Thread.__init__(self)

        self.ser = ser
        self.reset_states()

    def reset_states(self):

        self.current_state = None
        self.status_starttime = {}
        self.status_duration = {}
        self.last_gps_balise = None
        self.last_message = None
        self.last_balise = None
        self.reseted = False
        self.hoho_message = None

    def run(self):

        queue = self.ser.register_client()

        while True:

            try:
                line = queue.popleft()
            except IndexError:
                time.sleep(1)
                line = None

            if line:
                line = line.strip()

                self.last_message = datetime.datetime.now()

                if line.endswith("common init"):
                    self.reset_states()
                    self.reseted = True

                if "[HOHO]" in line:
                    self.hoho_message = line

                if "T_GPS" in line:
                    self.last_gps_balise = datetime.datetime.now()

                if "FSM: FSM_" in line:
                    new_state = line.split(' ')[-1]

                    if self.current_state:
                        self.status_duration[self.current_state] = datetime.datetime.now() - self.status_starttime[self.current_state]

                    self.status_starttime[new_state] = datetime.datetime.now()
                    self.current_state = new_state

                if "FSM: FSM_BALISE_LONGUE" in line or \
                        "FSM: FSM_BALISE_SPECIALE" in line or \
                        "FSM: FSM_BALISE_STATS1" in line or \
                        "FSM: FSM_BALISE_SPECIALE_STATS1" in line:
                    self.last_balise = datetime.datetime.now()

    def alarms(self):

        MAXIMUM_STATES = {
            'FSM_OISIF': (10800, '3 hours'),
            'FSM_OPEN1': (120, '2 minutes'),
            'FSM_OPEN2': (120, '2 minutes'),
            'FSM_LETTRE': (120, '2 minutes'),
            'FSM_ECOUTE': (120, '2 minutes'),
            'FSM_ATTENTE': (120, '2 minutes'),
            'FSM_QSO': (1800, '30 minutes'),
            'FSM_ANTI_BAVARD': (120, '2 minutes'),
            'FSM_BLOQUE': (120, '2 minutes'),
            'FSM_TEXTE_73': (120, '2 minutes'),
            'FSM_TEXTE_HB9G': (120, '2 minutes'),
            'FSM_TEXTE_LONG': (120, '2 minutes'),
            'FSM_BALISE_LONGUE': (120, '2 minutes'),
            'FSM_BALISE_STATS1' : (120, '2 minutes'),
            'FSM_BALISE_STATS2' : (120, '2 minutes'),
            'FSM_BALISE_STATS3' : (120, '2 minutes'),
            'FSM_BALISE_SPECIALE': (120, '2 minutes'),
            'FSM_BALISE_SPECIALE_STATS1' : (120, '2 minutes'),
            'FSM_BALISE_SPECIALE_STATS2' : (120, '2 minutes'),
            'FSM_BALISE_SPECIALE_STATS3' : (120, '2 minutes'),
            'FSM_BALISE_COURTE': (120, '2 minutes'),
            'FSM_BALISE_COURTE_OPEN': (120, '2 minutes'),
        }

        result = []

        if self.reseted:
            result.append("(AutoAckedError) A reset occured !")
            self.reseted = False

        if self.hoho_message:
            result.append("(AutoAckedError) An error message was found in the UART: {}".format(self.hoho_message))
            self.hoho_message = None

        if self.last_message and (datetime.datetime.now() - self.last_message).total_seconds() > 300:
            result.append("No message on UART for more than 5 minutes !")

        if self.last_gps_balise and (datetime.datetime.now() - self.last_gps_balise).total_seconds() > 300:
            result.append("No GPS for more than 5 minutes !")

        if self.last_balise and (datetime.datetime.now() - self.last_balise).total_seconds() > 10800:
            result.append("No long balise for more than 3 hours !")

        if self.current_state and self.current_state in MAXIMUM_STATES and (datetime.datetime.now() - self.status_starttime[self.current_state]).total_seconds() > MAXIMUM_STATES[self.current_state][0]:
            result.append("The FSM has been in the state {} for more than {} !".format(self.current_state, MAXIMUM_STATES[self.current_state][1]))

        return result


class ADSL(threading.Thread):

    def __init__(self, ser):
        threading.Thread.__init__(self)
        self.monitor = Monitor(ser)
        self._ser = ser

    def run(self):

        self.monitor.start()

        alarms = []

        if not config.TELEGRAM_API_TOKEN or not config.TELEGRAM_GROUP:
            print("Telegram not configured, ADSL not running.")
            return

        bot = TelegramBot(config.TELEGRAM_API_TOKEN)
        bot.update_bot_info().wait()
        print("Telegram bot {} ready".format(bot.username))

        offset = None

        bot.send_message(config.TELEGRAM_GROUP, b'\xe2\x84\xb9 Hello ! I have been started, so everything has been reset on my side.'.decode()).wait()

        while True:

            updates = bot.get_updates(offset=offset, limit=1, timeout=15).wait()
            if updates:
                offset = updates[0].update_id + 1

                try:
                    if int(updates[0].message.chat.id) == int(config.TELEGRAM_GROUP):
                        if updates[0].message.text.startswith('/status'):
                            response = "Here is the current status:\n\n"

                            response += "Current state: {}\n".format(self.monitor.current_state)
                            if self.monitor.last_message:
                                response += "Last message: {} ({} seconds ago)\n".format(self.monitor.last_message.strftime("%H:%M:%S %d/%m/%Y"), int((datetime.datetime.now() - self.monitor.last_message).total_seconds()))
                            if self.monitor.last_gps_balise:
                                response += "Last GPS: {} ({} seconds ago)\n".format(self.monitor.last_gps_balise.strftime("%H:%M:%S %d/%m/%Y"), int((datetime.datetime.now() - self.monitor.last_gps_balise).total_seconds()))
                            if self.monitor.last_balise:
                                response += "Last Balise: {} ({} seconds ago)\n".format(self.monitor.last_balise.strftime("%H:%M:%S %d/%m/%Y"), int((datetime.datetime.now() - self.monitor.last_balise).total_seconds()))

                            response += "\n"

                            for state, starttime in self.monitor.status_starttime.items():
                                response += "{}: Started on {} ({} seconds ago)".format(state, starttime.strftime("%H:%M:%S %d/%m/%Y"), int((datetime.datetime.now() - starttime).total_seconds()))

                                if state == self.monitor.current_state:
                                    response += ", in progress\n"
                                else:
                                    response += ", duration: {} seconds\n".format(int(self.monitor.status_duration[state].total_seconds()))

                            bot.send_message(config.TELEGRAM_GROUP, response).wait()

                        elif updates[0].message.text.startswith('/stats'):
                            t_now = time.time()
                            values = ser.get_parsed_values()

                            stats_lines = ["Stats:"]

                            for k in values:
                                value, ts = values[k]
                                since = t_now - ts
                                stats_lines.append(f"{k}: {value} since {since}s")
                            bot.send_message(config.TELEGRAM_GROUP, "\n".join(stats_lines)).wait()


                        elif updates[0].message.text.startswith('/reboot'):
                            os.system(config.TELEGRAM_REBOOT_COMMAND)
                            bot.send_message(config.TELEGRAM_GROUP, b'\xe2\x84\xb9 I issued a reboot command. I hope everything is ok.'.decode()).wait()
                    else:
                        print(f"Ignore chat ID {updates[0].message.chat.id}")
                except:
                    pass

            new_alarms = self.monitor.alarms()

            for alarm in new_alarms:
                if alarm not in alarms:
                    bot.send_message(config.TELEGRAM_GROUP, b'\xe2\x9a\xa0 Problem \xe2\x9a\xa0\nSorry to bother you, but I think there is a problem with the glutt-o-matique: \n\n{}'.decode().format(alarm)).wait()

            for old_alarm in alarms:
                if old_alarm not in new_alarms:
                    bot.send_message(config.TELEGRAM_GROUP, b'\xe2\x9c\x85 Problem fixed \xe2\x9c\x85\nThe following problem is not anymore a problem with the glutt-o-matique:\n\n{}'.decode().format(old_alarm)).wait()

            alarms = new_alarms

            time.sleep(1)
