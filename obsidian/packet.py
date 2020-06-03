import enum
import struct
from typing import Any

# from obsidian.network import *
# from obsidian.constants import *
from obsidian.log import Logger


# Enums
class PacketDirections(enum.Enum):
    REQUEST = 0
    RESPONSE = 1
    NONE = -1


# Packet Skeleton
class AbstractPacket:
    ID: int = -1            # Packet Id
    FORMAT: str = ""        # Packet Structure Format
    SIZE: int = 0           # Packet Size
    CIRTICAL: bool = False  # Packet Criticality. Dictates What Event Should Occur When Error
    MODULE: str = "None"    # Packet Module Owner
    DIRECTION: PacketDirections = PacketDirections.NONE


class AbstractRequestPacket(AbstractPacket):
    DIRECTION = PacketDirections.REQUEST  # Network Direction (Response or Response)
    PLAYERLOOP = None               # Accept Packet During Player Loop

    @classmethod
    def deserialize(cls, *args, **kwargs) -> Any:
        return None

    @classmethod
    def postDeserialization(cls):
        pass


# Packet Skeletons
class AbstractResponsePacket(AbstractPacket):
    DIRECTION = PacketDirections.RESPONSE    # Network Direction (Response or Response)

    @classmethod
    def serialize(cls, *args, **kwargs) -> bytes:
        return bytes()

    @classmethod
    def postSterilization(cls):
        pass


#
# Request Network Packets
#
class TestPacket(AbstractRequestPacket):
    ID = 0x61
    FORMAT = "B5s"
    CIRTICAL = True
    PLAYERLOOP = False
    MODULE = "Test"
    SIZE = struct.calcsize(FORMAT)

    @classmethod
    def deserialize(cls, rawData):
        _, msg = struct.unpack(cls.FORMAT, rawData)
        print(msg)
        return None

    @classmethod
    def postDeserialization(cls):
        Logger.debug("POST-DES")


class PlayerIdentificationPacket(AbstractRequestPacket):
    ID = 0x00
    FORMAT = "BB64s64sB"
    CIRTICAL = True
    PLAYERLOOP = False
    MODULE = "Core"
    SIZE = struct.calcsize(FORMAT)

    @classmethod
    def deserialize(cls, rawData):
        # <Player Identification Packet>
        # (Byte) Packet ID
        # (Byte) Protocol Version
        # (64String) Username
        # (64String) Verification Key
        # (Byte) Unused
        _, protocolVersion, username, verificationKey, _ = struct.unpack(cls.FORMAT, rawData)
        # Unpackage String
        username = unpackageString(username)
        verificationKey = unpackageString(verificationKey)
        return protocolVersion, username, verificationKey

    @classmethod
    def postDeserialization(cls):
        pass


#
# Response Network Packets
#
class TestReturnPacket(AbstractResponsePacket):
    ID = 0x61
    FORMAT = "B5s"
    CIRTICAL = True
    MODULE = "Test"
    SIZE = struct.calcsize(FORMAT)

    @classmethod
    def serialize(cls):
        msg = bytes("ahello_there!\n", "ascii")
        print(msg)
        return msg

    @classmethod
    def postSterilization(cls):
        Logger.debug("POST-SER")


class ServerIdentificationPacket(AbstractResponsePacket):
    ID = 0x00
    FORMAT = "BB64s64sB"
    CIRTICAL = True
    MODULE = "Core"
    SIZE = struct.calcsize(FORMAT)

    @classmethod
    def serialize(cls, protocolVersion, name, motd, userType):
        # <Server Identification Packet>
        # (Byte) Packet ID
        # (Byte) Protocol Version
        # (64String) Server Name
        # (64String) Server MOTD
        # (Byte) User Type
        msg = struct.pack(cls.FORMAT, cls.ID, protocolVersion, packageString(name), packageString(motd), userType)
        return msg

    @classmethod
    def postSterilization(cls):
        pass


class PingPacket(AbstractResponsePacket):
    ID = 0x01
    FORMAT = "B"
    CIRTICAL = False
    MODULE = "Core"
    SIZE = struct.calcsize(FORMAT)

    @classmethod
    def serialize(cls):
        # <Ping Packet>
        # (Byte) Packet ID
        msg = struct.pack(cls.FORMAT, cls.ID)
        return msg

    @classmethod
    def postSterilization(cls):
        pass


class LevelInitializePacket(AbstractResponsePacket):
    ID = 0x02
    FORMAT = "B"
    CIRTICAL = True
    MODULE = "Core"
    SIZE = struct.calcsize(FORMAT)

    @classmethod
    def serialize(cls):
        # <Level Initialize Packet>
        # (Byte) Packet ID
        msg = struct.pack(cls.FORMAT, cls.ID)
        return msg

    @classmethod
    def postSterilization(cls):
        pass


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


def registerCoreModules(manager):  # manager accepts any class that supports the registerInit and registerPacket function
    # Run Register Initialization
    manager.registerInit("Test")
    manager.registerInit("Core")

    # Register Downsteam Packets
    manager.registerPacket(TestPacket)
    manager.registerPacket(PlayerIdentificationPacket)

    # Register Response Packets
    manager.registerPacket(TestReturnPacket)
    manager.registerPacket(ServerIdentificationPacket)
    manager.registerPacket(PingPacket)
    manager.registerPacket(LevelInitializePacket)
