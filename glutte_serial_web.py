#!/usr/bin/env python3
#
# The MIT License (MIT)
#
# Copyright (c) 2022 Matthias P. Braendli, Maximilien Cuony
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

import time
import json
from geventwebsocket.handler import WebSocketHandler
from gevent import pywsgi, Timeout
from flask import Flask, Response, render_template, jsonify
from flask_sockets import Sockets
import serialrx
import adsl
import config

app = Flask(__name__)
sockets = Sockets(app)

ser = serialrx.SerialRX()
adsl = adsl.ADSL(ser)

@app.route('/')
def index():
    return render_template('index.html', last_lines=ser.get_last_lines())

@app.route('/history')
def history():
    hist = []
    if config.CACHE_FILE:
        with open(config.CACHE_FILE) as fd:
            hist = json.load(fd)
    text = "\n".join(f"{entry['ts'].isoformat()} {entry['line']}" for entry in hist)
    return Response(text, mimetype='text/plain')

@app.route('/stats')
def stats():
    t_now = time.time()
    values = ser.get_parsed_values()

    out_json = {}

    for k in values:
        value, ts = values[k]
        if ts + 60 < t_now:
            out_json[k] = None
        else:
            out_json[k] = value

    return jsonify(out_json)

@sockets.route('/stream')
def stream(socket):
    try:
        queue = ser.register_client()
        error = False

        while not socket.closed and not error:
            # Force to check if the client is still here
            try:
                with Timeout(0.1, False):
                    socket.receive()
            except:
                pass
            try:
                line = queue.popleft()
                socket.send(line)
            except IndexError:
                pass
            except:
                error = True
            time.sleep(0.1)
    except:
        raise
    finally:
        ser.unregister_client(queue)

ser.start()
adsl.start()

if __name__ == "__main__":
    print("You're running in dev mode, only one client at a time will works ! Please use gunicorn to fix this :)")
    try:
        http_server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
        http_server.serve_forever()
    except KeyboardInterrupt:
        print("Ctrl-C received, quitting")
    finally:
        ser.stop()
