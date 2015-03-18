#!/bin/bash
##set up i2c for rpi1/2 and python environment
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y python-pip git libi2c-dev python-serial python-rpi.gpio i2c-tools python-smbus
sudo apt-get install -y python-dev libffi-dev samba
##flask app dependencies
sudo pip install flask tornado jsonpickle pyttsx pyOSC websocket-client pika flask-bcrypt requests
##rabbitMQ and erlang deps
wget http://www.rabbitmq.com/releases/rabbitmq-server/v3.4.3/rabbitmq-server_3.4.3-1_all.deb
sudo dpkg -i rabbitmq-server_3.4.3-1_all.deb
sudo apt-get -f -y install
#config for rabbit mq
echo "[{rabbit, [{loopback_users,[]}]}]." | sudo tee -a /etc/rabbitmq/rabbitmq.config
sudo rabbitmq-plugins enable rabbitmq_web_stomp
sudo rabbitmqctl set_policy TTL ".*" '{"message-ttl":3000}' --apply-to queues
sudo apt-get clean
##daemontools
sudo mkdir -p /package
sudo chmod 755 /package
cd /package
sudo wget http://cr.yp.to/daemontools/daemontools-0.76.tar.gz
sudo tar -xpf daemontools-0.76.tar.gz
sudo rm -f daemontools-0.76.tar.gz
cd admin/daemontools-0.76
#install tends to fail on rpi so fix src:
sudo sed -i ' 1 s/$/ -include errno.h/' ./src/conf-cc
#install:
sudo package/install
sudo apt-get install -y csh
sudo csh -cf '/command/svscanboot &'
sudo mkdir /service/hd
sudo cp /home/pi/blockytalky/build.d/run /service/hd
##samba
echo 'wins server =wlan0:0.0.0.0' | sudo tee -a /etc/samba/dhcp.conf
##a2enmod for apache
sudo apt-get install -y libapache2-mod-wsgi
sudo a2enmod wsgi
sudo a2enmod rewrite
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod ssl
sudo cp /home/pi/blockytalky/build.d/blockly_ws.wsgi /etc/apache2/
sudo cp /home/pi/blockytalky/build.d/blockly_ws.conf /etc/apache2/sites-available/
sudo a2dissite default
sudo a2ensite blockly_ws.conf
echo "ServerName localhost" | sudo tee /etc/apache2/conf.d/fqdn
#overclocking
echo "arm_freq_min=400" | sudo tee -a /boot/config.txt
echo "sdram_freq_min=250" | sudo tee -a /boot/config.txt
echo "core_freq_min=250" | sudo tee -a /boot/config.txt
echo "initial_turbo = 30 #Does not affect warranty. (Speeds up boot)" | sudo tee -a /boot/config.txt
echo "gpu_mem=16" | sudo tee -a /boot/config.txt
#is this a pi 1?
#arm=$(more /proc/cpuinfo | grep "model name" | grep ARMv6)
##logs
sudo mkdir /home/pi/blockytalky/logs
sudo touch /home/pi/blockytalky/logs/blockly_ws.log
sudo chown pi /home/pi/blockytalky/logs/blockly_ws.log
sudo chmod 775 /home/pi/blockytalky/logs/blockly_ws.log

sudo touch /home/pi/blockytalky/logs/comms_module.log
sudo chown pi /home/pi/blockytalky/logs/comms_module.log
sudo chmod 775 /home/pi/blockytalky/logs/comms_module.log

sudo touch /home/pi/blockytalky/logs/master.log
sudo chown pi /home/pi/blockytalky/logs/master.log
sudo chmod 775 /home/pi/blockytalky/logs/master.log

sudo touch /home/pi/blockytalky/logs/hardware_daemon.log
sudo chown pi /home/pi/blockytalky/logs/hardware_daemon.log
sudo chmod 775 /home/pi/blockytalky/logs/hardware_daemon.log

sudo touch /home/pi/cm.log
sudo chown pi /home/pi/cm.log
sudo chmod 664 /home/pi/cm.log
