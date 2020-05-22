import asyncio
import threading

from obsidian.constants import *
from obsidian.log import *
from obsidian.client import *

class Server(object):
    def __init__(self, address, port, colour=True):
        self.address = address
        self.port = port
        #Init Colour
        if(colour):
            Colour.init()

    def setup(self):
        Logger.info(f"Setting Up Server", module="setup")
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(asyncio.start_server(self.handleClient, self.address, self.port))
        #print(self.address, self.port)

    def start(self):
        Logger.info(f"Starting Server")
        self.loop.run_forever()
        Logger.info(f"Server Starting On {self.address} Port {self.port}")

    def stop(self):
        pass

    async def handleClient(self, reader, writer):
        #Temporary Socket Testing Code
        while True:
            request = (await reader.read(255)).decode('utf8')
            response = str(request) + '\n'
            writer.write(response.encode('utf8'))
            await writer.drain()

