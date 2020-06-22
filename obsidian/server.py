import asyncio
from typing import Optional
# import threading

from obsidian.packet import PacketManager
from obsidian.constants import Colour
from obsidian.log import Logger
from obsidian.network import NetworkHandler
from obsidian.module import ModuleManager


class Server(object):
    def __init__(self, address: str, port: int, name: str, motd: str, colour: bool = True):
        self.address: str = address
        self.port: int = port
        self.name: str = name
        self.motd: str = motd
        self.server: Optional[asyncio.AbstractServer] = None
        self.packets: dict = dict()
        self.protocolVersion: int = 0x07

        # Init Colour
        if colour:
            Colour.init()

    async def init(self):
        # Testing If Debug Is Enabled
        Logger.debug("Debug Is Enabled", module="init")
        Logger.verbose("Verbose Is Enabled", module="init")

        Logger.info(f"Initializing Server {self.name}", module="init")

        ModuleManager.initModules()

        Logger.info(f"{ModuleManager.numModules} Modules, {PacketManager.numPackets} Packets Initialized!", module="init")
        # Print Pretty List of All Modules
        Logger.info("Module List:", module="init")
        print(ModuleManager.generateTable())
        # Only print Packet List If Debug Enabled
        if(Logger.DEBUG):
            Logger.debug("Packets List:", module="init")
            print(PacketManager.generateTable())

        # Create Asyncio Socket Server
        # When new connection occurs, run callback _getConnHandler
        Logger.info(f"Setting Up Server {self.name}", module="init")
        self.server = await asyncio.start_server(self._getConnHandler(), self.address, self.port)

        '''
        #print(PlayerIdentification.doTheThing())
        #print(Packets._packet_list[PacketDirections.REQUEST]["PlayerIdentification"].doTheThing())
        print(Packets.Request.PlayerIdentification)
        print(Packets.Request.PlayerIdentification.doTheThing())
        print(Packets.Request.PlayerIdentification.FORMAT)
        print(Packets.Request.PlayerIdentification.MODULE.NAME)
        '''

    async def run(self):
        # Start Server
        Logger.info(f"Starting Server {self.name} On {self.address} Port {self.port}")
        async with self.server as s:
            await s.serve_forever()

    def _getConnHandler(self):  # -> Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]
        # Callback function on new connection
        async def handler(reader, writer):
            c = NetworkHandler(self, reader, writer)
            await c.initConnection()

        return handler
