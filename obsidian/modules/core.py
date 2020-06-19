from obsidian.module import Module, AbstractModule
from obsidian.constants import __version__
from obsidian.packet import (
    Packet,
    AbstractRequestPacket,
    AbstractResponsePacket,
    PacketDirections,
    unpackageString,
    packageString
)

import struct


@Module(
    "Core",
    description="Central Module For All Services",
    version=__version__
)
class CoreModule(AbstractModule):
    def __init__(self):
        super().__init__()

    @Packet(
        "PlayerIdentification",
        PacketDirections.REQUEST,
        description="Handle First Packet Sent By Player"
    )
    class PlayerIdentificationPacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x00,
                FORMAT="BB64s64sB",
                CIRTICAL=True,
                PLAYERLOOP=False
            )

        def deserialize(self, rawData):
            # <Player Identification Packet>
            # (Byte) Packet ID
            # (Byte) Protocol Version
            # (64String) Username
            # (64String) Verification Key
            # (Byte) Unused
            _, protocolVersion, username, verificationKey, _ = struct.unpack(self.FORMAT, rawData)
            # Unpackage String
            username = unpackageString(username)
            verificationKey = unpackageString(verificationKey)
            return protocolVersion, username, verificationKey

    @Packet(
        "ServerIdentification",
        PacketDirections.RESPONSE,
        description="Response Packet After Player Identification"
    )
    class ServerIdentificationPacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x00,
                FORMAT="BB64s64sB",
                CIRTICAL=True
            )

        def serialize(self, protocolVersion, name, motd, userType):
            # <Server Identification Packet>
            # (Byte) Packet ID
            # (Byte) Protocol Version
            # (64String) Server Name
            # (64String) Server MOTD
            # (Byte) User Type
            msg = struct.pack(self.FORMAT, self.ID, protocolVersion, packageString(name), packageString(motd), userType)
            return msg

    @Packet(
        "Ping",
        PacketDirections.RESPONSE,
        description="General Ping Packet To Test Network Connection"
    )
    class PingPacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x01,
                FORMAT="B",
                CIRTICAL=False
            )

        def serialize(self):
            # <Ping Packet>
            # (Byte) Packet ID
            msg = struct.pack(self.FORMAT, self.ID)
            return msg

    @Packet(
        "LevelInitialize",
        PacketDirections.RESPONSE,
        description="Packet To Begin World Data Transfer"
    )
    class LevelInitializePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x02,
                FORMAT="B",
                CIRTICAL=True
            )

        def serialize(self):
            # <Level Initialize Packet>
            # (Byte) Packet ID
            msg = struct.pack(self.FORMAT, self.ID)
            return msg
