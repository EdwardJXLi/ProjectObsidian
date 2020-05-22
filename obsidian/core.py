from obsidian.constants import *
from obsidian.log import *

class Server(object):
    def __init__(self, address, port, colour=True):
        self._address = address
        self._port = port
        #Init Colour
        if(colour):
            Colour.init()

    def setup(self):
        Logger.info(f"Setting Up Server", module="setup")
        print(self._address, self._port)

    def start(self):
        print(self._address, self._port)

    def stop(self):
        print(self._address, self._port)
