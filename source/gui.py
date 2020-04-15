#!/usr/bin/python3
import logging
import os
import json

from flask import Flask, request, Response, render_template, redirect, current_app
from threading import Thread
from source.log import *
from source import ensa

flog = logging.getLogger('werkzeug')
#flog.setLevel(logging.ERROR)

class GUI(Thread):
    app = Flask(__name__, root_path=os.path.join(os.getcwd(), 'gui'))
    def __init__(self):
        Thread.__init__(self)
        
    def run(self):
        #ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        #ssl_context.load_cert_chain(certfile=..., keyfile=...)
        #app.run('127.0.0.1', port=8111, ssl_context=ssl_context, use_reloader=False)
        GUI.app.config['TEMPLATES_AUTO_RELOAD'] = True
        GUI.app.run('127.0.0.1', port=8111, use_reloader=False)

@GUI.app.route('/get_subjects/<ring>')
def get_subjects(ring):
    return json.dumps(ensa.db.get_subjects(ring=int(ring)))

@GUI.app.route('/get_locations/<ring>')
def get_locations(ring):
    return json.dumps(ensa.db.get_locations(ring=int(ring)))

@GUI.app.route('/get_times/<ring>')
def get_times(ring):
    return json.dumps(ensa.db.get_times(ring=int(ring)))

@GUI.app.route('/get_associations/<ring>')
def get_associations(ring):
    return json.dumps(ensa.db.get_associations(ring=int(ring)))


@GUI.app.route('/')
def gui_index():
    #return '<html><body><h1>It works!</h1></body></html>'
    return render_template('index.html', 
                           rings=json.dumps(ensa.db.get_rings()),
                          )


