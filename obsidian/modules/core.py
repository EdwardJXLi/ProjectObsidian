from obsidian.module import Module, AbstractModule
from obsidian.constants import ClientError, PacketError, __version__
from obsidian.log import Logger
from obsidian.player import Player
from obsidian.packet import (
    Packet,
    AbstractRequestPacket,
    AbstractResponsePacket,
    PacketDirections,
    unpackageString,
    packageString,
    StringStrictness
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

        async def deserialize(self, rawData: bytearray):
            # <Player Identification Packet>
            # (Byte) Packet ID
            # (Byte) Protocol Version
            # (64String) Username
            # (64String) Verification Key
            # (Byte) Unused
            _, protocolVersion, username, verificationKey, _ = struct.unpack(self.FORMAT, bytearray(rawData))

            # Unpackage String
            # Username
            try:
                username = unpackageString(username, strictness=StringStrictness.ALPHANUM)
            except PacketError:
                raise ClientError("Invalid Character In Username")
            # Verification String
            try:
                verificationKey = unpackageString(verificationKey, strictness=StringStrictness.PRINTABLE)
            except PacketError:
                raise ClientError("Invalid Character In Verification Key")

            # Check Username Length (Hard Capped At 16 To Prevent Length Bugs)
            if(len(username) > 16):
                raise ClientError("Your Username Is Too Long (Max 16 Chars)")

            return protocolVersion, username, verificationKey

    @Packet(
        "UpdateBlock",
        PacketDirections.REQUEST,
        description="Packet Received When Block Placed/Broken"
    )
    class UpdateBlockPacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x05,
                FORMAT="!BhhhBB",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Player, rawData: bytearray):
            # print("update block")
            return None  # TODO

    @Packet(
        "PlayerUpdate",
        PacketDirections.REQUEST,
        description="Received When Player Position And Orentation Is Sent"
    )
    class PlayerUpdatePacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x08,
                FORMAT="!BBhhhBB",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Player, rawData: bytearray):
            # print("player move")
            return None  # TODO

    @Packet(
        "PlayerMessage",
        PacketDirections.REQUEST,
        description="Received When Player Sends A Message"
    )
    class PlayerMessagePacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x0d,
                FORMAT="BB64s",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Player, rawData: bytearray):
            # <Player Message Packet>
            # (Byte) Packet ID
            # (Byte) Unused (Should Always Be 0xFF)
            # (64String) Message
            _, _, message = struct.unpack(self.FORMAT, bytearray(rawData))

            # Unpackage String
            # Message
            try:
                message = unpackageString(message, strictness=StringStrictness.PRINTABLE)
            except PacketError:
                raise ClientError("Invalid Character In Message")

            # Check If Last Character Is '&' (Crashes All Clients)
            if message[-1:] == "&":
                message = message[:-1]  # Cut Last Colour

            return None  # Nothing should be returned

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

        async def serialize(self, protocolVersion: int, name: str, motd: str, userType: int):
            # <Server Identification Packet>
            # (Byte) Packet ID
            # (Byte) Protocol Version
            # (64String) Server Name
            # (64String) Server MOTD
            # (Byte) User Type
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(protocolVersion),
                bytearray(packageString(name)),
                bytearray(packageString(motd)),
                int(userType)
            )
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

        async def serialize(self, chunk: bytearray, percentComplete: int = 0):
            # <Level Data Chunk Packet>
            # (Byte) Packet ID
            # (Short) Chunk Size
            # (1024ByteArray) Chunk Data
            # (Byte) Percent Complete

            # Chunks have to be padded by 0x00s
            formattedChunk = bytearray(chunk).ljust(1024, b'\0')

            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(len(chunk)),
                bytearray(formattedChunk),
                int(percentComplete)
            )
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

        async def serialize(self, sizeX: int, sizeY: int, sizeZ: int):
            # <Level Initialize Packet>
            # (Byte) Packet ID
            # (Short) X Size
            # (Short) Y Size
            # (Short) Z Size
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(sizeX),
                int(sizeY),
                int(sizeZ)
            )
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

        async def serialize(self, blockX: int, blockY: int, blockZ: int, blockType: int):
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

        async def serialize(self, playerId: int, playerName: str, x: int, y: int, z: int, yaw: int, pitch: int):
            # <Spawn Player Packet>
            # (Byte) Packet ID
            # (Signed Byte) Player ID
            # (64String) Player Name
            # (Short) Spawn X Coords
            # (Short) Spawn Y Coords
            # (Short) Spawn Z Coords
            # (Byte) Spawn Yaw
            # (Byte) Spawn Pitch
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(playerId),
                bytearray(packageString(playerName)),
                int(x),
                int(y),
                int(z),
                int(yaw),
                int(pitch)
            )
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

        async def serialize(self, playerId: int):
            # <Despawn Player Packet>
            # (Byte) Packet ID
            # (Byte) Player ID
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(playerId)
            )
            return msg

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

        async def serialize(self, message: str, playerId: int = 0):
            # <Player Message Packet>
            # (Byte) Packet ID
            # (Byte) Player ID (Seems to be unused?)
            # (64String) Message
            if len(message) > 64:
                Logger.warn(f"Trying to send message {message} over 64 character limit!", module="packet-serializer")
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(playerId),
                bytearray(packageString(message))
            )
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

        async def serialize(self, reason: str):
            # <Player Disconnect Packet>
            # (Byte) Packet ID
            # (64String) Disconnect Reason
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                bytearray(packageString(reason))
            )
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
        def generateMap(self, sizeX: int, sizeY: int, sizeZ: int, grassHeight: int = 32):
            mapData = bytearray(sizeX * sizeY * sizeZ)
            for x in range(sizeX):
                for y in range(sizeY):
                    for z in range(sizeZ):
                        mapData[x + sizeZ * (z + sizeX * y)] = 0 if y > grassHeight else (2 if y == grassHeight else 3)
            return mapData
