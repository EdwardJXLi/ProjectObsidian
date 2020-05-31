import asyncio
# import threading

from obsidian.constants import Colour
from obsidian.log import Logger
from obsidian.network import NetworkHandler


class Server(object):
    def __init__(self, address, port, name, motd, colour=True):
        self.address = address
        self.port = port
        self.name = name
        self.motd = motd
        self.server = None
        self.packets = {}

        # Init Colour
        if(colour):
            Colour.init()

    async def init(self):
        # Testing If Debug Is Enabled
        Logger.debug("Debug Is Enabled", module="init")
        Logger.verbose("Verbose Is Enabled", module="init")

        Logger.info(f"Initializing Server {self.name}", module="init")

        Logger.info("Registering Core Packets", module="init")
        # registerCorePackets(self.dispacher)

        # Create Asyncio Socket Server
        # When new connection occurs, run callback _getConnHandler
        Logger.info(f"Setting Up Server {self.name}", module="init")
        self.server = await asyncio.start_server(self._getConnHandler(), self.address, self.port)

    async def run(self):
        # Start Server
        Logger.info(f"Starting Server {self.name} On {self.address} Port {self.port}")
        async with self.server as s:
            await s.serve_forever()

    def _getConnHandler(self):
        # Callback function on new connection
        async def handler(reader, writer):
            c = NetworkHandler(self, reader, writer)
            await c.initConnection()

        return handler

    def registerPacket(self, packet):
        pass
