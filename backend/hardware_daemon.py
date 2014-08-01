#!/usr/bin/env python
"""
Blocky Talky - Hardware Daemon (hd.py, RabbitMQ client)

This module keeps the userscript on the Pi updated with sensor values and it
also directly controls the hardware.
"""
import time
import threading
import logging
import socket
import pika
import os
from blockytalky_id import *
from message import *
from BrickPi import *

channel = None
logger = logging.getLogger(__name__)
os.nice(-5)

class HardwareDaemon(object):
    PUBLISH_INTERVAL = 0.01
    
    def __init__(self):
        logger.info('Initializing hardware daemon')
        self.hostname = BlockyTalkyID()
        self.robot = Message.initStatus()
        self.sensorsRequested = False
        self.hwval_channel = None
        self.hwcmd_channel = None
        self.encoder_offsets = [0,0,0,0]

        os.chdir("/home/pi/blockytalky/backend/")
        f = open("sensors", "r")
        slist = f.read()
        f.close()
        slist = slist.split(",")
        processedlist = map(int, slist)
        self.sensorList = processedlist
        BrickPi.SensorType = processedlist
        os.chdir("/home/pi/blockytalky/")

        parameters = pika.ConnectionParameters()
        self.connection = pika.BlockingConnection(parameters)
        self.setup_hwval_channel()
        self.setup_hwcmd_channel()
        
        initPins()
        BrickPiSetup()
        BrickPi.MotorEnable[PORT_A] = 1
        BrickPi.MotorEnable[PORT_B] = 1
        BrickPi.MotorEnable[PORT_C] = 1
        BrickPi.MotorEnable[PORT_D] = 1    

        BrickPiSetupSensors()
        
    def start(self):
        self.schedule_check_status()
        self.hwcmd_channel.start_consuming()
    
    def schedule_check_status(self):
        logger.info("Scheduling a check_status in %s seconds" % self.__class__.PUBLISH_INTERVAL)
        self.connection.add_timeout(self.__class__.PUBLISH_INTERVAL, self.check_status_and_reschedule)   

    def check_status_and_reschedule(self):
        self.check_status()
        self.schedule_check_status()

    def check_status(self):
        """
        Applies the changes made to LEDs and motors and sends a message to HwVal
        channel every time a hardware value changes on the robot.
        """
        valuesChanged = False
        
        if self.hwval_channel is None:
            logger.info("skipping check_status because channel is None")
            return

        BrickPi.Led = self.robot["leds"]
        try:
            BrickPi.MotorSpeed[0] = int(float(self.robot["motors"][0]) * 2.55)
            BrickPi.MotorSpeed[1] = int(float(self.robot["motors"][1]) * 2.55)
            BrickPi.MotorSpeed[2] = int(float(self.robot["motors"][2]) * 2.55)
            BrickPi.MotorSpeed[3] = int(float(self.robot["motors"][3]) * 2.55)
        except Exception as e:
            logger.exception('Error occurred while reading motor values:')
       
        BrickPi.Gpio = self.robot["pins"]
        logger.info("Calling BrickPiUpdateValues")
        BrickPiUpdateValues()

        #Copy sensors and encoders for comparison.
        sensors = BrickPi.Sensor[:]
        encoders = BrickPi.Encoder[:]

        #Check to see if sensor or encoder status has changed.
        for index, sensor in enumerate(sensors):
            try:
                if (self.sensorList[index] == 32) or (self.sensorList[index] == 33):
                    if (abs(int(sensor) - self.robot["sensors"][index]) > 0 or
                        self.robot["sensors"][index] == None):
                        self.robot["sensors"][index] = sensor
                        if not valuesChanged:
                            valuesChanged = True

                if (abs(int(sensor) - self.robot["sensors"][index]) > 5 or
                    self.robot["sensors"][index] == None):
                    self.robot["sensors"][index] = sensor
                    if not valuesChanged:
                        valuesChanged = True

            except:
                logger.debug('Sensor[%d] not found' % index)
                self.robot["sensors"][index] = None

        for index, encoder in enumerate(encoders):
            try:
                if (abs((encoder) - (self.robot["encoders"][index])) > 5 or
                    self.robot["encoders"][index] == None):
                    self.robot["encoders"][index] = encoder
                    if not valuesChanged:
                        valuesChanged = True
            except:
                logger.debug('Sensor[%d] not found' % index)
                self.robot["encoders"][index] = None

        if self.sensorsRequested:
            logger.debug('Sensor values requested')
            valuesChanged = True
            self.sensorsRequested = False
        
        #if not valuesChanged: print "no values seem to have changed"

        if valuesChanged:
            s1 = sensors[0]
            s2 = sensors[1]
            s3 = sensors[2]
            s4 = sensors[3]
            if self.sensorList[0] == 50:
                value1 = int(-0.0003 * (s1 * s1) + 0.0489 * s1 + 95.997)
            elif self.sensorList[0] == 51:
                value1 = int(-0.0004 * (s1 * s1) + 0.1103 * s1 + 99.2576)
            elif self.sensorList[0] == 9:
                value1 = int(-0.1659 * s1 + 128.55)
            else:
                value1 = s1

            if self.sensorList[1] == 50:
                value2 = int(-0.0003 * (s2 * s2) + 0.0489 * s2 + 95.997)
            elif self.sensorList[1] == 51:
                value2 = int(-0.0004 * (s2 * s2) + 0.1103 * s2 + 99.2576)
            elif self.sensorList[1] == 9:
                value2 = int(-0.1659 * s2 + 128.55)
            else:
                value2 = s2

            if self.sensorList[2] == 50:
                value3 = int(-0.0003 * (s3 * s3) + 0.0489 * s3 + 95.997)
            elif self.sensorList[2] == 51:
                value3 = int(-0.0004 * (s3 * s3) + 0.1103 * s3 + 99.2576)
            elif self.sensorList[2] == 9:
                value3 = int(-0.1659 * s3 + 128.55)
            else:
                value3 = s3

            if self.sensorList[3] == 50:
                value4 = int(-0.0003 * (s4 * s4) + 0.0489 * s4 + 95.997)
            elif self.sensorList[3] == 51:
                value4 = int(-0.0004 * (s4 * s4) + 0.1103 * s4 + 99.2576)
            elif self.sensorList[3] == 9:
                value4 = int(-0.1659 * s4 + 128.55)
            else:
                value4 = s4

            # offset encoders back to zero
            encoders[0] -= self.encoder_offsets[0]
            encoders[1] -= self.encoder_offsets[1]
            encoders[2] -= self.encoder_offsets[2]
            encoders[3] -= self.encoder_offsets[3]

            # Send a status message with the updated values.
            content = Message.createImage(
                                            encoder1 = encoders[0],
                                            encoder2 = encoders[1],
                                            encoder3 = encoders[2],
                                            encoder4 = encoders[3],
                                            sensor1 = value1,
                                            sensor2 = value2,
                                            sensor3 = value3,
                                            sensor4 = value4
                                         )
            statusMessage = Message(self.hostname, None, "HwVal", content)
            statusMessage = Message.encode(statusMessage)
            self.hwval_channel.basic_publish(exchange='sensors', routing_key='', body=statusMessage)


    def setup_hwval_channel(self):
        ##fixme:  document what the below line of code is for.  Joe???
        self.prevMessage = Message("none", None, "HwCmd", Message.createImage(pin11=2))
        
        self.hwval_channel = self.connection.channel()
        logger.info("Creating sensors exchange...")
        self.hwval_channel.exchange_declare(exchange='sensors', type='fanout')
    
    def setup_hwcmd_channel(self):
        self.hwcmd_channel = self.connection.channel()
        self.hwcmd_channel.exchange_declare(exchange='HwCmd', type='fanout')
        result = self.hwcmd_channel.queue_declare(exclusive=True)
        queue_name = result.method.queue
        self.hwcmd_channel.queue_bind(exchange='HwCmd', queue=queue_name)
        self.hwcmd_channel.basic_consume(self.handle_hwcmd_delivery, 
                                    queue=queue_name, no_ack = True)
        
    def handle_hwcmd_delivery(self, channel, method, header, body):
        logger.info("hwcmd command received: " + body)
        command = Message.decode(body)
        if command.channel == "handshake":
            self.encoder_offsets = [self.robot["encoders"][0], 
                                    self.robot["encoders"][1],
                                    self.robot["encoders"][2], 
                                    self.robot["encoders"][3]]
            print self.encoder_offsets
            content = Message.createImage(
                encoder1 = self.robot["encoders"][0]-self.encoder_offsets[0],
                encoder2 = self.robot["encoders"][1]-self.encoder_offsets[1],
                encoder3 = self.robot["encoders"][2]-self.encoder_offsets[2],
                encoder4 = self.robot["encoders"][3]-self.encoder_offsets[3],
                sensor1 =  self.robot["sensors"][0],
                sensor2 =  self.robot["sensors"][0],
                sensor3 =  self.robot["sensors"][0],
                sensor4 =  self.robot["sensors"][0])
            statusMessage = Message(self.hostname, None, "HwVal", content)
            statusMessage = Message.encode(statusMessage)
            self.hwval_channel.basic_publish(exchange='sensors', 
                                             routing_key='', body=statusMessage)

        elif command.channel == "Sensor":
            port = None
            newType = None
            sensorDict = command.getContent()
            for key, valueList in sensorDict.iteritems():
                for index, value in enumerate(valueList):
                    if value is not None:
                        if value == "none":
                            newType = TYPE_SENSOR_RAW
                        if value == "touch":
                            newType = TYPE_SENSOR_TOUCH
                        if value == "ultra":
                            newType = TYPE_SENSOR_ULTRASONIC_CONT
                        if value == "sound":
                            newType = TYPE_SENSOR_SOUND
                        if value == "light_on":
                            newType = TYPE_SENSOR_LIGHT_ON
                        if value == "light_off":
                            newType = TYPE_SENSOR_LIGHT_OFF

                        BrickPi.SensorType[index] = newType 
                        self.sensorList[index] = newType
                        os.chdir("/home/pi/blockytalky/backend/")
                        sensorString = ""
                        for item in self.sensorList:
                            sensorString = sensorString + "," + str(item)
                        
                        sensorString = sensorString[1:]
                        print "sensorString: " + str(sensorString)
                        fo = open("sensors", "wb")
                        fo.write(sensorString)
                        fo.close()

                        os.chdir("/home/pi/blockytalky/")

            time.sleep(.01)
            BrickPiSetupSensors()
            self.sensorsRequested = True

        else:
            hwDict = command.getContent()
            if command == self.prevMessage: # Message is the same, do nothing
                pass
            else:
                for key, valueList in hwDict.iteritems():
                    for index, value in enumerate(valueList):
                        if value is not None:
                            self.robot[key][index] = value
                logger.debug('Command: ' + str(hwDict))
            self.prevMessage = command


if __name__ == "__main__":
    handler = logging.handlers.RotatingFileHandler(filename='/home/pi/blockytalky/logs/hardware_daemon.log',
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
    
    hd = HardwareDaemon()
    hd.start()

