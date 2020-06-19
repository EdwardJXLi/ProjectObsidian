import enum
import struct
from typing import Type, Optional
from dataclasses import dataclass
from obsidian.module import AbstractModule

# from obsidian.network import *
from obsidian.constants import InitError
from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger


# Enums
class PacketDirections(enum.Enum):
    REQUEST = 0
    RESPONSE = 1
    NONE = -1


# Packet Skeleton
@dataclass
class AbstractPacket:
    ID: int         # Packet Id
    FORMAT: str     # Packet Structure Format
    CIRTICAL: bool  # Packet Criticality. Dictates What Event Should Occur When Error
    # Defined Later In _DirectionalPacketManager
    DIRECTION: PacketDirections = PacketDirections.NONE
    NAME: str = ""
    DESCRIPTION: str = ""
    MODULE: Optional[AbstractModule] = None

    @property
    def SIZE(self):
        return struct.calcsize(self.FORMAT)


@dataclass
class AbstractRequestPacket(AbstractPacket):
    PLAYERLOOP: bool = False            # Accept Packet During Player Loop
    DIRECTION: PacketDirections = PacketDirections.REQUEST  # Network Direction (Response or Response)


@dataclass
class AbstractResponsePacket(AbstractPacket):
    DIRECTION = PacketDirections.REQUEST  # Network Direction (Response or Response)


def Packet(name: str, direction: PacketDirections, description: str = None):
    def internal(cls):
        cls.obsidian_packet = dict()
        cls.obsidian_packet["name"] = name
        cls.obsidian_packet["direction"] = direction
        cls.obsidian_packet["description"] = description
        cls.obsidian_packet["packet"] = cls
        return cls
    return internal


# Internal Directional Packet Manager
class _DirectionalPacketManager():
    def __init__(self, direction: PacketDirections):
        # Creates List Of Packets That Has The Packet Name As Keys
        self._packet_list = dict()
        self.direction = direction

    # Registration. Called by Packet Decorator
    def register(self, name: str, description: str, packet: Type[AbstractRequestPacket], module):
        Logger.debug(f"Registering Packet {name} From Module {module.NAME}", module="init-" + module.NAME)
        obj = packet()  # type: ignore    # Create Object
        # Attach Name, Direction, and Module As Attribute
        obj.DIRECTION = self.direction
        obj.NAME = name
        obj.DESCRIPTION = description
        obj.MODULE = module
        self._packet_list[name] = obj

    # Handles _DirectionalPacketManager["item"]
    def __getitem__(self, packet: str):
        return self._packet_list[packet]

    # Handles _DirectionalPacketManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Internal Packet Manager Singleton
class _PacketManager():
    def __init__(self):
        # Creates List Of Packets That Has The Packet Name As Keys
        self.RequestManager = _DirectionalPacketManager(PacketDirections.REQUEST)
        self.ResponseManager = _DirectionalPacketManager(PacketDirections.RESPONSE)
        self.Request = self.RequestManager  # Alias for RequestManager
        self.Response = self.ResponseManager  # Alias for ResponseManager

    # Registration. Called by Packet Decorator
    def register(self, direction: PacketDirections, *args, **kwargs):
        # Check Direction
        if(direction == PacketDirections.REQUEST):
            self.RequestManager.register(*args, **kwargs)
        elif(direction == PacketDirections.RESPONSE):
            self.ResponseManager.register(*args, **kwargs)
        else:
            raise InitError(f"Unknown Direction {direction} While Registering Packet")

    # Generate a Pretty List of Packets
    def generateTable(self):
        table = PrettyTableLite()  # Create Pretty List Class

        table.field_names = ["Direction", "Packet", "Id", "Module"]
        # Loop Through All Request Modules And Add Value
        for _, packet in self.RequestManager._packet_list.items():
            table.add_row(["Request", packet.NAME, packet.ID, packet.MODULE.NAME])
        # Loop Through All Response Modules And Add Value
        for _, packet in self.ResponseManager._packet_list.items():
            table.add_row(["Response", packet.NAME, packet.ID, packet.MODULE.NAME])

        return table

    # Property Method To Get Number Of Packets
    @property
    def numPackets(self):
        return len(self.RequestManager._packet_list) + len(self.ResponseManager._packet_list)


# Packet Utils
def unpackageString(data, encoding="ascii"):
    Logger.verbose(f"Unpacking String {data}")
    # Decode Data From Bytes To String
    # Remove Excess Zeros
    return data.decode(encoding).strip()


def packageString(data, maxSize=64, encoding="ascii"):
    Logger.verbose(f"Packing String {data}")
    # Trim Text Down To maxSize
    # Fill Blank Space With Spaces Using ljust
    # Encode String Into Bytes Using Encoding
    return bytes(data[:maxSize].ljust(maxSize), encoding)


# Creates Global PacketManager As Singleton
PacketManager = _PacketManager()
# Adds Alias To PacketManager
Packets = PacketManager
