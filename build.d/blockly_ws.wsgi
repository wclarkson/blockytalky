import sys, logging
sys.path.insert(0,'/home/pi/blockytalky/backend/')
import blockly_webserver
from blockly_webserver import app as application
logging.basicConfig(stream=sys.stderr)
