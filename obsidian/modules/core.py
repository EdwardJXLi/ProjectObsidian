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
from obsidian.world import AbstraceWorldGenerator, WorldGenerator

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
                CRITICAL=True,
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
                CRITICAL=True
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
                CRITICAL=False
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
                CRITICAL=True
            )

        def serialize(self):
            # <Level Initialize Packet>
            # (Byte) Packet ID
            msg = struct.pack(self.FORMAT, self.ID)
            return msg

    @Packet(
        "DisconnectPlayer",
        PacketDirections.RESPONSE,
        description="Packet Sent To Client To Force Disconnect"
    )
    class DisconnectPlayerPacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x0e,
                FORMAT="B64s",
                CRITICAL=True
            )

        def serialize(self, reason):
            # <Level Initialize Packet>
            # (Byte) Packet ID
            msg = struct.pack(self.FORMAT, self.ID, packageString(reason))
            return msg

    @WorldGenerator(
        "Flat",
        description="Default World Generator. Just Flat.",
        version="V1.0.0"
    )
    class FlatWorldGenerator(AbstraceWorldGenerator):
        def __init__(self):
            super().__init__()

        def generateWorld(self, sizeX, sizeY, sizeZ):
            mapData = bytearray(sizeX * sizeY * sizeZ)
            for x in range(256):
                for y in range(64):
                    for z in range(256):
                        mapData[x + 256 * (z + 256 * y)] = 0 if y > 32 else (2 if y == 32 else 3)
            return mapData
