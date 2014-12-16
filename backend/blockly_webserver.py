#!/usr/bin/env python
"""
Blocky Talky - Upload (upload.py)

This script is needed for the Blocky code to run on the Pi.

Authorization is based on:
    Coder auth app
    Flask Bcrypt - pythonhosted.org/Flask-Bcrypt/
    Flask HTTP Basic Auth - flask.pocoo.org/snippets/8/
"""

import os
import sys
import logging
import logging.handlers
from functools import wraps
from flask import Flask, request, Response, redirect, url_for, render_template
from flask.ext.bcrypt import Bcrypt
from message import *
import time, commands, subprocess, pika
import jsonpickle
import requests
import socket

app = Flask(__name__)
bcrypt = Bcrypt(app)
logger = logging.getLogger(__name__)
device_settings = {
        'password_hash': '',
        'device_name': '',
        'hostname': '',
        'coder_owner': '',
        'coder_color': ''
        }

#app.debug = True

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='HwCmd', type='fanout')
result = channel.queue_declare(exclusive=True)
queue_name = result.method.queue

channel.queue_bind(exchange='HwCmd', queue=queue_name)

toSend = Message('name', None, 'HwCmd', Message.createImage(motor1=0, motor2=0, motor3=0, motor4=0, pin13=0))
toSend = Message.encode(toSend)

upMsg = Message('name', None, 'HwCmd', Message.createImage(pin13=1))
upMsg = Message.encode(upMsg)
channel.basic_publish(exchange='HwCmd', routing_key='', body=upMsg)

os.chdir('/home/pi/blockytalky')

max_retries = 5

# def load_device_settings():
#     try:
#         json_file = open('/home/coder/coder-dist/coder-base/device.json', 'r')
#         device_json = jsonpickle.decode(json_file.read())
#         device_settings = {
#                 'password_hash': device_json['password_hash'],
#                 'device_name': device_json['device_name'],
#                 'hostname': device_json['hostname'],
#                 'coder_owner': device_json['coder_owner'],
#                 'coder_color': device_json['coder_color']
#                 }
#         json_file.close()
#     except Exception as e:
#         logger.exception('Failed to open device settings file:')
#     return device_settings

# def requires_auth(f):
#     @wraps(f)
#     def decorated(*args, **kwargs):
#         auth = request.authorization
#         if not auth or not check_auth(auth.username, auth.password):
#             logger.info('Incorrect login attempt')
#             return authenticate()
#         return f(*args, **kwargs)
#     return decorated

# def check_auth(username, password):
#     return (username == device_settings['device_name'] and
#             bcrypt.check_password_hash(device_settings['password_hash'], password))

def restart_comms_module():
    cmd = ['sudo python /home/pi/blockytalky/backend/comms_module.py']
    try:
        subprocess.call(['sudo pkill -15 -f comms_module.py'], shell = True)
        try:
            subprocess.Popen(cmd, shell = True)
        except Exception as e:
            logger.exception('Failed to start comms_module back up')
    except Exception as e:
        logger.exception('Failed to terminate communication module. Trying again more forcefully:')
        try:
            subprocess.call(['sudo pkill -9 -f comms_module.py'], shell =True)
            try:
                subprocess.Popen(cmd, shell = True)
            except Exception as e:
                logger.exception('Failed to start comms_module back up')
        except Exception as e:
            logger.exception('Failed to terminate communication module:')

def stop_user_script():
    try:
        subprocess.call(['sudo pkill -15 -f user_script.py'], shell = True)
    except Exception as e:
        logger.exception('Failed to stop Blockly code, trying again more forcefully:')
        try:
            subprocess.call(['sudo pkill -9 -f user_script.py'], shell = True)
        except:
            logger.exception('Failed to stop Blockly code:')

