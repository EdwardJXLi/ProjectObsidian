from obsidian.module import Module, AbstractModule, ModuleManager
from obsidian.constants import MAX_MESSAGE_LENGTH, __version__
from obsidian.errors import ClientError, ServerError, WorldFormatError, CommandError
from obsidian.types import _formatUsername, _formatIp
from obsidian.log import Logger
from obsidian.player import Player
from obsidian.worldformat import AbstractWorldFormat, WorldFormat
from obsidian.world import World, WorldManager
from obsidian.mapgen import AbstractMapGenerator, MapGenerator
from obsidian.commands import AbstractCommand, Command, Commands, CommandManager, _typeToString
from obsidian.blocks import AbstractBlock, BlockManager, Block, Blocks
from obsidian.packet import (
    RequestPacket,
    ResponsePacket,
    AbstractRequestPacket,
    AbstractResponsePacket,
    unpackageString,
    packageString
)

from typing import Optional, Iterable, Callable, Any
from pathlib import Path
import inspect
import struct
import gzip
import math
import io


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
    class PlayerIdentificationPacket(AbstractRequestPacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
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

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @RequestPacket(
        "UpdateBlock",
        description="Packet Received When Block Placed/Broken"
    )
    class UpdateBlockPacket(AbstractRequestPacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
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

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

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
    class MovementUpdatePacket(AbstractRequestPacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
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

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

            # Handle Player Movement
            await ctx.handlePlayerMovement(posX, posY, posZ, posYaw, posPitch)

            return None  # Nothing should be returned

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @RequestPacket(
        "PlayerMessage",
        description="Received When Player Sends A Message"
    )
    class PlayerMessagePacket(AbstractRequestPacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
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

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

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
    class ServerIdentificationPacket(AbstractResponsePacket["CoreModule"]):
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
    class PingPacket(AbstractResponsePacket["CoreModule"]):
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
    class LevelInitializePacket(AbstractResponsePacket["CoreModule"]):
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
    class LevelDataChunkPacket(AbstractResponsePacket["CoreModule"]):
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
    class LevelFinalizePacket(AbstractResponsePacket["CoreModule"]):
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
    class SetBlockPacket(AbstractResponsePacket["CoreModule"]):
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
    class SpawnPlayerPacket(AbstractResponsePacket["CoreModule"]):
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
    class PlayerPositionUpdatePacket(AbstractResponsePacket["CoreModule"]):
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
    class PositionOrientationUpdatePacket(AbstractResponsePacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x09,
                FORMAT="!BBbbbBB",
                CRITICAL=False
            )

        async def serialize(self):
            raise NotImplementedError(self)  # TODO

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "PositionUpdate",
        description="Sent to Update Changes in Position"
    )
    class PositionUpdatePacket(AbstractResponsePacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0a,
                FORMAT="!BBbb",
                CRITICAL=False
            )

        async def serialize(self):
            raise NotImplementedError(self)  # TODO

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "OrientationUpdate",
        description="Sent to Update Changes in Orientation"
    )
    class OrientationUpdatePacket(AbstractResponsePacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0b,
                FORMAT="!BBBB",
                CRITICAL=False
            )

        async def serialize(self):
            raise NotImplementedError(self)  # TODO

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "DespawnPlayer",
        description="Sent to Despawn Existing Player"
    )
    class DespawnPlayerPacket(AbstractResponsePacket["CoreModule"]):
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
    class SendMessagePacket(AbstractResponsePacket["CoreModule"]):
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

            # Format Message Packet
            packedMessage = packageString(message)
            if len(packedMessage) > 0 and packedMessage[-1] == ord("&"):  # Using the ascii value as it is packed into a bytearray already
                Logger.warn(f"Trying to send message '{message}' with '&' as the last character!", module="packet-serializer")
                packedMessage = packedMessage[:-1]

            # Send Message Packet
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(playerId),
                bytearray(packedMessage)
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "DisconnectPlayer",
        description="Packet Sent To Client To Force Disconnect"
    )
    class DisconnectPlayerPacket(AbstractResponsePacket["CoreModule"]):
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
    class UserTypeUpdatePacket(AbstractResponsePacket["CoreModule"]):
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
    class RawWorldFormat(AbstractWorldFormat["CoreModule"]):
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
                Path(fileIO.name).stem,  # Pass In World Name (Save File Name Without EXT)
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
    class FlatMapGenerator(AbstractMapGenerator["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args)

        # Default Map Generator (Creates Flat Map Of Grass And Dirt)
        def generateMap(self, sizeX: int, sizeY: int, sizeZ: int, grassHeight: int = 32):
            mapData = bytearray(sizeX * sizeY * sizeZ)
            for x in range(sizeX):
                for y in range(sizeY):
                    for z in range(sizeZ):
                        mapData[x + sizeX * (sizeZ * y + z)] = Blocks.Air.ID if y > grassHeight else (Blocks.Grass.ID if y == grassHeight else Blocks.Dirt.ID)
            return mapData

    #
    # BLOCKS
    #

    @Block("Air")
    class Air(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=0)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Stone")
    class Stone(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=1)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Grass")
    class Grass(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=2)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Dirt")
    class Dirt(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=3)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Cobblestone")
    class Cobblestone(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=4)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Planks")
    class Planks(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=5)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Sapling")
    class Sapling(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=6)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Bedrock")
    class Bedrock(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=7)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("FlowingWater")
    class FlowingWater(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=8)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("StationaryWater")
    class StationaryWater(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=9)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("FlowingLava")
    class FlowingLava(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=10)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("StationaryLava")
    class StationaryLava(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=11)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Sand")
    class Sand(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=12)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Gravel")
    class Gravel(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=13)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("GoldOre")
    class GoldOre(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=14)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("IronOre")
    class IronOre(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=15)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("CoalOre")
    class CoalOre(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=16)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Wood")
    class Wood(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=17)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Leaves")
    class Leaves(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=18)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Sponge")
    class Sponge(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=19)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Glass")
    class Glass(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=20)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("RedCloth")
    class RedCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=21)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("OrangeCloth")
    class OrangeCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=22)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("YellowCloth")
    class YellowCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=23)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("ChartreuseCloth")
    class ChartreuseCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=24)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("GreenCloth")
    class GreenCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=25)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("SpringGreenCloth")
    class SpringGreenCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=26)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("CyanCloth")
    class CyanCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=27)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("CapriCloth")
    class CapriCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=28)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("UltramarineCloth")
    class UltramarineCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=29)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("VioletCloth")
    class VioletCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=30)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("PurpleCloth")
    class PurpleCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=31)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("MagentaCloth")
    class MagentaCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=32)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("RoseCloth")
    class RoseCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=33)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("DarkGrayCloth")
    class DarkGrayCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=34)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("LightGrayCloth")
    class LightGrayCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=35)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("WhiteCloth")
    class WhiteCloth(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=36)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Dandelion")
    class Dandelion(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=37)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Rose")
    class Rose(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=38)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("BrownMushroom")
    class BrownMushroom(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=39)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("RedMushroom")
    class RedMushroom(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=40)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("BlockGold")
    class BlockGold(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=41)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("BlockIron")
    class BlockIron(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=42)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("DoubleSlab")
    class DoubleSlab(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=43)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Slab")
    class Slab(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=44)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Bricks")
    class Bricks(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=45)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("TNT")
    class TNT(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=46)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Bookshelf")
    class Bookshelf(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=47)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("MossyCobblestone")
    class MossyCobblestone(AbstractBlock["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ID=48)

        async def placeBlock(self, *args, **kwargs):
            return await super().placeBlock(*args, **kwargs)

    @Block("Obsidian")
    class Obsidian(AbstractBlock["CoreModule"]):
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
    class HelpCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["help", "commands", "cmds"])

        async def execute(self, ctx: Player, page_or_command: int | str = 1):
            # If command is not an int, assume its a command name and print help for that
            if isinstance(page_or_command, str) and not page_or_command.isnumeric():
                return await Commands.HelpCmd.execute(ctx, cmd_name=page_or_command)

            # Alias & Convert
            page = int(page_or_command)
            # Generate and Parse list of commands
            cmd_list = CommandManager._command_dict
            # If user is not OP, filter out OP and Disabled commands
            if not ctx.opStatus:
                cmd_list = {k: v for k, v in cmd_list.items() if (not v.OP) and (v.NAME not in ctx.playerManager.server.config.disabledCommands)}

            # Get information on the number of commands, pages, and commands per page
            num_commands = len(cmd_list)  # This should never be zero as it should always count itself!
            commands_per_page = 4
            num_pages = math.ceil(num_commands / commands_per_page)
            current_page = page - 1

            # Check if user input was valid
            if page > num_pages or page <= 0:
                raise CommandError(f"&cThere are only {num_pages} pages of commands!&f")

            # Get a list of commands registed
            commands = tuple(cmd_list.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.center_message(f"&eHelp Page {page}/{num_pages}", colour="&2"))

            # Add some additional tips to help command
            output.append("&7Use /help [n] to get the nth page of help.&f")
            output.append("&7Use /help or /helpcmd [name] to get more info on a command&f")

            # Add command information
            for cmd_name, cmd in commands[current_page * commands_per_page:current_page * commands_per_page + commands_per_page]:
                help_message = f"&d[{cmd_name}] &e/{cmd.ACTIVATORS[0]}"
                if cmd.OP:
                    help_message = "&4[OP] " + help_message
                if cmd.NAME in ctx.server.config.disabledCommands:
                    help_message = "&4[DISABLED] " + help_message
                if len(cmd.ACTIVATORS) > 1:
                    help_message += f" &7(Aliases: {', '.join(['/'+c for c in cmd.ACTIVATORS][1:])})"
                help_message += "&f"
                output.append(help_message)
                output.append(f"{cmd.DESCRIPTION}")

            # Add Footer
            output.append(CommandHelper.center_message(f"&eTotal Commands: {num_commands}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "HelpCmd",
        description="Detailed help message for a specific command",
        version="v1.0.0"
    )
    class HelpCmdCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["helpcmd", "cmdhelp"])

        async def execute(self, ctx: Player, cmd_name: str):
            # Generate command output
            output = []

            # Get the command in question
            if cmd_name in CommandManager._command_dict:
                # User is passing by command name
                cmd = CommandManager._command_dict[cmd_name]
            elif cmd_name in CommandManager._activators:
                # User is passing by activator
                cmd = CommandManager._activators[cmd_name.lower()]
            else:
                # Command doesnt exist!
                raise CommandError(f"&cCommand {cmd_name} not found!&f")

            # If command is an operator-only command and if user is not operator, return error
            if cmd.OP and not ctx.opStatus:
                raise CommandError(f"&cCommand {cmd_name} not found!&f")  # Fake "Not Found" Error

            # Add Header
            output.append(CommandHelper.center_message(f"&eCommand Information: {cmd.NAME}", colour="&2"))

            # Add Command Description
            if cmd.DESCRIPTION:
                output.append(f"&d[Description]&f {cmd.DESCRIPTION}")

            # Add Command Version
            if cmd.VERSION:
                output.append(f"&d[Version]&f {cmd.VERSION}")

            # If Command has a Documentation String, Add it on!
            if cmd.__doc__:
                output.append("&d[Documentation]")
                output += [line.strip() for line in cmd.__doc__.strip().splitlines()]

            # Generate Command Usage
            param_usages = []
            # Loop through all arguments ** except for first ** (that is the ctx)
            for name, param in list(inspect.signature(cmd.execute).parameters.items())[1:]:
                param_str = " "
                # Code recycled from parseargs
                # Normal Arguments (Nothing Special)
                if param.kind == param.POSITIONAL_OR_KEYWORD:
                    # Required arguments use ""
                    if param.default == inspect._empty:
                        param_str += f"&b{name}"
                        if param.annotation != inspect._empty:
                            param_str += f"&7({_typeToString(param.annotation)})"
                    # Optional arguments use []
                    else:
                        param_str += f"&b[{name}"
                        if param.annotation != inspect._empty:
                            param_str += f"&7({_typeToString(param.annotation)})"
                        param_str += f"&b=&6{param.default}&b]"
                # Capture arguments use {}
                elif param.kind == param.VAR_POSITIONAL or param.kind == param.KEYWORD_ONLY:
                    param_str += f"&b{{{name}..."
                    if param.annotation != inspect._empty:
                        param_str += f"&7({_typeToString(param.annotation)})"
                    param_str += "&b}"
                else:
                    # This shouldnt really happen
                    raise ServerError(f"Unknown argument type {param.kind} while generating help command")

                # Add the formatted text to the list of other formatted texts
                param_usages.append(param_str)

            output += CommandHelper.format_list(param_usages, initial_message=f"&d[Usage] &e/{cmd.ACTIVATORS[0]} ", seperator=" ", line_start="&d ->")

            # Append list of aliases (if they exist)
            if len(cmd.ACTIVATORS) > 1:
                output += CommandHelper.format_list(cmd.ACTIVATORS[1:], initial_message="&d[Aliases] &e", seperator=", ", line_start="&e", prefix="/")

            # If command is operator only, add a warning
            if cmd.OP:
                output.append("&4[NOTICE] &fThis Command Is For Operators and Admins Only!")

            # If command is disabled only, add a warning
            if cmd.NAME in ctx.server.config.disabledCommands:
                output.append("&4[NOTICE] &fThis Command Is DISABLED!")

            output.append(CommandHelper.center_message(f"&ePlugin: {cmd.MODULE.NAME} v. {cmd.MODULE.VERSION}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "PluginsList",
        description="Lists all plugins/modules installed",
        version="v1.0.0"
    )
    class PulginsCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["plugins", "modules"])

        async def execute(self, ctx: Player, page: int = 1):
            # Get information on the number of modules, pages, and modules per page
            num_modules = len(ModuleManager._module_dict)  # This should never be zero as it should always count itself!
            modules_per_page = 8
            num_pages = math.ceil(num_modules / modules_per_page)
            current_page = page - 1

            # Check if user input was valid
            if page > num_pages or page <= 0:
                raise CommandError(f"&cThere are only {num_pages} pages of modules!&f")

            # Get a list of modules registed
            modules = tuple(ModuleManager._module_dict.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.center_message(f"&eHelp Page {page}/{num_pages}", colour="&2"))

            # Add command information
            for module_name, module in modules[current_page * modules_per_page:current_page * modules_per_page + modules_per_page]:
                output.append(f"&e{module_name}: &f{module.DESCRIPTION}")

            # Add Footer
            output.append(CommandHelper.center_message(f"&eTotal Modules: {num_modules}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "PluginInfo",
        description="Detailed help message for a specific plugin",
        version="v1.0.0"
    )
    class PluginInfoCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["plugin", "module", "plugininfo", "moduleinfo"])

        async def execute(self, ctx: Player, module_name: str):
            # Generate plugin output
            output = []

            # Get the plugin in question
            if module_name in ModuleManager._module_dict:
                plugin = ModuleManager._module_dict[module_name]
            else:
                # Plugin doesnt exist!
                raise CommandError(f"&cPlugin {module_name} not found!&f")

            # Add Header
            output.append(CommandHelper.center_message(f"&ePlugin Information: {plugin.NAME}", colour="&2"))

            # Add Plugin Description
            if plugin.DESCRIPTION:
                output.append(f"&d[Description]&f {plugin.DESCRIPTION}")

            # Add Plugin Author
            if plugin.AUTHOR:
                output.append(f"&d[Author]&f {plugin.AUTHOR}")

            # Add Plugin Version
            if plugin.VERSION:
                output.append(f"&d[Version]&f {plugin.VERSION}")

            # If Plugin has a Documentation String, Add it on!
            if plugin.__doc__:
                output.append("&d[Documentation]")
                output += [line.strip() for line in plugin.__doc__.strip().splitlines()]

            # If the plugin has dependencies, Add it on!
            if len(plugin.DEPENDENCIES):
                output.append("&d[Dependencies]")
                output += CommandHelper.format_list(
                    plugin.DEPENDENCIES,
                    process_input=lambda d: f"&b[{d.NAME} &7| v.{d.VERSION}&b]" if d.VERSION else f"&b[{d.NAME} &7| Any&b]",
                    seperator=", ",
                    line_start="")

            # Add # of Submodules
            output.append(f"&d[Submodules] &f{len(plugin.SUBMODULES)}")

            output.append(CommandHelper.center_message(f"&ePlugins Installed: {len(ModuleManager._module_dict)}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListPlayers",
        description="Lists all players in specific world",
        version="v1.0.0"
    )
    class ListPlayersCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["list", "players", "listplayers"])

        async def execute(self, ctx: Player, world: Optional[str] = None):
            if ctx.worldPlayerManager is None:
                raise CommandError("&cYou are not in a world!&f")

            # Get what the user wants
            if world is None:
                manager = ctx.worldPlayerManager
            else:
                try:
                    manager = ctx.server.worldManager.getWorld(world).playerManager
                except NameError:
                    raise CommandError(f"World {world} not found!")

            # Get a list of players
            players_list = manager.getPlayers()

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.center_message(f"&ePlayers Online: {len(players_list)}/{manager.world.maxPlayers}", colour="&2"))

            # Generate Player List Output
            output += CommandHelper.format_list(players_list, process_input=lambda p: str(p.name), initial_message="&e", seperator=", ")

            # Add Footer
            output.append("&7To see players in all worlds, use /listall")
            output.append(CommandHelper.center_message(f"&eWorld Name: {manager.world.name}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListAllPlayers",
        description="Lists all players in all worlds",
        version="v1.0.0"
    )
    class ListAllPlayersCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["listall", "allplayers", "online"])

        async def execute(self, ctx: Player):
            # Generate command output
            output = []

            # Add Header (Different depending on if server max size is set)
            if ctx.server.playerManager.maxSize is not None:
                output.append(CommandHelper.center_message(f"&ePlayers Online: {len(ctx.server.playerManager.players)}/{ctx.server.playerManager.maxSize} | Worlds: {len(ctx.server.worldManager.worlds)}", colour="&2"))
            else:
                output.append(CommandHelper.center_message(f"&ePlayers Online: {len(ctx.server.playerManager.players)} | Worlds: {len(ctx.server.worldManager.worlds)}", colour="&2"))

            # Keep track of the number of worlds that were hidden
            num_hidden = 0

            # Loop through all worlds and print their players
            for world in ctx.server.worldManager.worlds.values():
                # Get the worlds player list
                players_list = world.playerManager.getPlayers()

                # If there are no players, hide this server from the list
                if len(players_list) == 0:
                    num_hidden += 1
                    continue

                # Generate Player List Output

                output += CommandHelper.format_list(players_list, process_input=lambda p: str(p.name), initial_message=f"&d[{world.name}] &e", seperator=", ")

            # If any words were hidden, print notice
            if num_hidden > 0:
                output.append(f"&7{num_hidden} worlds were hidden due to having no players online.")
                output.append("&7Use /worlds to see all worlds.")

            # Add Footer
            output.append(CommandHelper.center_message(f"&eServer Name: {ctx.server.name}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListStaff",
        description="Lists all online staff/operators",
        version="v1.0.0"
    )
    class ListStaffCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["liststaff", "staff", "listallstaff", "allstaff"])

        async def execute(self, ctx: Player, world: Optional[str] = None):
            staff_list = list(ctx.server.playerManager.players.values())

            # Generate command output
            output = []

            # Filter List to Staff Only
            players_list = [player for player in staff_list if player.opStatus]

            # Add Header
            output.append(CommandHelper.center_message(f"&eStaff Online: {len(players_list)}", colour="&2"))

            # Generate Player List Output
            output += CommandHelper.format_list(players_list, process_input=lambda p: str(p.name), initial_message="&4", seperator=", ")

            # Add Footer
            output.append(CommandHelper.center_message(f"&eServer Name: {ctx.server.name}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "JoinWorld",
        description="Joins another world",
        version="v1.0.0"
    )
    class JoinWorldCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["join", "joinworld", "jw"])

        async def execute(self, ctx: Player, world: str):
            # Get World To Join
            try:
                join_world = ctx.server.worldManager.getWorld(world)
            except NameError:
                raise CommandError(f"World {world} not found!")

            await ctx.changeWorld(join_world)

    @Command(
        "ListWorlds",
        description="Lists All Loaded Worlds",
        version="v1.0.0"
    )
    class ListWorldsCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["listworlds", "worlds", "lw"])

        async def execute(self, ctx: Player):
            # Get list of worlds
            world_list = list(ctx.server.worldManager.worlds.values())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.center_message(f"&eWorlds Loaded: {len(world_list)}", colour="&2"))

            # Generate Player List Output
            output += CommandHelper.format_list(world_list, process_input=lambda p: str(p.name), initial_message="&e", seperator=", ")

            # Add Footer
            output.append(CommandHelper.center_message(f"&eServer Name: {ctx.server.name}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "MOTD",
        description="Prints Message of the Day",
        version="v1.0.0"
    )
    class MOTDCommand(AbstractCommand["CoreModule"]):
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
    class OPCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["op", "operator"], OP=True)

        async def execute(self, ctx: Player, name: str):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if user is already operator
            serverConfig = ctx.playerManager.server.config
            if username in serverConfig.operatorsList:
                raise CommandError(f"Player {username} is already an operator!")

            # Add Player To Operators List
            serverConfig.operatorsList.append(username)
            serverConfig.save()

            # Update User On Its OP Status
            if(player := ctx.playerManager.players.get(username, None)):
                await player.updateOperatorStatus()

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Added To Operators List")

    @Command(
        "DeOperator",
        description="Removes A Player As An Operator",
        version="v1.0.0"
    )
    class DEOPCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["deop", "deoperator"], OP=True)

        async def execute(self, ctx: Player, name: str):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if player is operator
            serverConfig = ctx.playerManager.server.config
            if username not in serverConfig.operatorsList:
                raise CommandError(f"Player {username} is not an operator!")

            # Remove Player From Operators List
            serverConfig.operatorsList.remove(username)
            serverConfig.save()

            # Update User On Its OP Status
            if(player := ctx.playerManager.players.get(username, None)):
                await player.updateOperatorStatus()

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Removed From Operators List")

    @Command(
        "ListOperators",
        description="List all operators",
        version="v1.0.0"
    )
    class ListOPCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["listop", "oplist"], OP=True)

        async def execute(self, ctx: Player):
            # Send formatted operators list
            await ctx.sendMessage(
                CommandHelper.format_list(
                    ctx.server.config.operatorsList,
                    initial_message="&4[Operators] &e",
                    line_start="&e", seperator=", "
                )
            )

    @Command(
        "Kick",
        description="Kicks a user by name",
        version="v1.0.0"
    )
    class KickCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["kick", "kickuser"], OP=True)

        async def execute(self, ctx: Player, name: str, reason: str = "You Have Been Kicked By An Operator"):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if user is in list of players
            if not ctx.playerManager.players.get(username, None):
                raise CommandError(f"Player {username} is not online!")

            # Kick Player
            await ctx.playerManager.kickPlayer(username, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Kicked!")

    @Command(
        "KickIp",
        description="Kicks a user by ip",
        version="v1.0.0"
    )
    class KickIpCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["kickip"], OP=True)

        async def execute(self, ctx: Player, ip: str, reason: str = "You Have Been Kicked By An Operator"):
            # Check if IP is valid
            try:
                ip = _formatIp(ip)
            except TypeError:
                raise CommandError(f"Ip {ip} is not a valid Ip!")

            # Check if user with ip is connected
            if not ctx.playerManager.getPlayersByIp(ip):
                raise CommandError(f"No Players With Ip {ip} is online!")

            # Kick Player
            await ctx.playerManager.kickPlayerByIp(ip, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aKick Players With {ip}!")

    @Command(
        "Ban",
        description="Bans a user by name",
        version="v1.0.0"
    )
    class BanCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["ban", "banuser"], OP=True)

        async def execute(self, ctx: Player, name: str, *, reason: str = "You Have Been Banned By An Operator"):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if user is already banned
            serverConfig = ctx.server.config
            if username in serverConfig.bannedPlayers:
                raise CommandError(f"Player {username} is already banned!")

            # Add Player To Banned Users List
            serverConfig.bannedPlayers.append(username)
            serverConfig.save()

            # If Player Is Connected, Kick Player
            if ctx.playerManager.players.get(username, None):
                await ctx.playerManager.kickPlayer(username, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Banned!")

    @Command(
        "Unban",
        description="Unbans a user by name",
        version="v1.0.0"
    )
    class UnbanCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["unban", "unbanuser"], OP=True)

        async def execute(self, ctx: Player, name: str):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if player is banned
            serverConfig = ctx.server.config
            if username not in serverConfig.bannedPlayers:
                raise CommandError(f"Player {username} is not banned!")

            # Remove Player From Banned List
            serverConfig.bannedPlayers.remove(username)
            serverConfig.save()

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Unbanned!")

    @Command(
        "IpBan",
        description="Bans a user by ip",
        version="v1.0.0"
    )
    class IpBanCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["ipban"], OP=True)

        async def execute(self, ctx: Player, name: str, *, reason: str = "You Have Been Banned By An Operator"):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Get Player Object
            player = ctx.playerManager.players.get(username, None)

            # If Player is Not Found, Return Error
            if not player:
                raise CommandError(f"Player {username} is not online!")

            # Check if player ip is already banned.
            serverConfig = ctx.server.config
            ip = player.networkHandler.ip
            if ip in serverConfig.bannedIps:
                await ctx.sendMessage(f"Player Ip {ip} is already banned! Kicking All Players With IP.")
            else:
                # Add Ip To Banned Ips List
                serverConfig.bannedIps.append(ip)
                serverConfig.save()

            # If Ip Is Connected, Kick Players With That Ip
            if ctx.playerManager.getPlayersByIp(ip):
                await ctx.playerManager.kickPlayerByIp(ip, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Banned By Ip {ip}!")

    @Command(
        "BanIp",
        description="Bans an ip",
        version="v1.0.0"
    )
    class BanIpCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["banip"], OP=True)

        async def execute(self, ctx: Player, ip: str, *, reason: str = "You Have Been Banned By An Operator"):
            # Check if IP is valid
            try:
                ip = _formatIp(ip)
            except TypeError:
                raise CommandError(f"Ip {ip} is not a valid Ip!")

            # Check if Ip is already banned
            serverConfig = ctx.server.config
            if ip in serverConfig.bannedIps:
                raise CommandError(f"Ip {ip} is already banned!")

            # Add Ip To Banned Ips List
            serverConfig.bannedIps.append(ip)
            serverConfig.save()

            # If Ip Is Connected, Kick Players With That Ip
            if ctx.playerManager.getPlayersByIp(ip):
                await ctx.playerManager.kickPlayerByIp(ip, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aIp {ip} Banned!")

    @Command(
        "UnbanIp",
        description="Unbans an Ip",
        version="v1.0.0"
    )
    class UnbanIpCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["unbanip"], OP=True)

        async def execute(self, ctx: Player, ip: str):
            # Check if IP is valid
            try:
                ip = _formatIp(ip)
            except TypeError:
                raise CommandError(f"Ip {ip} is not a valid Ip!")

            # Check if Ip is Banned
            serverConfig = ctx.server.config
            if ip not in serverConfig.bannedIps:
                raise CommandError(f"Ip {ip} is not banned!")

            # Remove Ip From Banned Ips List
            serverConfig.bannedIps.remove(ip)
            serverConfig.save()

            # Send Response Back
            await ctx.sendMessage(f"&aIp {ip} Unbanned!")

    @Command(
        "BanList",
        description="List all banned players",
        version="v1.0.0"
    )
    class BanListCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["banlist", "listbans"], OP=True)

        async def execute(self, ctx: Player):
            # Send formatted banned list
            await ctx.sendMessage(
                CommandHelper.format_list(
                    ctx.server.config.bannedPlayers,
                    initial_message="&4[Banned Players] &e",
                    line_start="&e", seperator=", "
                )
            )
            await ctx.sendMessage(
                CommandHelper.format_list(
                    ctx.server.config.bannedIps,
                    initial_message="&4[Banned Ips] &e",
                    line_start="&e", seperator=", "
                )
            )

    @Command(
        "DisableCommand",
        description="Disables a command",
        version="v1.0.0"
    )
    class DisableCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["disable", "disablecommand", "disablecmd"], OP=True)

        async def execute(self, ctx: Player, cmd_name: str):
            # Get the command in question
            if cmd_name in CommandManager._command_dict:
                # User is passing by command name
                cmd = CommandManager._command_dict[cmd_name]
            elif cmd_name in CommandManager._activators:
                # User is passing by activator
                cmd = CommandManager._activators[cmd_name.lower()]
            else:
                # Command doesnt exist!
                raise CommandError(f"&cCommand {cmd_name} not found!&f")

            # Check if Command is already banned
            serverConfig = ctx.server.config
            if cmd.NAME in serverConfig.disabledCommands:
                raise CommandError(f"Command {cmd.NAME} is already disabled!")

            # Add Ip To Banned Ips List
            serverConfig.disabledCommands.append(cmd.NAME)
            serverConfig.save()

            # Send Response Back
            await ctx.sendMessage(f"&aCommand {cmd.NAME} Disabled!")

    @Command(
        "EnableCommand",
        description="Enables a command",
        version="v1.0.0"
    )
    class EnableCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["enable", "enablecommand", "enablecmd"], OP=True)

        async def execute(self, ctx: Player, cmd_name: str):
            # Get the command in question
            if cmd_name in CommandManager._command_dict:
                # User is passing by command name
                cmd = CommandManager._command_dict[cmd_name]
            elif cmd_name in CommandManager._activators:
                # User is passing by activator
                cmd = CommandManager._activators[cmd_name.lower()]
            else:
                # Command doesnt exist!
                raise CommandError(f"&cCommand {cmd_name} not found!&f")

            # Check if command is disabled
            serverConfig = ctx.server.config
            if cmd.NAME not in serverConfig.disabledCommands:
                raise CommandError(f"Command {cmd.NAME} is already enabled!")

            # Remove Command from Disabled Commands List
            serverConfig.disabledCommands.remove(cmd.NAME)
            serverConfig.save()

            # Send Response Back
            await ctx.sendMessage(f"&aCommand {cmd.NAME} Enabled!")

    @Command(
        "DisabledCommandsList",
        description="List all disabled commands",
        version="v1.0.0"
    )
    class DisabledCommandsListCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["disabled", "disabledcommands", "listdisabled"], OP=True)

        async def execute(self, ctx: Player):
            # Send formatted disabled list
            await ctx.sendMessage(
                CommandHelper.format_list(
                    ctx.server.config.disabledCommands,
                    initial_message="&4[Disabled Commands] &e",
                    line_start="&e", seperator=", "
                )
            )

    @Command(
        "ReloadConfig",
        description="Forces a reload of the config",
        version="v1.0.0"
    )
    class ReloadConfigCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reloadconfig"], OP=True)

        async def execute(self, ctx: Player):
            # Reload Config
            serverConfig = ctx.server.config
            serverConfig.reload()

            # Send Response Back
            await ctx.sendMessage("&aConfig Reloaded!")

    @Command(
        "StopServer",
        description="Stops the server",
        version="v1.0.0"
    )
    class StopCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["stop"], OP=True)

        async def execute(self, ctx: Player):
            await ctx.sendMessage("&4Stopping Server")
            # await ctx.playerManager.server.stop()

            # Server doesnt like it when it sys.exit()s mid await
            # So as a workaround, we disconnect the calling user first then stop the server using asyncstop
            # Which should launch the stop script on another event loop.
            # TODO: This works fine for now, but might cause issues later...
            await ctx.networkHandler.closeConnection("Server Shutting Down", notifyPlayer=True)

            # Server doesnt like it if
            ctx.server.asyncstop()


# Helper functions for the command generation
class CommandHelper():
    @staticmethod
    def center_message(message: str, colour: str = "", padCharacter: str = "=") -> str:
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

    @staticmethod
    def format_list(
        values: Iterable[Any],
        process_input: Callable[[Any], str] = lambda s: str(s),
        initial_message: str = "",
        seperator: str = "",
        line_start: str = "",
        line_end: str = "",
        prefix: str = "",
        postfix: str = ""
    ) -> list[str]:
        output = []
        output.append(initial_message)
        isEmpty = True

        i = iter(values)  # Use an iterable to loop through values
        while (val := next(i, None)):
            isEmpty = False
            # Format Val
            val = prefix + process_input(val) + postfix + seperator

            # Check if adding the player name will overflow the max message length
            if len(output[-1]) + len(line_end) + len(val) > MAX_MESSAGE_LENGTH:
                output[-1] += line_end  # Add whatever postfix is needed
                output.append(line_start)  # Add a new line for output (prefix)

            # Add Player Name
            output[-1] += val

        # Remove final seperator from the last line
        if len(seperator) and not isEmpty:
            output[-1] = output[-1][:-len(seperator)]

        return output
