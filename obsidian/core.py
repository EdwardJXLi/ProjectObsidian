import asyncio
import threading

from obsidian.constants import *
from obsidian.log import *
from obsidian.network import *

class Server(object):
    def __init__(self, address, port, name, motd, colour=True):
        self.address = address
        self.port = port
        self.name = name
        self.motd = motd
        #Init Colour
        if(colour):
            Colour.init()

    async def init(self):
        #Testing If Debug Is Enabled
        Logger.debug("Debug Is Enabled", module="init")
        Logger.verbose("Verbose Is Enabled", module="init")
        #Create Asyncio Socket Server
        #When connection, run callback connHandler
        Logger.info(f"Setting Up Server {self.name}", module="init")
        self.server = await asyncio.start_server(self.connHandler(), self.address, self.port)
   
    async def run(self):
        #Start Server
        Logger.info(f"Starting Server {self.name} On {self.address} Port {self.port}")
        async with self.server as s:
            await s.serve_forever()
    
    def connHandler(self):
        #Callback function on new connection
        async def handler(reader, writer):
            c = NetworkHandler(reader, writer)
            await c.initConnection()

        return handler
