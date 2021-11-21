from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.player import Player

import enum
import struct
from typing import Type
from dataclasses import dataclass
from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager

# from obsidian.network import *
from obsidian.constants import (
    InitRegisterError,
    PacketError,
    FatalError
)
from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger


# Enums
class PacketDirections(enum.Enum):
    REQUEST = 0
    RESPONSE = 1
    NONE = -1


# Packet Utils
def unpackageString(data, encoding: str = "ascii"):
    Logger.verbose(f"Unpacking String {data}", module="packet")
    # Decode Data From Bytes To String
    # Remove Excess Zeros
    return data.decode(encoding).strip()


def packageString(data: str, maxSize: int = 64, encoding: str = "ascii"):
    Logger.verbose(f"Packing String {data}", module="packet")
    # Trim Text Down To maxSize
    # Fill Blank Space With Spaces Using ljust
    # Encode String Into Bytes Using Encoding
    return bytearray(data[:maxSize].ljust(maxSize), encoding)


# Packet Skeleton
@dataclass
class AbstractPacket(AbstractSubmodule):
    ID: int = 0             # Packet Id
    FORMAT: str = ""        # Packet Structure Format
    CRITICAL: bool = False  # Packet Criticality. Dictates What Event Should Occur When Error

    # Error Handler. Called If Critical If False And An Error Occurs
    def onError(self, error: str):
        Logger.error(f"Packet {self.NAME} Raised Error {error}", module="packet")

    @property
    def SIZE(self) -> int:
        return int(struct.calcsize(self.FORMAT))


@dataclass
class AbstractRequestPacket(AbstractPacket):
    # Mandatory Values Defined In Packet Init
    PLAYERLOOP: bool = False            # Accept Packet During Player Loop
    DIRECTION: PacketDirections = PacketDirections.REQUEST  # Network Direction (Response or Response)

    async def deserialize(self, ctx: Player, *args, **kwargs):
        return None


@dataclass
class AbstractResponsePacket(AbstractPacket):
    # Mandatory Values Defined In Packet Init
    DIRECTION = PacketDirections.REQUEST  # Network Direction (Response or Response)

    async def serialize(self, *args, **kwargs):
        return bytearray()


# Request Packet Decorator
# Used In @RequestPacket
def RequestPacket(*args, **kwargs):
    return Submodule(PacketManager.RequestManager, *args, **kwargs)


# Response Packet Decorator
# Used In @ResponsePacket
def ResponsePacket(*args, **kwargs):
    return Submodule(PacketManager.ResponseManager, *args, **kwargs)


# Internal Directional Packet Manager
class _DirectionalPacketManager(AbstractManager):
    def __init__(self, direction: PacketDirections):
        # Initialize Overarching Manager Class
        super().__init__(f"{direction.name.title()} Packet", AbstractPacket)

        # Creates List Of Packets That Has The Packet Name As Keys
        self._packet_list = dict()  # Not putting a type here as it breaks more things than it fixes
        self.direction: PacketDirections = direction
        # Only Used If Request
        if self.direction is PacketDirections.REQUEST:
            self.loopPackets = {}  # Fast Cache Of Packet Ids to Packet Objects That Are Used During PlayerLoop

    # Registration. Called by (Directional) Packet Decorator
    def register(self, packetClass: Type[AbstractPacket], module: AbstractModule):
        Logger.debug(f"Registering Packet {packetClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        packet: AbstractPacket = super()._initSubmodule(packetClass, module)

        # Handling Special Cases if OVERRIDE is Set
        if packet.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if (packet.ID not in self._packet_list.keys()) and (packet.NAME not in self.getAllPacketIds()):
                Logger.warn(f"Packet {packet.NAME} (ID: {packet.ID}) From Module {packet.MODULE.NAME} Is Trying To Override A Packet That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"Packet {packet.NAME} Is Overriding Packet {self._packet_list[packet.NAME].NAME} (ID: {packet.ID})", module=f"{module.NAME}-submodule-init")

        # Checking If Packet And PacketId Is Already In Packets List
        # Ignoring if OVERRIDE is set
        if packet.NAME in self._packet_list.keys() and not packet.OVERRIDE:
            raise InitRegisterError(f"Packet {packet.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")
        if packet.ID in self.getAllPacketIds() and not packet.OVERRIDE:
            raise InitRegisterError(f"Packet Id {packet.ID} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Only Used If Request
        if self.direction is PacketDirections.REQUEST:
            # Cast Packet into Request Packet Type
            requestPacket: AbstractRequestPacket = packet  # type: ignore
            # Add To Packet Cache If Packet Is Used In Main Player Loop
            if requestPacket.PLAYERLOOP:
                Logger.verbose(f"Adding Packet {requestPacket.ID} To Main Player Loop Request Packet Cache", module=f"{module.NAME}-submodule-init")
                self.loopPackets[requestPacket.ID] = requestPacket

        # Add Packet to Packets List
        self._packet_list[packet.NAME] = packet

    def getAllPacketIds(self):
        return [obj.ID for obj in self._packet_list.values()]

    def getPacketById(self, packetId: int):
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
        self.RequestManager: _DirectionalPacketManager = _DirectionalPacketManager(PacketDirections.REQUEST)
        self.ResponseManager: _DirectionalPacketManager = _DirectionalPacketManager(PacketDirections.RESPONSE)
        self.Request: _DirectionalPacketManager = self.RequestManager  # Alias for RequestManager
        self.Response: _DirectionalPacketManager = self.ResponseManager  # Alias for ResponseManager

    # Generate a Pretty List of Packets
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Direction", "Packet", "Id", "Player Loop", "Module"]
            # Loop Through All Request Modules And Add Value
            for _, packet in self.RequestManager._packet_list.items():
                requestPacket: AbstractRequestPacket = packet
                # Adding Row To Table
                table.add_row(["Request", requestPacket.NAME, requestPacket.ID, requestPacket.PLAYERLOOP, requestPacket.MODULE.NAME])
            # Loop Through All Response Modules And Add Value
            for _, packet in self.ResponseManager._packet_list.items():
                responsePacket: AbstractResponsePacket = packet
                # Adding Row To Table
                table.add_row(["Response", responsePacket.NAME, responsePacket.ID, "N/A", responsePacket.MODULE.NAME])

            return table
        except FatalError as e:
            # Pass Down Fatal Error To Base Server
            raise e
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

    # Property Method To Get Number Of Packets
    @property
    def numPackets(self):
        return len(self.RequestManager._packet_list) + len(self.ResponseManager._packet_list)


# Creates Global PacketManager As Singleton
PacketManager = _PacketManager()
# Adds Alias To PacketManager
Packets = PacketManager
