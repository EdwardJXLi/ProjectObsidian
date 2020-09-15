from obsidian.module import Module, AbstractModule
from obsidian.constants import ClientError, ServerError, WorldFormatError, __version__
from obsidian.log import Logger
from obsidian.player import Player
from obsidian.worldformat import AbstractWorldFormat, WorldFormat
from obsidian.world import World, WorldManager
from obsidian.mapgen import AbstractMapGenerator, MapGenerator
from obsidian.commands import AbstractCommand, Command
from obsidian.blocks import AbstractBlock, BlockManager, Block, Blocks
from obsidian.packet import (
    Packet,
    AbstractRequestPacket,
    AbstractResponsePacket,
    PacketDirections,
    unpackageString,
    packageString
)

import struct
import copy
import gzip
import io
import os
from typing import Optional


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

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray):
            # <Player Identification Packet>
            # (Byte) Packet ID
            # (Byte) Protocol Version
            # (64String) Username
            # (64String) Verification Key
            # (Byte) Unused
            _, protocolVersion, username, verificationKey, _ = struct.unpack(self.FORMAT, bytearray(rawData))

            # Unpackage String
            # Username
            username = unpackageString(username)
            if not username.isalnum():
                raise ClientError("Invalid Character In Username")
            # Verification String
            verificationKey = unpackageString(verificationKey)
            if not username.isprintable():
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

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray):
            # <Block Update Packet>
            # (Byte) Packet ID
            # (Short) X Position
            # (Short) Y Position
            # (Short) Z Position
            # (Byte) Mode
            # (Byte) Block Type
            _, blockX, blockY, blockZ, updateMode, blockId = struct.unpack(self.FORMAT, bytearray(rawData))

            # Get Block Types
            if updateMode == 0:  # updateMode 0 is Block Breaking (set to air)
                blockType = Blocks.Air
            else:
                # Get Block Object From Block ID
                blockType = BlockManager.getBlockById(blockId)

            # Handle Block Update
            await ctx.handleBlockUpdate(blockX, blockY, blockZ, blockType)

            return None  # Nothing should be returned

    @Packet(
        "MovementUpdate",
        PacketDirections.REQUEST,
        description="Received When Player Position And Orentation Is Sent"
    )
    class MovementUpdatePacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x08,
                FORMAT="!BBhhhBB",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray):
            # <Player Movement Packet>
            # (Byte) Packet ID
            # (Byte) Player ID  <- Should Always Be 255
            # (Short) X Position
            # (Short) Y Position
            # (Short) Z Position
            # (Byte) Yaw
            # (Byte) Pitch
            _, _, posX, posY, posZ, posYaw, posPitch = struct.unpack(self.FORMAT, bytearray(rawData))

            # Handle Player Movement
            await ctx.handlePlayerMovement(posX, posY, posZ, posYaw, posPitch)

            return None  # Nothing should be returned

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

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray):
            # <Player Message Packet>
            # (Byte) Packet ID
            # (Byte) Unused (Should Always Be 0xFF)
            # (64String) Message
            _, _, message = struct.unpack(self.FORMAT, bytearray(rawData))

            # Check if player was passed
            if ctx is None:
                raise ServerError("Player Context Was Not Passed!")

            # Unpackage String
            # Message
            message = unpackageString(message)
            if not message.isprintable():
                await ctx.sendMessage("&4ERROR: Message Failed To Send - Invalid Character In Message&f")
                return None  # Don't Complete Message Sending

            # Handle Player Message
            await ctx.handlePlayerMessage(message)

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
            # <Set Block Packet>
            # (Byte) Packet ID=
            # (Short) Block X Coords
            # (Short) Block Y Coords
            # (Short) Block Z Coords
            # (Byte) Block Id
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(blockX),
                int(blockY),
                int(blockZ),
                int(blockType),
            )
            return msg

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
        "PlayerPositionUpdate",
        PacketDirections.RESPONSE,
        description="Sent To Update Player Position and Rotation"
    )
    class PlayerPositionUpdatePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x08,
                FORMAT="!BBhhhBB",
                CRITICAL=False
            )

        async def serialize(self, playerId: int, x: int, y: int, z: int, yaw: int, pitch: int):
            # <Player Movement Packet>
            # (Byte) Packet ID
            # (Signed Byte) Player ID
            # (Short) Spawn X Coords
            # (Short) Spawn Y Coords
            # (Short) Spawn Z Coords
            # (Byte) Spawn Yaw
            # (Byte) Spawn Pitch
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(playerId),
                int(x),
                int(y),
                int(z),
                int(yaw),
                int(pitch)
            )
            return msg

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
            raise NotImplementedError(self)
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
            raise NotImplementedError(self)
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
            raise NotImplementedError(self)
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
    class UserTypeUpdatePacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0x0f,
                FORMAT="BB",
                CRITICAL=False
            )

        async def serialize(self):
            return None  # TODO

    #
    # WORLD FORMATS
    #

    @WorldFormat(
        "Raw",
        description="Raw Map Data File (WORLD HAS TO BE 256x256x256)",
        version="v1.0.0"
    )
    class RawWorldFormat(AbstractWorldFormat):
        def __init__(self):
            super().__init__(
                KEYS=["raw"],
                EXTENTIONS=["gz"]
            )

        def loadWorld(
            self,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager,
            persistant: bool = True
        ):
            rawData = gzip.GzipFile(fileobj=fileIO).read()
            # Expected Map Size (MAX SIZE)
            fileSize = 256 * 256 * 256
            # Check If Given Map Is Largest Size
            if len(rawData) != fileSize:
                raise WorldFormatError(f"RawWorldFormat - Invalid World Size {len(rawData)}! Expected: {fileSize} (256 x 256 x 256)")

            # Create World Data
            return World(
                worldManager,  # Pass In World Manager
                os.path.splitext(os.path.basename(fileIO.name))[0],  # Pass In World Name (Save File Name Without EXT)
                256, 256, 256,  # Passing World X, Y, Z
                bytearray(rawData),  # Generating Map Data
                persistant=persistant,  # Pass In Persistant Flag
                fileIO=fileIO  # Pass In File Reader/Writer
            )

        def saveWorld(
            self,
            world: World,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager
        ):
            # Checking if file size matches!
            if not (world.sizeX == 256 and world.sizeY == 256 and world.sizeZ == 256):
                raise WorldFormatError(f"RawWorldFormat - Trying to save world that has invalid world size! Expected: 256, 256, 256! Got: {world.sizeX}, {world.sizeY}, {world.sizeZ}!")

            # Clearing Current Save File
            fileIO.truncate(0)
            fileIO.seek(0)
            # Saving Map To File
            fileIO.write(world.gzipMap())

    @WorldFormat(
        "Basic",
        description="Basic World Format That Stores X, Y, Z, Size, and Map Data",
        version="v1.0.0"
    )
    class BasicWorldFormat(AbstractWorldFormat):
        def __init__(self):
            super().__init__(
                KEYS=["basic"],
                EXTENTIONS=["bw"]
            )

    #
    # MAP GENERATORS
    #

    @MapGenerator(
        "Flat",
        description="Default Map Generator. Just Flat.",
        version="v1.0.0"
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
                        mapData[x + sizeX * (z + sizeZ * y)] = Blocks.Air.ID if y > grassHeight else (Blocks.Grass.ID if y == grassHeight else Blocks.Dirt.ID)
            return mapData

    #
    # COMMANDS
    #

    @Command(
        "Test",
        activators=["test"],
        description="Test Command",
        version="v1.0.0"
    )
    class TestCommand(AbstractCommand):
        def __init__(self):
            super().__init__()

        async def execute(self, ctx: Optional[Player]):
            # Check if player was passed
            if ctx is None:
                raise ServerError("Player Context Was Not Passed!")

            # Handle Player Message
            await ctx.sendMessage("Test Command Received")

            return None  # Nothing should be returned

    #
    # BLOCKS
    #

    # List Of Blocks To Be Registered
    blockList = [
        "Air",
        "Stone",
        "Grass",
        "Dirt",
        "Cobblestone",
        "Planks",
        "Sapling",
        "Bedrock",
        "FlowingWater",
        "StationaryWater",
        "FlowingLava",
        "StationaryLava",
        "Sand",
        "Gravel",
        "GoldOre",
        "IronOre",
        "CoalOre",
        "Wood",
        "Leaves",
        "Sponge",
        "Glass",
        "RedCloth",
        "OrangeCloth",
        "YellowCloth",
        "ChartreuseCloth",
        "GreenCloth",
        "Spring GreenCloth",
        "CyanCloth",
        "CapriCloth",
        "UltramarineCloth",
        "VioletCloth",
        "PurpleCloth",
        "MagentaCloth",
        "RoseCloth",
        "DarkGrayCloth",
        "LightGrayCloth",
        "WhiteCloth",
        "Dandelion",
        "Rose",
        "BrownMushroom",
        "RedMushroom",
        "BlockGold",
        "BlockIron",
        "DoubleSlab",
        "Slab",
        "Bricks",
        "TNT",
        "Bookshelf",
        "MossyCobblestone",
        "Obsidian"
    ]

    # Loop Through All Blocks And Register Block
    for blockId, block in enumerate(blockList):
        # Add Block To Local Scope
        # TODO: HACKY

        # Dynamically Create Class
        @Block(block, blockId)
        class CoreBlock(AbstractBlock):
            def __init__(self):
                super().__init__()

        # Deep Copy Object Into Local Scope With Custom Name
        locals()["CoreBlock" + block] = copy.deepcopy(CoreBlock)

        # Delete Existing CoreBlock To Prevent Redefinitions
        del CoreBlock
