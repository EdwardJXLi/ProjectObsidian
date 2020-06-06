import enum
from dataclasses import dataclass

# from obsidian.network import *
# from obsidian.constants import *
from obsidian.log import Logger

# Enums
class PacketDirections(enum.Enum):
    REQUEST = 0
    RESPONSE = 1


class _PacketManagerImplementation():
    def __init__(self):
        self._packet_list = {}
        self._packet_list[PacketDirections.REQUEST] = {}
        self._packet_list[PacketDirections.RESPONSE] = {}

    def register(self, name, direction, packet, module):
        obj = packet()
        obj.NAME = name
        obj.DIRECTION = direction
        obj.MODULE = module
        self._packet_list[direction][name] = obj

    def __getitem__(self, name):
        if(name in self._packet_list[PacketDirections.REQUEST]):
            return self._packet_list[PacketDirections.REQUEST][name]
        elif(name in self._packet_list[PacketDirections.REQUEST]):
            return self._packet_list[PacketDirections.REQUEST][name]
        else:
            raise EOFError

    def __getattr__(self, name):
        if(name in self._packet_list[PacketDirections.REQUEST]):
            return self._packet_list[PacketDirections.REQUEST][name]
        elif(name in self._packet_list[PacketDirections.REQUEST]):
            return self._packet_list[PacketDirections.REQUEST][name]
        else:
            raise EOFError


PacketManager = _PacketManagerImplementation()
Packets = PacketManager


# Packet Skeleton
@dataclass
class AbstractPacket:
    ID: int         # Packet Id
    FORMAT: str     # Packet Structure Format
    SIZE: int       # Packet Size
    CIRTICAL: bool  # Packet Criticality. Dictates What Event Should Occur When Error
    MODULE: str     # Packet Module Owner


@dataclass
class AbstractRequestPacket(AbstractPacket):
    PLAYERLOOP: bool             # Accept Packet During Player Loop
    DIRECTION: PacketDirections = PacketDirections.REQUEST  # Network Direction (Response or Response)


@dataclass
class AbstractResponsePacket(AbstractPacket):
    DIRECTION = PacketDirections.REQUEST  # Network Direction (Response or Response)


def Packet(name, direction):
    def internal(cls):
        cls.obsidian_packet = dict()
        cls.obsidian_packet["name"] = name
        cls.obsidian_packet["direction"] = direction
        cls.obsidian_packet["packet"] = cls
        return cls
    return internal


#Packet Utils
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


'''
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
    '''
