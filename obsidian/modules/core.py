from obsidian.module import Module, AbstractModule
from obsidian.packet import Packet, AbstractRequestPacket, AbstractResponsePacket, PacketDirections


@Module("Core")
class CoreModule(AbstractModule):
    def __init__(self):
        print("dbg")
        print(self.__dict__.items())
        super().__init__()

    @Packet("PlayerIdentification", PacketDirections.REQUEST)
    class PlayerIdentificationPacket(AbstractRequestPacket):
        def __init__(self):
            print("lol")
            super().__init__(
                ID = 0x00,
                FORMAT = "BB64s64sB",
                CIRTICAL = True,
                PLAYERLOOP = False,
                MODULE = "Core",
                SIZE = 0
            )

        def doTheThing(self):
            print("yay!")

















'''



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
'''