def retry_request(request=None, num_tries=0, action='complete request', *args, **kwargs):
    max_retries = 5
    wait_time = 3
    if num_tries < 0:
        num_tries = 0

    try:
        if num_tries == 0:
            logger.exception('Failed to %; restarting communication module and trying again (try #1):' % action)
        elif num_tries < max_retries:
            logger.exception('Failed to %; restarting communication module and trying again in %d seconds (try #%d):'
                             % (action, wait_time, num_tries + 1))
            time.sleep(wait_time)
        num_tries += 1
        restart_comms_module()
        request(num_tries=num_tries, *args, **kwargs)
    except Exception as e:
        retry_request(request=request, num_tries=num_tries, action=action, *args, **kwargs)

@app.route('/', methods = ['GET'])
def index():
    return render_template('index.html')

@app.route('/blockly', methods = ['GET','POST'])
#@requires_auth
def blockly():
    startMsg = Message('name', None, 'HwCmd', Message.createImage(pin13=0))
    startMsg = Message.encode(startMsg)
    try:
        channel.basic_publish(exchange='HwCmd', routing_key='', body=startMsg)
    except:
        logger.exception('Failed to start Blockly:')
    return render_template('code.html')

@app.route('/upload', methods = ['GET', 'POST'])
#@requires_auth
def upload():
    startTime = None
    endTime = None
    if request.method == 'POST':
        logger.info('Uploading code')
        data = request.form.copy()
        xml_data = data['xml']
        python_data = data['python']
        upload_code(xml_data, python_data);
        logger.info('Blockly code uploaded')
        return 'OK'

def code_to_file(code, file_name, file_label):
    logger.debug('Writing %s code:\n%s\n\n' % (file_name, code))
    startTime = time.time()
    fo = open(file_name, 'wb')
    fo.write(code)
    fo.close()
    endTime = time.time()
    logger.info('%s file took %fs' % (file_label, endTime - startTime))

def upload_code(xml_data, python_data):
    uploadStart = time.time()
    code_to_file(xml_data, 'code/rawxml.txt', 'XML')
    #code_to_file(convert_usercode(python_data), 'backend/usercode.py', 'Python')
    code_to_file(convert_usercode(python_data), 'backend/user_script.py', 'Python')
    save_locally(xml_data)
    startTime = time.time()
    logger.info('Issuing kill command before uploading code')
    stop_user_script()
    endTime = time.time()
    logger.debug('Subprocess pt1 took '+ str(endTime - startTime) + ' s')

    logger.info('Upload took '+ str(time.time() - uploadStart) + ' s')

def save_locally(code):
    os.chdir('/home/pi/blockytalky/usercode')
    filename = socket.gethostname() + "-" + str(int(round(time.time() * 1000)))
    fo = open(filename, 'wb')
    fo.write(code)
    fo.close()
    os.chdir('/home/pi/blockytalky')


def convert_usercode(python_code):
    # Need to use two-space tabs for consistency with Blockly conversion
    python_code = "\n%s" % python_code
    python_code += "\n"
    python_code = python_code.splitlines()
    callback_functions = "    def init_callbacks(self): \n"
    while_functions = "    def init_whiles(self): \n"
    msg_functions = "    def init_msgs(self): \n"
    variables = "\n      global "

    # comment out code that comes from blocks not in event blocks.
    comment = True
    i = 0
    while i < len(python_code):
        if python_code[i].isspace() or python_code[i] == "":
            comment = False
        elif python_code[i][-7:] == " = None":
            comment = False
            var = python_code[i][:python_code[i].index('=')-1]
            variables += var + ", "

        elif python_code[i][:4] == "def ":
            func = python_code[i][python_code[i].find(" ")+1:python_code[i].find("(")]
            if func[0] != "_":
                if variables != "\n      global ":
                    python_code[i] += variables[:-2]
                if func == "run_continuously":
                    python_code[i] += "\n      for f in self.whiles: \n        f() \n"
                if func[:2] == "wl":
                    while_functions += "        self.whiles.append(self." + func + ") \n"
                if func[:2] == "wm":
                    msg_functions += "        self.msg_functions.append(self." + func + ") \n"
                else:
                    callback_functions += "        self.callbacks.append(self." + func + ") \n"
            comment = False
            while not (python_code[i].isspace() or python_code[i] == ""):
                i += 1
        else:
            comment = True

        if comment == True:
            python_code[i] = "#" + python_code[i]
        i += 1

    python_code = ["    " + x for x in python_code]
    python_code = "\n".join(python_code)

    callback_functions += "        if self.run_on_start in self.callbacks: self.callbacks.remove(self.run_on_start) \n        if self.run_continuously in self.callbacks: self.callbacks.remove(self.run_continuously) \n"

    while_functions += "        True \n"

    msg_functions += "        True \n"

    python_code += "\n" + callback_functions + "\n" + while_functions + "\n" + msg_functions + "\n"

    print python_code

    user_script_header = open('backend/us_header', 'r')
    header_text = user_script_header.read()

    footer_text = ('if __name__ == "__main__": \n'
                   '    handle_logging(logger) \n'
                   '    uscript = UserScript() \n'
                   '    uscript.handshake() \n'
                   '    uscript.start() \n')


    return header_text + python_code + footer_text

