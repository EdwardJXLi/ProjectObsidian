import enum
import struct

from obsidian.network import *
from obsidian.constants import *
from obsidian.log import *

#Enums
class PacketDirections(enum.Enum):
    UPSTREAM = 0
    DOWNSTREAM = 1

#Packet Skeleton
class Message:
    DIRECTION = None   #Network Direction (Upstream or Downstream)
    ID = None          #Packet Id
    SIZE = None        #Side (In Bytes) Of Packet
    CIRTICAL = None    #Criticality. Dictates What Event Should Occur When Error
    PLAYERLOOP = None  #Accept Packet During Player Loop
    MODULE = None      #Packet Module Owner

    def init(message):
        pass

    def serialize(*args, **kwargs):
        return None

    def postSterilization():
        pass

    def deserialize(*args, **kwargs):
        return None

    def postDesterilization():
        pass

#Downstream Network Packets
class TestPacket(Message):
    DIRECTION = PacketDirections.DOWNSTREAM
    ID = 0x61
    SIZE = 6
    CIRTICAL = True
    PLAYERLOOP = False
    MODULE = "Main"

    def deserialize(rawData):
        _, msg = struct.unpack("B5s", rawData)
        print(msg)
        return None

    def postDesterilization():
        Logger.debug("POST-DES")

#Upstream Netowrk Packets
class TestReturnPacket(Message):
    DIRECTION = PacketDirections.UPSTREAM
    ID = 0x61
    SIZE = 14
    CIRTICAL = True
    PLAYERLOOP = False
    MODULE = "Main"

    def sterilize():
        msg = bytes("ahello_there!\n", "ascii")
        print(msg)
        return msg

    def postSterilization():
        Logger.debug("POST-SER")

def registerCorePackets(manager):
    #Register Downsteam Packets
    manager.registerPacket(TestPacket)

    #Register Upstream Packets
    manager.registerPacket(TestReturnPacket)