from __future__ import annotations

import enum
import struct
from typing import Type, Optional
from dataclasses import dataclass
from obsidian.module import AbstractModule

# from obsidian.network import *
from obsidian.constants import InitError, InitRegisterError, PacketError, FatalError
from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger


# Enums
class PacketDirections(enum.Enum):
    REQUEST = 0
    RESPONSE = 1
    NONE = -1


# Packet Utils
def unpackageString(data, encoding="ascii"):
    Logger.verbose(f"Unpacking String {data}", module="packet")
    # Decode Data From Bytes To String
    # Remove Excess Zeros
    return data.decode(encoding).strip()


def packageString(data, maxSize=64, encoding="ascii"):
    Logger.verbose(f"Packing String {data}", module="packet")
    # Trim Text Down To maxSize
    # Fill Blank Space With Spaces Using ljust
    # Encode String Into Bytes Using Encoding
    return bytes(data[:maxSize].ljust(maxSize), encoding)


# Packet Skeleton
@dataclass
class AbstractPacket:
    # Mandatory Values Defined In Packet Init
    ID: int         # Packet Id
    FORMAT: str     # Packet Structure Format
    CRITICAL: bool  # Packet Criticality. Dictates What Event Should Occur When Error
    # Mandatory Values Defined In Packet Decorator
    DIRECTION: PacketDirections = PacketDirections.NONE
    NAME: str = ""
    # Optional Values Defined In Packet Decorator
    DESCRIPTION: str = ""
    # Mandatory Values Defined During Module Initialization
    MODULE: Optional[AbstractModule] = None

    # Error Handler. Called If Critical If False And An Error Occurs
    def onError(self, error):
        Logger.error(f"Packet {self.NAME} Received Error {error}")

    @property
    def SIZE(self):
        return struct.calcsize(self.FORMAT)


@dataclass
class AbstractRequestPacket(AbstractPacket):
    # Mandatory Values Defined In Packet Init
    PLAYERLOOP: bool = False            # Accept Packet During Player Loop
    DIRECTION: PacketDirections = PacketDirections.REQUEST  # Network Direction (Response or Response)

    async def deserialize(self, *args, **kwargs):
        return None


@dataclass
class AbstractResponsePacket(AbstractPacket):
    # Mandatory Values Defined In Packet Init
    DIRECTION = PacketDirections.REQUEST  # Network Direction (Response or Response)

    async def serialize(self, *args, **kwargs):
        return bytes()


# Packet Decorator
# Used In @Packet
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
class _DirectionalPacketManager:
    def __init__(self, direction: PacketDirections):
        # Creates List Of Packets That Has The Packet Name As Keys
        self._packet_list = dict()
        self.direction = direction
        # Only Used If Request
        if self.direction is PacketDirections.REQUEST:
            self.loopPackets = {}  # Fast Cache Of Packet Ids to Packet Objects That Are Used During PlayerLoop

    # Registration. Called by Packet Decorator
    def register(self, name: str, description: str, packet: Type[AbstractRequestPacket], module):
        Logger.debug(f"Registering Packet {name} From Module {module.NAME}", module="init-" + module.NAME)
        obj = packet()  # type: ignore    # Create Object
        # Checking If Packet And PacketId Is Already In Packets List
        if name in self._packet_list.keys():
            raise InitRegisterError(f"Packet {name} Has Already Been Registered!")
        if obj.ID in self.getAllPacketIds():
            raise InitRegisterError(f"Packet Id {obj.ID} Has Already Been Registered!")
        # Attach Name, Direction, and Module As Attribute
        obj.DIRECTION = self.direction
        obj.NAME = name
        obj.DESCRIPTION = description
        obj.MODULE = module
        self._packet_list[name] = obj
        # Only Used If Request
        if self.direction is PacketDirections.REQUEST:
            # Add To Packet Cache If Packet Is Used In Main Player Loop
            if obj.PLAYERLOOP:
                Logger.verbose(f"Adding Packet {obj.ID} To Main Player Loop Request Packet Cache", module="init-" + module.NAME)
                self.loopPackets[obj.ID] = obj

    def getAllPacketIds(self):
        return [obj.ID for obj in self._packet_list.values()]

    def getPacketById(self, packetId):
        # Search Packet With Matching packetId
        for packet in self._packet_list.values():
            if packet.ID == packetId:
                return packet
        raise PacketError(f"Packet {packetId} Was Not Found")

    # Handles _DirectionalPacketManager["item"]
    def __getitem__(self, packet: str):
        return self._packet_list[packet]

    # Handles _DirectionalPacketManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Internal Packet Manager Singleton
class _PacketManager:
    def __init__(self):
        # Creates List Of Packets That Has The Packet Name As Keys
        self.RequestManager = _DirectionalPacketManager(PacketDirections.REQUEST)
        self.ResponseManager = _DirectionalPacketManager(PacketDirections.RESPONSE)
        self.Request = self.RequestManager  # Alias for RequestManager
        self.Response = self.ResponseManager  # Alias for ResponseManager

    # Registration. Called by Packet Decorator
    def register(self, direction: PacketDirections, *args, **kwargs):
        # Check Direction
        if direction is PacketDirections.REQUEST:
            self.RequestManager.register(*args, **kwargs)
        elif direction is PacketDirections.RESPONSE:
            self.ResponseManager.register(*args, **kwargs)
        else:
            raise InitError(f"Unknown Direction {direction} While Registering Packet")

    # Generate a Pretty List of Packets
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Direction", "Packet", "Id", "Player Loop", "Module"]
            # Loop Through All Request Modules And Add Value
            for _, packet in self.RequestManager._packet_list.items():
                # Adding Row To Table
                table.add_row(["Request", packet.NAME, packet.ID, packet.PLAYERLOOP, packet.MODULE.NAME])
            # Loop Through All Response Modules And Add Value
            for _, packet in self.ResponseManager._packet_list.items():
                table.add_row(["Response", packet.NAME, packet.ID, "N/A", packet.MODULE.NAME])

            return table
        except FatalError:
            # Pass Down Fatal Error To Base Server
            raise FatalError()
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", "server")

    # Property Method To Get Number Of Packets
    @property
    def numPackets(self):
        return len(self.RequestManager._packet_list) + len(self.ResponseManager._packet_list)


# Creates Global PacketManager As Singleton
PacketManager = _PacketManager()
# Adds Alias To PacketManager
Packets = PacketManager
