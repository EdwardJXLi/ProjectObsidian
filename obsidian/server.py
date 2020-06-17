import asyncio
from typing import Optional
import importlib
# import threading

import obsidian.packet as corepacket
from obsidian.packet import PacketDirections, PacketManager, Packets
from obsidian.constants import Colour, InitError
from obsidian.log import Logger
from obsidian.network import NetworkHandler
from obsidian.module import ModuleManager, Modules


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

        #print(PlayerIdentification.doTheThing())
        #print(Packets._packet_list[PacketDirections.REQUEST]["PlayerIdentification"].doTheThing())
        print(Packets.Request.PlayerIdentification)
        print(Packets.Request.PlayerIdentification.doTheThing())
        print(Packets.Request.PlayerIdentification.FORMAT)
        print(Packets.Request.PlayerIdentification.MODULE.NAME)

    async def run(self):
        pass

        '''

        Logger.info("Setting Up Packet Dictionary", module="init")
        self.packets["request"] = dict()
        self.packets["response"] = dict()

        Logger.info("Initializing Core Module", module="init")
        Logger.info("Registering Core Module", module="init")
        corepacket.registerCoreModules(self)

        # Create Asyncio Socket Server
        # When new connection occurs, run callback _getConnHandler
        Logger.info(f"Setting Up Server {self.name}", module="init")
        self.server = await asyncio.start_server(self._getConnHandler(), self.address, self.port)


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

    # Initialize Regerster Packer Handler
    def registerInit(self, module):
        Logger.debug(f"Initialize {module} Module Registration", module=module + "-init")

        # Add Module To Packet dict
        self.packets["request"][module] = dict()
        self.packets["response"][module] = dict()

    def registerPacket(self, packet):
        Logger.verbose(f"Registering Packet {packet.__name__} (ID: {packet.ID}) From Module {packet.MODULE}", module=packet.MODULE + "-init")

        Logger.verbose("Adding Packet To Dict", module=packet.MODULE + "-init")
        # Creating Temporary Variables
        # Direction Key Word
        directionKW = None
        # Check Packet Type
        if packet.DIRECTION == PacketDirections.REQUEST:
            directionKW = "request"
        elif packet.DIRECTION == PacketDirections.RESPONSE:
            directionKW = "response"
        else:
            raise InitError(f"Unknown Packet Direction {packet.DIRECTION} for Packet {packet.__name__} (ID: {packet.ID}) From Module {packet.MODULE}!")

        # Check if Packet Id has Already been used.
        packetList = self._getPackets(directionKW).keys()
        if packet.ID in packetList:
            raise InitError(f"Packet ID {packet.ID} From Packet {packet.__name__} (Module {packet.MODULE}) Has Already Been Registered!")

        # Check if Packet Module Has Been Registered
        if packet.MODULE not in self.packets[directionKW].keys():
            raise InitError(f"Packet Module '{packet.MODULE}' From Packet {packet.__name__} (ID: {packet.ID}) Has Not Been Registered. Current Registered Modules: {list(self.packets[directionKW].keys())}")

        # Adding Packet To Packet Dict
        self.packets[directionKW][packet.MODULE][packet.ID] = packet

    # Returns Dictionary With All Directional Packets, With IDs As Keys
    def _getPackets(self, direction):
        packetDict = dict()
        # Loop Through All Modules and Packets
        for module, packets in self.packets[direction].items():
            for packetId, packet in packets.items():
                packetDict[packetId] = packet

        return packetDict
'''