@app.route('/stop', methods = ['GET', 'POST'])
#@requires_auth
def stop():
    logger.info('Issuing kill command')
    stop_user_script()
    toSend = Message('name', None, 'HwCmd', Message.createImage(motor1=0, motor2=0, motor3=0, motor4=0, pin13=0))
    toSend = Message.encode(toSend)
    try:
        channel.basic_publish(exchange='HwCmd', routing_key='', body=toSend)
    except:
        logger.exception('Failed to stop Blockly code:')
    return 'OK'

def update_sensors(sensors, num_tries=0):
    try:
        assert len(sensors) == 4
    except AssertionError as e:
        logging.exception('Update request didn\'t contain 4 sensors:')
    sensorMsg = Message('name', None, 'Sensor',
                Message.createImage(sensor1=sensors[0],
                sensor2=sensors[1],
                sensor3=sensors[2],
                sensor4=sensors[3]
                ))
    sensorMsg = Message.encode(sensorMsg)
    try:
        channel.basic_publish(exchange='HwCmd', routing_key='', body=sensorMsg)
    except Exception as e:
        retry_request(request=update_sensors, action='update sensors', num_tries=num_tries)

@app.route('/update', methods = ['GET', 'POST'])
# @requires_auth
def update():
    sensors = [request.form['sensor1'],
               request.form['sensor2'],
               request.form['sensor3'],
               request.form['sensor4']]
    logger.info('Updating sensor types')
    update_sensors(sensors)
    return 'OK'

@app.route('/run', methods = ['GET', 'POST'])
# @requires_auth
def start():
    logger.info('Issuing kill command')
    stop();

    logger.info('Running code on robot')
    # commands.getstatusoutput('python /home/pi/code/test.py')
    cmd = ['sudo python /home/pi/blockytalky/backend/user_script.py']
    try:
        p = subprocess.Popen(cmd, shell = True)
    except:
        logger.exception('Failed to run code on robot:')
    return 'OK'

@app.route('/load', methods = ['GET', 'POST'])
#@requires_auth
def load():
    logger.info('Loading Blockly code')
    url = url_for('static', filename='rawxml.txt', t=time.time())
    return redirect(url)

def authenticate():
    return Response('Oops! You need to login with the right username and'
                    ' password to access BlockyTalky.', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})

if __name__ == '__main__':
    handler = logging.handlers.RotatingFileHandler(filename='/home/pi/blockytalky/logs/blockly_ws.log',
                                                   maxBytes=8192, backupCount=3)
    globalHandler = logging.handlers.RotatingFileHandler(filename='/home/pi/blockytalky/logs/master.log',
                                                         maxBytes=16384, backupCount=3)
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s: %(message)s',
                                  datefmt='%H:%M:%S %d/%m')
    handler.setFormatter(formatter)
    globalHandler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(globalHandler)
    logger.setLevel(logging.INFO)

    #device_settings = load_device_settings()
    app.run(host = '0.0.0.0')
