from obsidian.module import Module, AbstractModule, ModuleManager
from obsidian.constants import MAX_MESSAGE_LENGTH, ClientError, ServerError, WorldFormatError, CommandError, __version__
from obsidian.log import Logger
from obsidian.player import Player
from obsidian.worldformat import AbstractWorldFormat, WorldFormat
from obsidian.world import World, WorldManager
from obsidian.mapgen import AbstractMapGenerator, MapGenerator
from obsidian.commands import AbstractCommand, Command, CommandManager
from obsidian.blocks import AbstractBlock, BlockManager, Block, Blocks
from obsidian.packet import (
    RequestPacket,
    ResponsePacket,
    AbstractRequestPacket,
    AbstractResponsePacket,
    unpackageString,
    packageString
)

import inspect
import struct
import gzip
import math
import io
import os


@Module(
    "Core",
    description="Central Module For All Services",
    author="Obsidian",
    version=__version__
)
class CoreModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    #
    # REQUEST PACKETS
    #

    @RequestPacket(
        "PlayerIdentification",
        description="Handle First Packet Sent By Player"
    )
    class PlayerIdentificationPacket(AbstractRequestPacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x00,
                FORMAT="BB64s64sB",
                CRITICAL=True,
                PLAYERLOOP=False
            )

        async def deserialize(self, ctx: Player, rawData: bytearray):
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @RequestPacket(
        "UpdateBlock",
        description="Packet Received When Block Placed/Broken"
    )
    class UpdateBlockPacket(AbstractRequestPacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x05,
                FORMAT="!BhhhBB",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Player, rawData: bytearray):
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @RequestPacket(
        "MovementUpdate",
        description="Received When Player Position And Orentation Is Sent"
    )
    class MovementUpdatePacket(AbstractRequestPacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x08,
                FORMAT="!BBhhhBB",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Player, rawData: bytearray):
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @RequestPacket(
        "PlayerMessage",
        description="Received When Player Sends A Message"
    )
    class PlayerMessagePacket(AbstractRequestPacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    #
    # RESPONSE PACKETS
    #

    @ResponsePacket(
        "ServerIdentification",
        description="Response Packet After Player Identification"
    )
    class ServerIdentificationPacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "Ping",
        description="General Ping Packet To Test Network Connection"
    )
    class PingPacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x01,
                FORMAT="B",
                CRITICAL=False
            )

        async def serialize(self):
            # <Ping Packet>
            # (Byte) Packet ID
            msg = struct.pack(self.FORMAT, self.ID)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "LevelInitialize",
        description="Packet To Begin World Data Transfer"
    )
    class LevelInitializePacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x02,
                FORMAT="B",
                CRITICAL=True
            )

        async def serialize(self):
            # <Level Initialize Packet>
            # (Byte) Packet ID
            msg = struct.pack(self.FORMAT, self.ID)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "LevelDataChunk",
        description="Packet Containing Chunk Of Gzipped Map"
    )
    class LevelDataChunkPacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "LevelFinalize",
        description="Packet To Finish World Data Transfer"
    )
    class LevelFinalizePacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "SetBlock",
        description="Sent To Update Block Changes"
    )
    class SetBlockPacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "SpawnPlayer",
        description="Packet Sent To All Players Initializing Player Spawn"
    )
    class SpawnPlayerPacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "PlayerPositionUpdate",
        description="Sent To Update Player Position and Rotation"
    )
    class PlayerPositionUpdatePacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "PositionOrientationUpdate",
        description="Sent to Update Changes in Position and Orientation"
    )
    class PositionOrientationUpdatePacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x09,
                FORMAT="!BBbbbBB",
                CRITICAL=False
            )

        async def serialize(self):
            raise NotImplementedError(self)
            return None  # TODO

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "PositionUpdate",
        description="Sent to Update Changes in Position"
    )
    class PositionUpdatePacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0a,
                FORMAT="!BBbb",
                CRITICAL=False
            )

        async def serialize(self):
            raise NotImplementedError(self)
            return None  # TODO

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "OrientationUpdate",
        description="Sent to Update Changes in Orientation"
    )
    class OrientationUpdatePacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0b,
                FORMAT="!BBBB",
                CRITICAL=False
            )

        async def serialize(self):
            raise NotImplementedError(self)
            return None  # TODO

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "DespawnPlayer",
        description="Sent to Despawn Existing Player"
    )
    class DespawnPlayerPacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "SendMessage",
        description="Broadcasts Message To Player"
    )
    class SendMessagePacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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
                Logger.warn(f"Trying to send message '{message}' over the 64 character limit!", module="packet-serializer")
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(playerId),
                bytearray(packageString(message))
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "DisconnectPlayer",
        description="Packet Sent To Client To Force Disconnect"
    )
    class DisconnectPlayerPacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "UpdateUserType",
        description="Sent to Update User OP Status. User type is 0x64 for op, 0x00 for normal user."
    )
    class UserTypeUpdatePacket(AbstractResponsePacket):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0f,
                FORMAT="BB",
                CRITICAL=False
            )

        async def serialize(self, isOperator: bool = False):
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                0x64 if isOperator else 0x00
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    #
    # WORLD FORMATS
    #

    @WorldFormat(
        "Raw",
        description="Raw Map Data File (WORLD HAS TO BE 256x256x256)",
        version="v1.0.0"
    )
    class RawWorldFormat(AbstractWorldFormat):
        def __init__(self, *args):
            super().__init__(
                *args,
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

    #
    # MAP GENERATORS
    #

    @MapGenerator(
        "Flat",
        description="Default Map Generator. Just Flat.",
        version="v1.0.0"
    )
    class FlatMapGenerator(AbstractMapGenerator):
        def __init__(self, *args):
            super().__init__(*args)

        # Default Map Generator (Creates Flat Map Of Grass And Dirt)
        def generateMap(self, sizeX: int, sizeY: int, sizeZ: int, grassHeight: int = 32):
            mapData = bytearray(sizeX * sizeY * sizeZ)
            for x in range(sizeX):
                for y in range(sizeY):
                    for z in range(sizeZ):
                        mapData[x + sizeX * (z + sizeZ * y)] = Blocks.Air.ID if y > grassHeight else (Blocks.Grass.ID if y == grassHeight else Blocks.Dirt.ID)
            return mapData

    #
    # BLOCKS
    #

    @Block("Air")
    class Air(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=0)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Stone")
    class Stone(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=1)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Grass")
    class Grass(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=2)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Dirt")
    class Dirt(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=3)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Cobblestone")
    class Cobblestone(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=4)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Planks")
    class Planks(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=5)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Sapling")
    class Sapling(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=6)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Bedrock")
    class Bedrock(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=7)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("FlowingWater")
    class FlowingWater(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=8)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("StationaryWater")
    class StationaryWater(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=9)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("FlowingLava")
    class FlowingLava(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=10)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("StationaryLava")
    class StationaryLava(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=11)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Sand")
    class Sand(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=12)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Gravel")
    class Gravel(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=13)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("GoldOre")
    class GoldOre(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=14)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("IronOre")
    class IronOre(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=15)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("CoalOre")
    class CoalOre(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=16)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Wood")
    class Wood(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=17)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Leaves")
    class Leaves(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=18)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Sponge")
    class Sponge(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=19)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Glass")
    class Glass(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=20)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("RedCloth")
    class RedCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=21)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("OrangeCloth")
    class OrangeCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=22)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("YellowCloth")
    class YellowCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=23)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("ChartreuseCloth")
    class ChartreuseCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=24)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("GreenCloth")
    class GreenCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=25)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("SpringGreenCloth")
    class SpringGreenCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=26)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("CyanCloth")
    class CyanCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=27)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("CapriCloth")
    class CapriCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=28)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("UltramarineCloth")
    class UltramarineCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=29)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("VioletCloth")
    class VioletCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=30)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("PurpleCloth")
    class PurpleCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=31)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("MagentaCloth")
    class MagentaCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=32)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("RoseCloth")
    class RoseCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=33)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("DarkGrayCloth")
    class DarkGrayCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=34)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("LightGrayCloth")
    class LightGrayCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=35)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("WhiteCloth")
    class WhiteCloth(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=36)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Dandelion")
    class Dandelion(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=37)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Rose")
    class Rose(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=38)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("BrownMushroom")
    class BrownMushroom(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=39)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("RedMushroom")
    class RedMushroom(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=40)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("BlockGold")
    class BlockGold(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=41)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("BlockIron")
    class BlockIron(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=42)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("DoubleSlab")
    class DoubleSlab(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=43)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Slab")
    class Slab(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=44)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Bricks")
    class Bricks(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=45)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("TNT")
    class TNT(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=46)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Bookshelf")
    class Bookshelf(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=47)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("MossyCobblestone")
    class MossyCobblestone(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=48)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Obsidian")
    class Obsidian(AbstractBlock):
        def __init__(self, *args):
            super().__init__(*args, ID=49)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    #
    # COMMANDS
    #

    @Command(
        "Help",
        description="Generates a help command for users",
        version="v1.0.0"
    )
    class HelpCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["help", "commands", "cmds"])

        async def execute(self, ctx: Player, page: int = 1):
            # Get information on the number of commands, pages, and commands per page
            num_commands = len(CommandManager._command_list)  # This should never be zero as it should always count itself!
            commands_per_page = 4
            num_pages = math.ceil(num_commands / commands_per_page)
            current_page = page - 1

            # Check if user input was valid
            if page > num_pages or page <= 0:
                raise CommandError(f"&cThere are only {num_pages} pages of commands!&f")

            # Get a list of commands registed
            commands = tuple(CommandManager._command_list.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.generateCenteredMessage(f"&eHelp Page {page}/{num_pages}", colour="&2"))

            # Add some additional tips to help command
            output.append("&7Use /help [n] to get the nth page of help.&f")
            output.append("&7Use /helpcmd [name] to more information on a command&f")

            # Add command information
            for cmd_name, cmd in commands[current_page * commands_per_page:current_page * commands_per_page + commands_per_page]:
                help_message = f"&d[{cmd_name}] &e/{cmd.ACTIVATORS[0]}"
                if len(cmd.ACTIVATORS) > 1:
                    help_message += f" &7(Aliases: {', '.join(['/'+c for c in cmd.ACTIVATORS])})"
                help_message += "&f"
                output.append(help_message)
                output.append(f"{cmd.DESCRIPTION}")

            # Add Footer
            output.append(CommandHelper.generateCenteredMessage(f"&eTotal Commands: {num_commands}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "HelpCmd",
        description="Detailed help message for a specific command",
        version="v1.0.0"
    )
    class HelpCmdCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["helpcmd", "cmdhelp"])

        async def execute(self, ctx: Player, cmd_name: str):
            # Generate command output
            output = []

            # Get the command in question
            if cmd_name in CommandManager._command_list:
                # User is passing by command name
                cmd = CommandManager._command_list[cmd_name]
            elif cmd_name in CommandManager._activators:
                # User is passing by activator
                cmd = CommandManager._activators[cmd_name]
            else:
                # Command doesnt exist!
                raise CommandError(f"&cCommand {cmd_name} not found!&f")

            # Add Header
            output.append(CommandHelper.generateCenteredMessage(f"&eCommand Information: {cmd.NAME}", colour="&2"))

            # Add Command Description
            output.append(f"&d[Description]&f {cmd.DESCRIPTION}")

            # Generate Command Usage
            cmd_usage_str = f"&d[Usage] &e/{cmd.ACTIVATORS[0]}"
            # Loop through all arguments ** except for first ** (that is the ctx)
            for name, param in list(inspect.signature(cmd.execute).parameters.items())[1:]:
                # Code recycled from parseargs
                # Normal arguments use ""
                if param.kind == param.KEYWORD_ONLY:
                    cmd_usage_str += f" &b{name}"
                    if param.annotation != inspect._empty:
                        cmd_usage_str += f"&7({param.annotation.__name__})"
                # Optional arguments use []
                elif param.kind == param.POSITIONAL_OR_KEYWORD:
                    cmd_usage_str += f" &b[{name}"
                    if param.annotation != inspect._empty:
                        cmd_usage_str += f"&7({param.annotation.__name__})"
                    cmd_usage_str += "&b]"
                # Capture arguments use {}
                elif param.kind == param.VAR_POSITIONAL:
                    cmd_usage_str += f" &b{{{name}...}}"
                    if param.annotation != inspect._empty:
                        cmd_usage_str += f"&7({param.annotation.__name__})"
                else:
                    # This shouldnt really happen
                    raise ServerError(f"Unknown argument type {param.kind} while generating help command")

            cmd_usage_str += "&f"
            output.append(cmd_usage_str)
            output.append(CommandHelper.generateCenteredMessage(f"&ePlugin: {cmd.MODULE.NAME} v. {cmd.MODULE.VERSION}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "PluginsList",
        description="Lists all plugins/modules installed",
        version="v1.0.0"
    )
    class PulginsCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["plugins", "modules"])

        async def execute(self, ctx: Player, page: int = 1):
            # Get information on the number of modules, pages, and modules per page
            num_modules = len(ModuleManager._module_list)  # This should never be zero as it should always count itself!
            modules_per_page = 8
            num_pages = math.ceil(num_modules / modules_per_page)
            current_page = page - 1

            # Check if user input was valid
            if page > num_pages or page <= 0:
                raise CommandError(f"&cThere are only {num_pages} pages of modules!&f")

            # Get a list of modules registed
            modules = tuple(ModuleManager._module_list.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.generateCenteredMessage(f"&eHelp Page {page}/{num_pages}", colour="&2"))

            # Add command information
            for module_name, module in modules[current_page * modules_per_page:current_page * modules_per_page + modules_per_page]:
                output.append(f"&e{module_name}: &f{module.DESCRIPTION}")

            # Add Footer
            output.append(CommandHelper.generateCenteredMessage(f"&eTotal Modules: {num_modules}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListPlayers",
        description="Lists all online players",
        version="v1.0.0"
    )
    class ListPlayersCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["list", "players", "online"])

        async def execute(self, ctx: Player):
            if ctx.worldPlayerManager is None:
                raise CommandError("&cYou are not in a world!&f")

            players_list = ctx.worldPlayerManager.getPlayers()

            # If the list is empty, something un oh happened
            if len(players_list) == 0:
                raise ServerError("&cSomething went wrong while getting the list of players!&f")

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.generateCenteredMessage(f"&ePlayers Online: {len(players_list)}/{ctx.worldPlayerManager.world.maxPlayers}", colour="&2"))

            # Generate Player List Output
            output.append("&e")
            while players_list:
                player_name = players_list.pop(0).name
                if len(players_list) != 0:
                    player_name += ", "

                # Check if adding the player name will overflow the max message length
                if len(output[-1]) + len(player_name) > MAX_MESSAGE_LENGTH:
                    output.append("&e")  # Add a new line for output

                # Add Player Name
                output[-1] += player_name

            # Add Footer
            output.append(CommandHelper.generateCenteredMessage(f"&eWorld Name: {ctx.worldPlayerManager.world.name}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListStaff",
        description="Lists all online staff/operators",
        version="v1.0.0"
    )
    class ListStaffCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["liststaff", "staff", "operators", "listoperators"])

        async def execute(self, ctx: Player):
            if ctx.worldPlayerManager is None:
                raise CommandError("&cYou are not in a world!&f")

            players_list = ctx.worldPlayerManager.getPlayers()

            # If the list is empty, something un oh happened
            if len(players_list) == 0:
                raise ServerError("&cSomething went wrong while getting the list of players!&f")

            # Generate command output
            output = []

            # Filter List to Staff Only
            players_list = [player for player in players_list if player.opStatus is True]

            # Add Header
            output.append(CommandHelper.generateCenteredMessage(f"&eStaff Online: {len(players_list)}", colour="&2"))

            # Generate Player List Output
            output.append("&4")
            while players_list:
                player_name = players_list.pop(0).name
                if len(players_list) != 0:
                    player_name += ", "

                # Check if adding the player name will overflow the max message length
                if len(output[-1]) + len(player_name) > MAX_MESSAGE_LENGTH:
                    output.append("&4")  # Add a new line for output

                # Add Player Name
                output[-1] += player_name

            # Add Footer
            output.append(CommandHelper.generateCenteredMessage(f"&eWorld Name: {ctx.worldPlayerManager.world.name}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "MOTD",
        description="Prints Message of the Day",
        version="v1.0.0"
    )
    class MOTDCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["motd"])

        async def execute(self, ctx: Player):
            await ctx.sendMOTD()

    #
    # COMMANDS (OPERATORS ONLY)
    #

    @Command(
        "Operator",
        description="Sets A Player As An Operator",
        version="v1.0.0"
    )
    class OPCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["op", "setop", "operator"], OP=True)

        async def execute(self, ctx: Player, player_name: str):
            # Add Player To Operators List
            serverConfig = ctx.playerManager.server.config
            serverConfig.operatorsList.append(player_name.lower())
            serverConfig.save()

            # Propagate Operator Status
            await ctx.playerManager.propagateOperatorStatus()

            # Send Response Back
            await ctx.sendMessage(f"Player {player_name} Added To Operators List")

    @Command(
        "DeOperator",
        description="Removes A Player As An Operator",
        version="v1.0.0"
    )
    class DEOPCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["deop", "removeop", "deoperator"], OP=True)

        async def execute(self, ctx: Player, player_name: str):
            # Add Player To Operators List
            serverConfig = ctx.playerManager.server.config
            if player_name not in serverConfig.operatorsList:
                raise CommandError(f"&cPlayer {player_name} is not an operator!&f")

            serverConfig.operatorsList.remove(player_name.lower())
            serverConfig.save()

            # Propagate Operator Status
            await ctx.playerManager.propagateOperatorStatus()

            # Send Response Back
            await ctx.sendMessage(f"Player {player_name} Removed From Operators List")

    @Command(
        "ReloadConfig",
        description="Forces a reload of the config",
        version="v1.0.0"
    )
    class ReloadConfigCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reloadconfig"], OP=True)

        async def execute(self, ctx: Player):
            # Reload Config
            serverConfig = ctx.playerManager.server.config
            serverConfig.reload()

            # Repropagate Operator Status
            await ctx.playerManager.propagateOperatorStatus()

            # Send Response Back
            await ctx.sendMessage("Config Reloaded!")

    @Command(
        "StopServer",
        description="Stops the server",
        version="v1.0.0"
    )
    class StopServerCommand(AbstractCommand):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["stop"], OP=True)

        async def execute(self, ctx: Player):
            await ctx.sendMessage("Stopping Server")
            await ctx.playerManager.server.stop()


# Helper functions for the command generation
class CommandHelper():
    @staticmethod
    def generateCenteredMessage(message: str, colour: str = "", padCharacter: str = "="):
        # Calculate the number of padding to add
        max_message_length = 64
        pad_space = max(
            max_message_length - len(message) - 2 * (len(colour) + 1) - 2,
            0  # Maxing at zero in case the final output goes into the negatives
        )
        pad_left = pad_space // 2
        pad_right = pad_space - pad_left

        # Generate and return padded message
        return (colour + padCharacter * pad_left) + (" " + message + " ") + (colour + padCharacter * pad_right) + "&f"
