from obsidian.module import Module, AbstractModule, ModuleManager
from obsidian.constants import MAX_MESSAGE_LENGTH, SERVERPATH, __version__
from obsidian.errors import ClientError, ServerError, WorldFormatError, CommandError, ConverterError
from obsidian.types import _formatUsername, _formatIp
from obsidian.log import Logger
from obsidian.player import Player
from obsidian.worldformat import AbstractWorldFormat, WorldFormat, WorldFormats
from obsidian.world import World, WorldManager
from obsidian.mapgen import AbstractMapGenerator, MapGenerator, MapGenerators
from obsidian.commands import AbstractCommand, Command, Commands, CommandManager, _typeToString
from obsidian.blocks import AbstractBlock, BlockManager, Block, Blocks
from obsidian.packet import (
    RequestPacket,
    ResponsePacket,
    AbstractRequestPacket,
    AbstractResponsePacket,
    unpackString,
    packageString
)

from typing import Optional, Iterable, Callable, Any
from pathlib import Path
import datetime
import inspect
import zipfile
import struct
import random
import json
import gzip
import math
import time
import uuid
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

            # Unpack String
            # Username
            username = unpackString(username)
            if not username.isalnum():
                raise ClientError("Invalid Character In Username")
            # Verification String
            verificationKey = unpackString(verificationKey)
            if not username.isprintable():
                raise ClientError("Invalid Character In Verification Key")

            # Check Username Length (Hard Capped At 16 To Prevent Length Bugs)
            if(len(username) > 16):
                raise ClientError("Your Username Is Too Long (Max 16 Chars)")

            # Return User Identification
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

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray, handleUpdate: bool = True):
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
            if handleUpdate:
                await ctx.handleBlockUpdate(blockX, blockY, blockZ, blockType)

            # Return block placement information
            return blockX, blockY, blockZ, blockId

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @RequestPacket(
        "MovementUpdate",
        description="Received When Player Position And Orientation Is Sent"
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

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray, handleUpdate: bool = True):
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
            if handleUpdate:
                await ctx.handlePlayerMovement(posX, posY, posZ, posYaw, posPitch)

            # Return new positions
            return posX, posY, posZ, posYaw, posPitch

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

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray, handleUpdate: bool = True):
            # <Player Message Packet>
            # (Byte) Packet ID
            # (Byte) Unused (Should Always Be 0xFF)
            # (64String) Message
            _, _, message = struct.unpack(self.FORMAT, bytearray(rawData))

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

            # Unpack String
            # Message
            message = unpackString(message)
            if not message.isprintable():
                await ctx.sendMessage("&4ERROR: Message Failed To Send - Invalid Character In Message&f")
                return None  # Don't Complete Message Sending

            # Handle Player Message
            if handleUpdate:
                await ctx.handlePlayerMessage(message)

            # Return Parsed Message
            return message

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
                EXTENSIONS=["gz"]
            )

            Logger.warn("The 'Raw Map' save file format is meant as a placeholder and is not meant to be used in production.", module="raw-map")
            Logger.warn("Although it will probably work, please install a more robust save format.", module="raw-map")

        def loadWorld(
            self,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager,
            persistent: bool = True
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
                0,  # World Seed (but ofc it doesn't exist)
                bytearray(rawData),  # Generating Map Data
                persistent=persistent,  # Pass In Persistent Flag
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
        "Obsidian",
        description="Obsidian Map Data File",
        version="v1.0.0"
    )
    class ObsidianWorldFormat(AbstractWorldFormat["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                KEYS=["obsidian"],
                EXTENSIONS=["obw", "zip"]
            )

        criticalFields = {
            "version",
            "name",
            "X",
            "Y",
            "Z"}

        def loadWorld(
            self,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager,
            persistent: bool = True
        ):
            # Open Zip File
            Logger.debug("Loading Zip File", module="obsidian-map")
            zipFile = zipfile.ZipFile(fileIO)

            # Check validity of zip file
            if "metadata" not in zipFile.namelist() or "map" not in zipFile.namelist():
                raise WorldFormatError("ObsidianWorldFormat - Invalid Zip File! Missing Critical Data!")

            # Load Metadata
            Logger.debug("Loading Metadata", module="obsidian-map")
            worldMetadata = json.loads(zipFile.read("metadata").decode("utf-8"))
            Logger.debug(f"Loaded Metadata: {worldMetadata}", module="obsidian-map")

            # Check if metadata is valid
            if self.criticalFields.intersection(set(worldMetadata.keys())) != self.criticalFields:
                raise WorldFormatError("ObsidianWorldFormat - Invalid Metadata! Missing Critical Data!")

            # Get information out of world metadata
            # Critical Values
            version = worldMetadata.get("version")
            name = worldMetadata.get("name")
            sizeX = worldMetadata.get("X")
            sizeY = worldMetadata.get("Y")
            sizeZ = worldMetadata.get("Z")
            # Optional Values
            spawnX = worldMetadata.get("spawnX", 0)
            spawnY = worldMetadata.get("spawnY", 0)
            spawnZ = worldMetadata.get("spawnZ", 0)
            spawnYaw = worldMetadata.get("spawnYaw", 0)
            spawnPitch = worldMetadata.get("spawnPitch", 0)
            # Misc Values
            seed = worldMetadata.get("seed", random.randint(0, 2**64))
            worldUUID = uuid.UUID(worldMetadata.get("worldUUID", str(uuid.uuid4())))
            worldCreationService = worldMetadata.get("worldCreationService", "Obsidian")
            worldCreationPlayer = worldMetadata.get("worldCreationPlayer", "ObsidianPlayer")
            timeCreated = datetime.datetime.fromtimestamp(worldMetadata.get("timeCreated", int(time.time())))
            lastModified = datetime.datetime.fromtimestamp(worldMetadata.get("lastModified", int(time.time())))
            lastAccessed = datetime.datetime.fromtimestamp(worldMetadata.get("lastAccessed", int(time.time())))

            # Try parsing world generator
            try:
                generator = MapGenerators[worldMetadata.get("generator", None)]
            except KeyError:
                Logger.warn("ObsidianWorldFormat - Unknown World Generator.")
                generator = None  # Continue with no generator

            # Check if world spawn need to be regenerated
            if (True and "spawnX" not in worldMetadata or
                         "spawnY" not in worldMetadata or
                         "spawnZ" not in worldMetadata or
                         "spawnYaw" not in worldMetadata or
                         "spawnPitch" not in worldMetadata):
                Logger.warn("ObsidianWorldFormat - World Spawn Data Missing! Generating New World Spawn Location...")
                resetWorldSpawn = True
            else:
                resetWorldSpawn = False

            # Check if version is valid
            if version != self.VERSION:
                Logger.warn(f"ObsidianWorldFormat - World Version Mismatch! Expected: {self.VERSION} Got: {version}", module="obsidian-map")

            # Check if world names are the same
            if name != Path(fileIO.name).stem:
                Logger.warn(f"ObsidianWorldFormat - World Name Mismatch! Expected: {Path(fileIO.name).stem} Got: {name}", module="obsidian-map")

            # Load Logout Locations
            Logger.debug("Loading Logout Locations", module="obsidian-map")
            if "logouts" in zipFile.namelist():
                logoutLocations = {}
                for player, coords in json.loads(zipFile.read("logouts").decode("utf-8")).items():
                    logX = coords["X"]
                    logY = coords["Y"]
                    logZ = coords["Z"]
                    logYaw = coords["Yaw"]
                    logPitch = coords["Pitch"]
                    logoutLocations[player] = (logX, logY, logZ, logYaw, logPitch)
                    Logger.debug(f"Loaded Logout Location x:{logX}, y:{logY}, z:{logZ}, yaw:{logYaw}, pitch:{logPitch} for player {player}", module="obsidian-map")
            else:
                logoutLocations = {}
                Logger.warn("ObsidianWorldFormat - Missing Logout Info.", module="obsidian-map")

            # Load Map Data
            Logger.debug("Loading Map Data", module="obsidian-map")
            raw_data = bytearray(gzip.GzipFile(fileobj=io.BytesIO(zipFile.read("map"))).read())

            # Sanity Check File Size
            if (sizeX * sizeY * sizeZ) != len(raw_data):
                raise WorldFormatError(f"ObsidianWorldFormat - Invalid Map Data! Expected: {sizeX * sizeY * sizeZ} Got: {len(raw_data)}")

            # Close Zip File
            zipFile.close()

            # Create World Data
            return World(
                worldManager,  # Pass In World Manager
                name,
                sizeX, sizeY, sizeZ,
                seed,
                raw_data,
                spawnX=spawnX,
                spawnY=spawnY,
                spawnZ=spawnZ,
                spawnYaw=spawnYaw,
                spawnPitch=spawnPitch,
                resetWorldSpawn=resetWorldSpawn,
                generator=generator,
                persistent=persistent,  # Pass In Persistent Flag
                fileIO=fileIO,  # Pass In File Reader/Writer
                logoutLocations=logoutLocations,
                worldUUID=worldUUID,
                worldCreationService=worldCreationService,
                worldCreationPlayer=worldCreationPlayer,
                timeCreated=timeCreated,
                lastModified=lastModified,
                lastAccessed=lastAccessed
            )

        def saveWorld(
            self,
            world: World,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager
        ):
            # Set up the metadata about the world
            worldMetadata = {}

            # This world format closely follows that of
            # https://wiki.vg/ClassicWorld_file_format

            # World Format Info
            worldMetadata["version"] = self.VERSION

            # Set Basic Info
            worldMetadata["name"] = world.name
            worldMetadata["X"] = world.sizeX
            worldMetadata["Y"] = world.sizeY
            worldMetadata["Z"] = world.sizeZ

            # Set Spawn Info
            worldMetadata["spawnX"] = world.spawnX
            worldMetadata["spawnY"] = world.spawnY
            worldMetadata["spawnZ"] = world.spawnZ
            worldMetadata["spawnYaw"] = world.spawnYaw
            worldMetadata["spawnPitch"] = world.spawnPitch

            # Add Misc Data
            worldMetadata["seed"] = world.seed
            worldMetadata["worldUUID"] = str(world.worldUUID)
            worldMetadata["worldCreationService"] = world.worldCreationService
            worldMetadata["worldCreationPlayer"] = world.worldCreationPlayer
            worldMetadata["timeCreated"] = int(time.mktime(world.timeCreated.timetuple()))
            worldMetadata["lastModified"] = int(time.mktime(world.lastModified.timetuple()))
            worldMetadata["lastAccessed"] = int(time.mktime(world.lastAccessed.timetuple()))

            # Set up logout location  metadata
            if world.logoutLocations is not None:
                logoutLocations = {}
                for player, coord in world.logoutLocations.items():
                    logX, logY, logZ, logYaw, logPitch = coord
                    logoutLocations[player] = {}
                    logoutLocations[player]["X"] = logX
                    logoutLocations[player]["Y"] = logY
                    logoutLocations[player]["Z"] = logZ
                    logoutLocations[player]["Yaw"] = logYaw
                    logoutLocations[player]["Pitch"] = logPitch
            else:
                logoutLocations = {}
                Logger.error("Logout locations is None! This should not happen, but continuing anyway...", module="obsidian-map", printTb=False)

            # Set Generator Info
            if world.generator:
                worldMetadata["generator"] = world.generator.NAME
            else:
                worldMetadata["generator"] = None
            worldMetadata["seed"] = world.seed

            # Clearing Current Save File
            fileIO.truncate(0)
            fileIO.seek(0)

            # Create zip file
            with zipfile.ZipFile(fileIO, "w") as zip_file:
                # Write the metadata file
                Logger.debug("Writing metadata file", module="obsidian-map")
                zip_file.writestr("metadata", json.dumps(worldMetadata, indent=4))
                # Write the logout location file
                Logger.debug("Writing logout locations file", module="obsidian-map")
                zip_file.writestr("logouts", json.dumps(logoutLocations, indent=4))
                # Write the map file
                Logger.debug("Writing map file", module="obsidian-map")
                zip_file.writestr("map", world.gzipMap())

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
        def generateMap(self, sizeX: int, sizeY: int, sizeZ: int, seed: int):
            grassHeight = sizeY // 2
            # Generate Map
            mapData = bytearray(0)
            # Pre-generate air, dirt, and grass layers
            slice_air = bytearray([Blocks.Air.ID]) * (sizeX * sizeZ)
            slice_dirt = bytearray([Blocks.Dirt.ID]) * (sizeX * sizeZ)
            slice_grass = bytearray([Blocks.Grass.ID]) * (sizeX * sizeZ)
            # Create World
            for y in range(sizeY):
                if y > grassHeight:
                    mapData.extend(slice_air)
                elif y == grassHeight:
                    mapData.extend(slice_grass)
                else:
                    mapData.extend(slice_dirt)
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

        async def execute(self, ctx: Player, *, page_num_or_query: int | str = 1):
            # If command is not an int, assume its a command name and print help for that
            if isinstance(page_num_or_query, str):
                # Check if rightmost value is part of the module/command name or a page number
                # This will cause some edge cases where it will fail, but its better than nothing
                if page_num_or_query.rsplit(" ", 1)[-1].isnumeric():
                    query = page_num_or_query.rsplit(" ", 1)[0]
                    page_num = int(page_num_or_query.rsplit(" ", 1)[1])
                else:
                    query = page_num_or_query
                    page_num = 1
                # Try to get query as a module
                try:
                    module = ModuleManager.SUBMODULE._convert_arg(ctx.server, query)
                except ConverterError:
                    module = None
                # Try to get query as a command
                try:
                    command = CommandManager.SUBMODULE._convert_arg(ctx.server, query)
                except ConverterError:
                    command = None
                # If both conditions match, raise a warning
                if module and command:
                    await ctx.sendMessage(f"&9[NOTICE] &f{query} is both a plugin name and a module name.")
                    await ctx.sendMessage("&9[NOTICE] &fTo get help as a command, please use &e/helpcmd")
                # Process First as a plugin
                if module:
                    return await Commands.HelpPlugin.execute(ctx, module=module, page=page_num)
                elif command:
                    return await Commands.HelpCmd.execute(ctx, cmd=command)
                else:
                    raise CommandError(f"{query} is not a plugin or a command.")

            # Generate and Parse list of commands
            cmd_list = CommandManager._command_dict
            # If user is not OP, filter out OP and Disabled commands
            if not ctx.opStatus:
                cmd_list = {k: v for k, v in cmd_list.items() if (not v.OP) and (v.NAME not in ctx.playerManager.server.config.disabledCommands)}

            # Alias page_or_query to just page
            page = page_num_or_query

            # Get information on the number of commands, pages, and commands per page
            num_commands = len(cmd_list)  # This should never be zero as it should always count itself!
            commands_per_page = 4
            num_pages = math.ceil(num_commands / commands_per_page)
            current_page = page - 1

            # Check if user input was valid
            if page > num_pages or page <= 0:
                raise CommandError(f"There are only {num_pages} pages of commands!")

            # Get a list of commands registered
            commands = tuple(cmd_list.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.center_message(f"&eHelp Page {page}/{num_pages}", colour="&2"))

            # Add some additional tips to help command (Only if first page)
            if current_page == 0:
                output.append("&7Use /help [n] to get the nth page of help.&f")
                output.append("&7Use /help [query] for help on a plugin or command.&f")

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
        "HelpPlugin",
        description="Gets help for commands from plugin",
        version="v1.0.0"
    )
    class HelpPluginCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["helpplugin", "pluginhelp"])

        async def execute(self, ctx: Player, module: AbstractModule, page: int = 1):
            # Generate and Parse list of commands
            cmd_list = CommandManager._command_dict
            # Filter to commands from only one plugin
            cmd_list = {k: v for k, v in cmd_list.items() if v.MODULE == module}
            # If user is not OP, filter out OP and Disabled commands
            if not ctx.opStatus:
                cmd_list = {k: v for k, v in cmd_list.items() if (not v.OP) and (v.NAME not in ctx.playerManager.server.config.disabledCommands)}

            # Get information on the number of commands, pages, and commands per page
            num_commands = len(cmd_list)
            commands_per_page = 4
            num_pages = math.ceil(num_commands / commands_per_page)
            current_page = page - 1

            # If there are no commands, return error
            if num_commands == 0:
                raise CommandError(f"Plugin {module.NAME} has no commands!")

            # Check if user input was valid
            if page > num_pages or page <= 0:
                raise CommandError(f"There are only {num_pages} pages of commands!")

            # Get a list of commands registered
            commands = tuple(cmd_list.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.center_message(f"&eHelp Page {page}/{num_pages}", colour="&2"))
            output.append(f"&d > Commands From {module.NAME}")

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
            output.append(CommandHelper.center_message(f"&e{module.NAME} Commands: {num_commands}", colour="&2"))

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

        async def execute(self, ctx: Player, cmd: AbstractCommand):
            # Generate command output
            output = []

            # If command is an operator-only command and if user is not operator, return error
            if cmd.OP and not ctx.opStatus:
                raise CommandError("You do not have permission to view this command!")

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
                param_str = ""
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

            output += CommandHelper.format_list(param_usages, initial_message=f"&d[Usage] &e/{cmd.ACTIVATORS[0]} ", separator=" ", line_start="&d ->")

            # Append list of aliases (if they exist)
            if len(cmd.ACTIVATORS) > 1:
                output += CommandHelper.format_list(cmd.ACTIVATORS[1:], initial_message="&d[Aliases] &e", separator=", ", line_start="&e", prefix="/")

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
    class PluginsCommand(AbstractCommand["CoreModule"]):
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
                raise CommandError(f"There are only {num_pages} pages of modules!")

            # Get a list of modules registered
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

        async def execute(self, ctx: Player, plugin: AbstractModule):
            # Generate plugin output
            output = []

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
                    separator=", ",
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

        async def execute(self, ctx: Player, world: Optional[World | Player] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    manager = ctx.worldPlayerManager
                else:
                    raise CommandError("You are not in a world!")
            elif isinstance(world, Player):
                if world.worldPlayerManager is not None:
                    manager = world.worldPlayerManager
                else:
                    raise CommandError("You are not in a world!")
            elif isinstance(world, World):
                manager = world.playerManager
            else:
                raise ServerError("bruh")

            # Get a list of players
            players_list = manager.getPlayers()

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.center_message(f"&ePlayers Online: {len(players_list)}/{manager.world.maxPlayers}", colour="&2"))

            # Generate Player List Output
            output += CommandHelper.format_list(players_list, process_input=lambda p: str(p.name), initial_message="&e", separator=", ")

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

                output += CommandHelper.format_list(players_list, process_input=lambda p: str(p.name), initial_message=f"&d[{world.name}] &e", separator=", ")

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

        async def execute(self, ctx: Player):
            staff_list = list(ctx.server.playerManager.players.values())

            # Generate command output
            output = []

            # Filter List to Staff Only
            players_list = [player for player in staff_list if player.opStatus]

            # Add Header
            output.append(CommandHelper.center_message(f"&eStaff Online: {len(players_list)}", colour="&2"))

            # Generate Player List Output
            output += CommandHelper.format_list(players_list, process_input=lambda p: str(p.name), initial_message="&4", separator=", ")

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

        async def execute(self, ctx: Player, world: World):
            await ctx.changeWorld(world)

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
            output += CommandHelper.format_list(world_list, process_input=lambda p: str(p.name), initial_message="&e", separator=", ")

            # Add Footer
            output.append(CommandHelper.center_message(f"&eServer Name: {ctx.server.name}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "WorldInfo",
        description="Detailed information for a specific world",
        version="v1.0.0"
    )
    class WorldInfoCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["world", "worldinfo"])

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Generate plugin output
            output = []

            # Add Header
            output.append(CommandHelper.center_message(f"&eWorld Information: {world.name}", colour="&2"))

            # Add World Information
            output.append(f"&d[Seed]&f {world.seed}")
            output.append(f"&d[World Size]&f &7x:&f{world.sizeX} &7y:&f{world.sizeY} &7z:&f{world.sizeZ}")
            output.append(f"&d[World Spawn]&f &7x:&f{world.spawnX//32} &7y:&f{world.spawnY//32} &7z:&f{world.spawnZ//32}")
            if world.generator:
                output.append(f"&d[World Generator]&f {world.generator.NAME}")
            output.append(f"&d[Persistent]&f {world.persistent}")
            output.append(f"&d[Max Players]&f {world.maxPlayers}")
            output.append(f"&d[UUID]&f {world.worldUUID}")
            output.append(f"&d[Created ]&f {world.worldCreationPlayer} using {world.worldCreationService}")
            output.append(f"&d[Time Created]&f {world.timeCreated}")

            # Add Footer
            output.append(CommandHelper.center_message(f"&eServer Name: {ctx.server.name}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "Seed",
        description="Get the world seed",
        version="v1.0.0"
    )
    class SeedCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["seed", "worldseed"])

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Send Formatted World Seed
            await ctx.sendMessage(f"Seed for &e{world.name}&f: [&a{world.seed}&f]")

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
                    line_start="&e", separator=", "
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
                    line_start="&e", separator=", "
                )
            )
            await ctx.sendMessage(
                CommandHelper.format_list(
                    ctx.server.config.bannedIps,
                    initial_message="&4[Banned Ips] &e",
                    line_start="&e", separator=", "
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

        async def execute(self, ctx: Player, cmd: AbstractCommand):
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

        async def execute(self, ctx: Player, cmd: AbstractCommand):
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
                    line_start="&e", separator=", "
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
        "SetWorldSpawn",
        description="Sets global default world spawn to current location.",
        version="v1.0.0"
    )
    class SetWorldSpawnCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["setspawn", "setworldspawn"], OP=True)

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Set the world spawn X, Y, Z, Yaw, and Pitch to current player
            world.spawnX = ctx.posX
            world.spawnY = ctx.posY
            world.spawnZ = ctx.posZ
            world.spawnYaw = ctx.posYaw
            world.spawnPitch = ctx.posPitch

            # Send Response Back
            await ctx.sendMessage("&aWorld Spawn Set To:")
            await ctx.sendMessage(f"&7x: &e{world.spawnX//32} &7y: &e{world.spawnY//32} &7z: &e{world.spawnZ//32} &7yaw: &e{world.spawnYaw} &7pitch: &e{world.spawnPitch}!")

    @Command(
        "ResetWorldSpawn",
        description="Sets global default world spawn to defaults.",
        version="v1.0.0"
    )
    class ResetWorldSpawnCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["resetspawn", "resetworldspawn"], OP=True)

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Set the world spawn X, Y, Z, Yaw, and Pitch to current player
            world.generateSpawnCoords(resetCoords=True)

            # Send Response Back
            await ctx.sendMessage("&aWorld Spawn Set To:")
            await ctx.sendMessage(f"&7x: &e{world.spawnX//32} &7y: &e{world.spawnY//32} &7z: &e{world.spawnZ//32} &7yaw: &e{world.spawnYaw} &7pitch: &e{world.spawnPitch}!")

    @Command(
        "ClearPlayerLogouts",
        description="Clears all last logout locations in world",
        version="v1.0.0"
    )
    class ClearPlayerLogoutsCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["clearplayerlogouts", "clearlastlogouts"], OP=True)

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Empty the dictionary for last login locations
            world.logoutLocations = {}

            # Send Response Back
            await ctx.sendMessage("&aLast Logins Cleared!")

    @Command(
        "ConvertWorld",
        description="Converts world from one format to another format.",
        version="v1.0.0"
    )
    class ConvertWorldCommand(AbstractCommand["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["convertworld"], OP=True)

        async def execute(self, ctx: Player, world_file: str, format_name: Optional[str] = None):
            # If no world format is passed, use current world format.
            # Else, get the requested world format.
            if format_name:
                try:
                    new_world_format = WorldFormats[format_name]
                except KeyError:
                    raise CommandError(f"&cWorld format '{format_name}' does not exist!")
            else:
                if ctx.worldPlayerManager is not None:
                    new_world_format = ctx.worldPlayerManager.world.worldManager.worldFormat
                else:
                    raise CommandError("&cYou are not in a world!")

            # Get world format extension
            new_format_ext = "." + new_world_format.EXTENSIONS[0]

            # Get the world to be converted
            if ctx.server.config.worldSaveLocation:
                old_world_path = Path(SERVERPATH, ctx.server.config.worldSaveLocation, world_file)
                new_world_path = Path(SERVERPATH, ctx.server.config.worldSaveLocation, Path(world_file).stem + new_format_ext)
            else:
                raise CommandError("&cworldSaveLocation in server configuration is not set!")

            # Check if world exists and if new world does not exist
            if not old_world_path.exists():
                raise CommandError(f"&cWorld '{old_world_path.name}' does not exist!")
            if new_world_path.exists():
                raise CommandError(f"&cWorld '{new_world_path.name}' already exists!")

            # Detect type of old world format
            old_world_format = WorldFormats.getWorldFormatFromExtension(old_world_path.suffix[1:])

            # Send user warning converting
            Logger.warn("User is about to convert world from one format to another!", module="format-convert")
            Logger.warn("This is a risky procedure! Use with caution!", module="format-convert")
            output = []

            # Add Header
            output.append(CommandHelper.center_message("&e[WARNING]", colour="&4"))

            # Add Warning
            output.append("&c[WARNING]&f You are about to perform a conversion")
            output.append("&c[WARNING]&f from one world format to another!")
            output.append("&c[WARNING]&f Formats may not be compatible with each other,")
            output.append("&c[WARNING]&f and &cDATA MAY BE LOST IN THE PROCESS&f!")
            output.append("&c[WARNING]&f Always make backups before continuing!")
            output.append("Type &aacknowledge &fto continue")

            # Add Footer
            output.append(CommandHelper.center_message("&e[WARNING]", colour="&4"))

            # Send warning message
            await ctx.sendMessage(output)

            # Get next user input
            resp = await ctx.getNextMessage()

            # Check if user acknowledged
            if resp != "acknowledge":
                raise CommandError("&cWorld conversion cancelled!")

            # Give information on world to be converted
            output = []

            # Add Header
            output.append(CommandHelper.center_message("&eWorld Format Conversion", colour="&2"))

            # Add World Information
            output.append(f"&3[Current World File]&f {old_world_path.name}")
            output.append(f"&3[Current World Format]&f {old_world_format.NAME}")
            output.append(f"&3[Current Format Adapter Version]&f {old_world_format.VERSION}")
            output.append(f"&b[New World File]&f {new_world_path.name}")
            output.append(f"&b[New World Format]&f {new_world_format.NAME}")
            output.append(f"&b[New Format Adapter Version]&f {new_world_format.VERSION}")
            output.append("&7World Path Location")
            output.append(str(old_world_path.parent))
            output.append("Type &aacknowledge &fto continue")

            # Add Footer
            output.append(CommandHelper.center_message(f"&eConverter Version: {self.VERSION}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

            # Get next user input
            resp = await ctx.getNextMessage()

            # Check if user acknowledged
            if resp != "acknowledge":
                raise CommandError("&cWorld conversion cancelled!")

            # Start Conversion Process
            await ctx.sendMessage("&aStarting World Conversion Process...")
            old_world_file = open(old_world_path, "rb+")
            new_world_file = open(new_world_path, "wb+")
            old_world_file.seek(0)
            new_world_file.seek(0)

            # Wrap in try except to catch errors
            try:
                # Create a temporary world manager
                await ctx.sendMessage("&aCreating Temporary World Manager...")
                temp_world_manager = WorldManager(ctx.server)

                # Load old world
                await ctx.sendMessage("&aLoading World from Old Format...")
                old_world = old_world_format.loadWorld(old_world_file, temp_world_manager)

                # Save to new world
                await ctx.sendMessage("&aSaving World to New Format...")
                new_world_format.saveWorld(old_world, new_world_file, temp_world_manager)
            except Exception as e:
                # Handle error by printing to chat and returning to user
                Logger.error(str(e), module="format-convert")
                await ctx.sendMessage("&cSomething went wrong while converting the world!")
                await ctx.sendMessage(f"&c{str(e)}")
                await ctx.sendMessage("&cPlease check the console for more information!")

            # Clean up open files
            await ctx.sendMessage("&aCleaning Up...")
            old_world_file.flush()
            old_world_file.close()
            new_world_file.flush()
            new_world_file.close()


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

            # Server doesn't like it when it sys.exit()s mid await
            # So as a workaround, we disconnect the calling user first then stop the server using asyncstop
            # Which should launch the stop script on another event loop.
            # TODO: This works fine for now, but might cause issues later...
            await ctx.networkHandler.closeConnection("Server Shutting Down", notifyPlayer=True)

            # Server doesn't like it if
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
        separator: str = "",
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
            val = prefix + process_input(val) + postfix + separator

            # Check if adding the player name will overflow the max message length
            if len(output[-1]) + len(line_end) + len(val) > MAX_MESSAGE_LENGTH:
                output[-1] += line_end  # Add whatever postfix is needed
                output.append(line_start)  # Add a new line for output (prefix)

            # Add Player Name
            output[-1] += val

        # Remove final separator from the last line
        if len(separator) and not isEmpty:
            output[-1] = output[-1][:-len(separator)]

        return output
