from obsidian.module import Module, AbstractModule
from obsidian.constants import __version__
from obsidian.log import Logger
from obsidian.packet import (
    Packet,
    AbstractRequestPacket,
    AbstractResponsePacket,
    PacketDirections,
    unpackageString,
    packageString
)
from obsidian.mapgen import (
    AbstractMapGenerator,
    MapGenerator
)

import struct


@Module(
    "Core",
    description="Central Module For All Services",
    author="Obsidian",
    version=__version__
)
class CoreModule(AbstractModule):
    def __init__(self):
        super().__init__()

    #
    # REQUEST PACKETS
    #

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

        async def deserialize(self, rawData):
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
        "UpdateBlock",
        PacketDirections.REQUEST,
        description="Packet Sent When Block Placed/Broken"
    )
    class UpdateBlockPacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x05,
                FORMAT="!BhhhBB",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, rawData):
            # print("update block")
            return None  # TODO

    @Packet(
        "PlayerUpdate",
        PacketDirections.REQUEST,
        description="Sent When Player Position And Orentation Is Sent"
    )
    class PlayerUpdatePacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x08,
                FORMAT="!BBhhhBB",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, rawData):
            # print("player move")
            return None  # TODO

    @Packet(
        "ReceiveMessage",
        PacketDirections.REQUEST,
        description="Sent When Player Sends A Message"
    )
    class ReceiveMessagePacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x0d,
                FORMAT="BB64s",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, rawData):
            # print("send message")
            return None  # TODO

    #
    # RESPONSE PACKETS
    #

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

        async def serialize(self, protocolVersion, name, motd, userType):
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

        async def serialize(self):
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

        async def serialize(self):
            # <Level Initialize Packet>
            # (Byte) Packet ID
            msg = struct.pack(self.FORMAT, self.ID)
            return msg

    @Packet(
        "LevelDataChunk",
        PacketDirections.RESPONSE,
        description="Packet Containing Chunk Of Gzipped Map"
    )
    class LevelDataChunkPacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x03,
                FORMAT="!Bh1024sB",
                CRITICAL=True
            )

        async def serialize(self, chunk, percentComplete=0):
            # <Level Data Chunk Packet>
            # (Byte) Packet ID
            # (Short) Chunk Size
            # (1024ByteArray) Chunk Data
            # (Byte) Percent Complete

            # Chunks have to be padded by 0x00s
            formattedChunk = bytes(chunk).ljust(1024, b'\0')

            msg = struct.pack(self.FORMAT, self.ID, len(chunk), formattedChunk, percentComplete)
            return msg

    @Packet(
        "LevelFinalize",
        PacketDirections.RESPONSE,
        description="Packet To Finish World Data Transfer"
    )
    class LevelFinalizePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x04,
                FORMAT="!Bhhh",
                CRITICAL=True
            )

        async def serialize(self, sizeX, sizeY, sizeZ):
            # <Level Initialize Packet>
            # (Byte) Packet ID
            # (Short) X Size
            # (Short) Y Size
            # (Short) Z Size
            msg = struct.pack(self.FORMAT, self.ID, sizeX, sizeY, sizeZ)
            return msg

    @Packet(
        "SetBlock",
        PacketDirections.RESPONSE,
        description="Sent To Update Block Changes"
    )
    class SetBlockPacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x06,
                FORMAT="!BhhhB",
                CRITICAL=False
            )

        async def serialize(self, blockX, blockY, blockZ, blockType):
            return None  # TODO

    @Packet(
        "SpawnPlayer",
        PacketDirections.RESPONSE,
        description="Packet Sent To All Players Initializing Player Spawn"
    )
    class SpawnPlayerPacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x07,
                FORMAT="!BB64shhhBB",
                CRITICAL=True
            )

        async def serialize(self, playerId, playerName, x, y, z, yaw, pitch):
            # <Spawn Player Packet>
            # (Byte) Packet ID
            # (Signed Byte) Player ID
            # (64String) Player Name
            # (Short) Spawn X Coords
            # (Short) Spawn Y Coords
            # (Short) Spawn Z Coords
            # (Byte) Spawn Yaw
            # (Byte) Spawn Pitch
            msg = struct.pack(self.FORMAT, self.ID, playerId, packageString(playerName), x, y, z, yaw, pitch)
            return msg

    @Packet(
        "PlayerMovementUpdate",
        PacketDirections.RESPONSE,
        description="Sent To Update Player Position and Rotation"
    )
    class PlayerMovementUpdatePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x08,
                FORMAT="!BBhhhBB",
                CRITICAL=False
            )

        async def serialize(self):
            return None  # TODO

    @Packet(
        "PositionOrientationUpdate",
        PacketDirections.RESPONSE,
        description="Sent to Update Changes in Position and Orientation"
    )
    class PositionOrientationUpdatePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x09,
                FORMAT="!BBbbbBB",
                CRITICAL=False
            )

        async def serialize(self):
            return None  # TODO

    @Packet(
        "PositionUpdate",
        PacketDirections.RESPONSE,
        description="Sent to Update Changes in Position"
    )
    class PositionUpdatePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x0a,
                FORMAT="!BBbb",
                CRITICAL=False
            )

        async def serialize(self):
            return None  # TODO

    @Packet(
        "OrientationUpdate",
        PacketDirections.RESPONSE,
        description="Sent to Update Changes in Orientation"
    )
    class OrientationUpdatePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x0b,
                FORMAT="!BBBB",
                CRITICAL=False
            )

        async def serialize(self):
            return None  # TODO

    @Packet(
        "DespawnPlayer",
        PacketDirections.RESPONSE,
        description="Sent to Despawn Existing Player"
    )
    class DespawnPlayerPacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x0c,
                FORMAT="BB",
                CRITICAL=True
            )

        async def serialize(self):
            return None  # TODO

    @Packet(
        "SendMessage",
        PacketDirections.RESPONSE,
        description="Broadcasts Message To Player"
    )
    class SendMessagePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x0d,
                FORMAT="BB64s",
                CRITICAL=False
            )

        async def serialize(self, message, playerId=0):
            # <Player Message Packet>
            # (Byte) Packet ID
            # (Byte) Player ID (Seems to be unused?)
            # (64String) Message
            if len(message) > 64:
                Logger.warn(f"Trying to send message {message} over 64 character limit!", module="packet-serializer")
            msg = struct.pack(self.FORMAT, self.ID, playerId, packageString(message))
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

        async def serialize(self, reason):
            # <Player Disconnect Packet>
            # (Byte) Packet ID
            # (64String) Disconnect Reason
            msg = struct.pack(self.FORMAT, self.ID, packageString(reason))
            return msg

    @Packet(
        "UpdateUserType",
        PacketDirections.RESPONSE,
        description="Sent to Update User OP Status. User type is 0x64 for op, 0x00 for normal user."
    )
    class UpdateUserTypePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x0f,
                FORMAT="BB",
                CRITICAL=False
            )

        async def serialize(self):
            return None  # TODO

    #
    # Map GENERATORS
    #

    @MapGenerator(
        "Flat",
        description="Default Map Generator. Just Flat.",
        version="V1.0.0"
    )
    class FlatMapGenerator(AbstractMapGenerator):
        def __init__(self):
            super().__init__()

        # Default Map Generator (Creates Flat Map Of Grass And Dirt)
        def generateMap(self, sizeX, sizeY, sizeZ, grassHeight=32):
            mapData = bytearray(sizeX * sizeY * sizeZ)
            for x in range(sizeX):
                for y in range(sizeY):
                    for z in range(sizeZ):
                        mapData[x + sizeZ * (z + sizeX * y)] = 0 if y > grassHeight else (2 if y == grassHeight else 3)
            return mapData
