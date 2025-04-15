from typing import Optional, Iterable, Callable, Any
from pathlib import Path
import datetime
import zipfile
import struct
import json
import gzip
import time
import uuid
import io

from obsidian.module import Module, AbstractModule
from obsidian.constants import MAX_MESSAGE_LENGTH, __version__
from obsidian.log import Logger
from obsidian.player import Player
from obsidian.worldformat import AbstractWorldFormat, WorldFormat, WorldFormatManager
from obsidian.world import World, WorldManager, WorldMetadata
from obsidian.mapgen import AbstractMapGenerator, MapGeneratorStatus, MapGenerator, MapGenerators
from obsidian.blocks import AbstractBlock, BlockManager, Block, Blocks
from obsidian.errors import (
    ClientError,
    ServerError,
    WorldFormatError
)
from obsidian.packet import (
    RequestPacket,
    ResponsePacket,
    AbstractRequestPacket,
    AbstractResponsePacket,
    unpackString,
    packageString
)

@Module(
    "Core",
    description="Central Module For All Core Obsidian Features.",
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
                FORMAT="!BB64s64sB",
                CRITICAL=True,
                PLAYERLOOP=False
            )

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray):
            # <Player Identification Packet>
            # (Byte) Packet ID
            # (Byte) Protocol Version
            # (64String) Username
            # (64String) Verification Key
            # (Byte) Magic Byte (Used for CPE Negotiation. Could also be used to negotiate a 3rd party protocol)
            _, protocolVersion, username, verificationKey, magicByte = struct.unpack(self.FORMAT, bytearray(rawData))

            # Clean null terminators off strings
            # Some clients send null terminators, cough CrossCraft cough

            # Unpack String
            # Username
            username = unpackString(username)
            if not username.replace("_", "").isalnum():
                raise ClientError("Invalid Character In Username")
            # Verification String
            verificationKey = unpackString(verificationKey)
            if not verificationKey.isprintable():
                raise ClientError("Invalid Character In Verification Key")

            # Check Username Length (Hard Capped At 16 To Prevent Length Bugs)
            if len(username) > 16:
                raise ClientError("Your Username Is Too Long (Max 16 Chars)")

            # Check if player supports CPE
            supportsCPE = magicByte == 0x42

            # Return User Identification
            return protocolVersion, username, verificationKey, supportsCPE

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
                FORMAT="!BB64s",
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
            message = unpackString(message)

            # Handle Player Message
            if handleUpdate:
                await ctx.handlePlayerMessage(message)

            # Return Parsed Message
            return message

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @RequestPacket(
        "PlayerExtInfo",
        description="Handle CPE ExtInfo Packet from Player"
    )
    class PlayerExtInfoPacket(AbstractRequestPacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x10,
                FORMAT="!B64sh",
                CRITICAL=True,
                PLAYERLOOP=False
            )

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray):
            # <Player ExtInfo Packet>
            # (64String) Client Application Name
            # (Byte) Client Extension Count
            _, clientSoftware, extensionCount = struct.unpack(self.FORMAT, bytearray(rawData))

            # Unpack Client Application Name
            clientSoftware = unpackString(clientSoftware)
            if not clientSoftware.isprintable():
                raise ClientError("Invalid Character In Client Application Name.")

            # Return ExtInfo Data
            return clientSoftware, extensionCount

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @RequestPacket(
        "PlayerExtEntry",
        description="Handle CPE ExtEntry Packet from Player"
    )
    class PlayerExtEntryPacket(AbstractRequestPacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x11,
                FORMAT="!B64si",
                CRITICAL=True,
                PLAYERLOOP=False
            )

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray):
            # <Player ExtEntry Packet>
            # (64String) Extension Name
            # (Integer) Extension Version
            _, extensionName, extensionVersion = struct.unpack(self.FORMAT, bytearray(rawData))

            # Unpack Extension Name
            extensionName = unpackString(extensionName)
            if not extensionName.isalnum():
                raise ClientError("Invalid Character In Client Extension Name.")

            # Return ExtEntry Data
            return extensionName, extensionVersion

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
                FORMAT="!BB64s64sB",
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
                bytes(packageString(name)),
                bytes(packageString(motd)),
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
                FORMAT="!B",
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
                FORMAT="!B",
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
                bytes(formattedChunk),
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
                bytes(packageString(playerName)),
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
                FORMAT="!BB",
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
                FORMAT="!BB64s",
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
                packedMessage = packedMessage[:-1]  # This isnt supposed to prevent any exploits, just to prevent accidents if the message gets cut off short

            # Send Message Packet
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(playerId),
                bytes(packedMessage)
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
                FORMAT="!B64s",
                CRITICAL=True
            )

        async def serialize(self, reason: str):
            # <Player Disconnect Packet>
            # (Byte) Packet ID
            # (64String) Disconnect Reason
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                bytes(packageString(reason))
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
                FORMAT="!BB",
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

    @ResponsePacket(
        "ServerExtInfo",
        description="Response Packet To Initiate CPE Extension Negotiation"
    )
    class ServerExtInfoPacket(AbstractResponsePacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x10,
                FORMAT="!B64sh",
                CRITICAL=True
            )

        async def serialize(self, serverSoftware: str, extensionCount: int):
            # <Server ExtInfo Packet>
            # (64String) Server Application Name
            # (Byte) Server Extension Count
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                bytes(packageString(serverSoftware)),
                int(extensionCount)
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "ServerExtEntry",
        description="Response Packet To Initiate CPE Negotiation"
    )
    class ServerExtEntryPacket(AbstractResponsePacket["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x11,
                FORMAT="!B64si",
                CRITICAL=True
            )

        async def serialize(self, extensionName: str, extensionVersion: int):
            # <Server ExtEntry Packet>
            # (64String) Extension Name
            # (Integer) Extension Version
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                bytes(packageString(extensionName)),
                int(extensionVersion)
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    #
    # WORLD FORMATS
    #

    @WorldFormat(
        "Raw",
        description="Raw Map Data File",
        version="v2.0.0"
    )
    class RawWorldFormat(AbstractWorldFormat["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                EXTENSIONS=["gz"]
            )

        def loadWorld(
            self,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager,
            persistent: bool = True
        ):
            Logger.warn("The RawWorld save file format is not meant to be used in production.", module="raw-map")
            Logger.warn("Please use a more robust format like ObsidianWorld instead!", module="raw-map")

            # Seek pointer
            fileIO.seek(0)

            # Read Gzip File
            Logger.debug(f"Reading Gzip File {fileIO.name}", module="raw-map")
            gzipData = io.BytesIO(gzip.GzipFile(fileobj=fileIO).read())

            # Read Word Size
            Logger.debug("Reading World Size", module="raw-map")
            sizeX, sizeY, sizeZ = struct.unpack("!hhh", gzipData.read(6))
            worldSize = sizeX * sizeY * sizeZ

            # Read Map Data
            Logger.debug("Reading Map Data", module="raw-map")
            rawData = bytearray(gzipData.read(worldSize))

            # Create World Data
            return World(
                worldManager,  # Pass In World Manager
                Path(fileIO.name).stem,  # Pass In World Name (Save File Name Without EXT)
                sizeX, sizeY, sizeZ,  # Passing World X, Y, Z
                rawData,  # Generating Map Data
                0,  # World Seed (but ofc it doesn't exist)
                persistent=persistent,  # Pass In Persistent Flag
                fileIO=fileIO,  # Pass In File Reader/Writer
                worldFormat=self  # Pass In World Format
            )

        def saveWorld(
            self,
            world: World,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager
        ):
            Logger.warn("The RawWorld save file format is not meant to be used in production.", module="raw-map")
            Logger.warn("Please use a more robust format like ObsidianWorld instead!", module="raw-map")

            # Clearing Current Save File
            fileIO.truncate(0)
            fileIO.seek(0)

            # Saving Map To File
            fileIO.write(
                gzip.compress(
                    struct.pack(
                        "!hhh",
                        world.sizeX,
                        world.sizeY,
                        world.sizeZ
                    ) + world.mapArray
                )
            )

    @WorldFormat(
        "ObsidianWorld",
        description="Obsidian World Data File",
        version="v1.0.0"
    )
    class ObsidianWorldFormat(AbstractWorldFormat["CoreModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                EXTENSIONS=["obw"],
                METADATA_SUPPORT=True
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
            Logger.debug("Loading OBW File", module="obsidianworld")
            with zipfile.ZipFile(fileIO) as zipFile:

                # Keep track of which files have not been touched
                # We will add these back to the zip file later when saving, as to maintain backward compatibility
                untouchedFiles = set(zipFile.namelist())

                # Check validity of zip file
                Logger.debug("Checking OBW File Validity", module="obsidianworld")
                if "metadata" not in zipFile.namelist() or "map" not in zipFile.namelist():
                    raise WorldFormatError("ObsidianWorldFormat - Invalid OBW File! Missing Critical Data!")

                # Load Metadata
                Logger.debug("Loading Metadata", module="obsidianworld")
                worldMetadata = json.loads(zipFile.read("metadata").decode("utf-8"))
                untouchedFiles.remove("metadata")
                Logger.debug(f"Loaded Metadata: {worldMetadata}", module="obsidianworld")

                # Check if metadata is valid
                if self.criticalFields.intersection(set(worldMetadata.keys())) != self.criticalFields:
                    raise WorldFormatError("ObsidianWorldFormat - Invalid Metadata! Missing Critical Data!")

                # Get information out of world metadata
                Logger.debug("Parsing Metadata", module="obsidianworld")
                # Critical Values
                version = worldMetadata.get("version")
                name = worldMetadata.get("name")
                sizeX = worldMetadata.get("X")
                sizeY = worldMetadata.get("Y")
                sizeZ = worldMetadata.get("Z")
                # Optional Values
                spawnX = worldMetadata.get("spawnX", None)
                spawnY = worldMetadata.get("spawnY", None)
                spawnZ = worldMetadata.get("spawnZ", None)
                spawnYaw = worldMetadata.get("spawnYaw", None)
                spawnPitch = worldMetadata.get("spawnPitch", None)
                # Misc Values
                seed = worldMetadata.get("seed", None)
                canEdit = worldMetadata.get("canEdit", True)
                worldUUID = uuid.UUID(worldMetadata.get("worldUUID")) if "worldUUID" in worldMetadata else None
                worldCreationService = worldMetadata.get("worldCreationService", None)
                worldCreationPlayer = worldMetadata.get("worldCreationPlayer", None)
                mapGeneratorSoftware = worldMetadata.get("mapGeneratorSoftware", None)
                mapGeneratorName = worldMetadata.get("mapGeneratorName", None)
                timeCreated = datetime.datetime.fromtimestamp(worldMetadata.get("timeCreated")) if "timeCreated" in worldMetadata else None
                lastModified = datetime.datetime.fromtimestamp(worldMetadata.get("lastModified")) if "lastModified" in worldMetadata else None
                lastAccessed = datetime.datetime.fromtimestamp(worldMetadata.get("lastAccessed")) if "lastAccessed" in worldMetadata else None

                # Try parsing world generator
                Logger.debug("Parsing World Generator", module="obsidianworld")
                if mapGeneratorSoftware == "Obsidian":
                    if mapGeneratorName in MapGenerators:
                        generator = MapGenerators[mapGeneratorName]
                    else:
                        Logger.info(f"ObsidianWorldFormat - Unknown World Generator {mapGeneratorName}.", module="obsidianworld")
                        generator = None  # Continue with no generator
                else:
                    Logger.info(f"ObsidianWorldFormat - Unknown World Generator Software {mapGeneratorSoftware}.", module="obsidianworld")
                    generator = None

                # Check if version is valid
                Logger.debug("Checking Version", module="obsidianworld")
                if version != self.VERSION:
                    Logger.warn(f"ObsidianWorldFormat - World Version Mismatch! Expected: {self.VERSION} Got: {version}", module="obsidianworld")

                # Check if world names are the same
                Logger.debug("Checking World Name", module="obsidianworld")
                if name != Path(fileIO.name).stem:
                    Logger.warn(f"ObsidianWorldFormat - World Name Mismatch! Expected: {Path(fileIO.name).stem} Got: {name}", module="obsidianworld")

                # Load Additional Metadata
                Logger.debug("Loading Additional Metadata", module="obsidianworld")
                additionalMetadata: dict[tuple[str, str], WorldMetadata] = {}
                for filename in zipFile.namelist():
                    Logger.verbose(f"Checking File: {filename}", module="obsidianworld")
                    # Check if file is additional metadata
                    if filename.startswith("extmetadata/"):
                        Logger.verbose(f"File {filename} is additional metadata file. Parsing File.", module="obsidianworld")
                        # Check if metadata is valid
                        if len(filename.split("/")) != 3:
                            Logger.warn(f"ObsidianWorldFormat - Invalid Additional Metadata File! Expected: extmetadata/<software>/<name>! Got: {filename}", module="obsidianworld")
                            continue

                        # Get metadata software and name
                        _, metadataSoftware, metadataName = filename.split("/")
                        Logger.verbose(f"File {filename} is additional metadata file for [{metadataSoftware}]{metadataName}", module="obsidianworld")

                        # Get the metadata reader
                        metadataReader = WorldFormatManager.getMetadataReader(self, metadataSoftware, metadataName)
                        if metadataReader is None:
                            Logger.warn(f"ObsidianWorldFormat - World Format Does Not Support Reading Metadata: [{metadataSoftware}]{metadataName}", module="obsidianworld")
                            continue
                        Logger.verbose(f"Metadata [{metadataSoftware}]{metadataName} uses reader {metadataReader}", module="obsidianworld]")

                        # Read metadata file
                        metadataDict = json.loads(zipFile.read(filename).decode("utf-8"))
                        Logger.debug(f"Loading Additional Metadata: [{metadataSoftware}]{metadataName} - {metadataDict}", module="obsidianworld")
                        additionalMetadata[(metadataSoftware, metadataName)] = metadataReader(metadataDict)
                        untouchedFiles.remove(filename)

                # Load Map Data
                Logger.debug("Loading Map Data", module="obsidianworld")
                rawData = bytearray(gzip.GzipFile(fileobj=io.BytesIO(zipFile.read("map"))).read())
                untouchedFiles.remove("map")

                # Sanity Check File Size
                if (sizeX * sizeY * sizeZ) != len(rawData):
                    raise WorldFormatError(f"ObsidianWorldFormat - Invalid Map Data! Expected: {sizeX * sizeY * sizeZ} Got: {len(rawData)}")

                # Create World Data
                world = World(
                    worldManager,  # Pass In World Manager
                    name,
                    sizeX, sizeY, sizeZ,
                    rawData,
                    seed=seed,
                    spawnX=spawnX,
                    spawnY=spawnY,
                    spawnZ=spawnZ,
                    spawnYaw=spawnYaw,
                    spawnPitch=spawnPitch,
                    generator=generator,
                    worldFormat=self,
                    persistent=persistent,  # Pass In Persistent Flag
                    fileIO=fileIO,  # Pass In File Reader/Writer
                    canEdit=canEdit,
                    worldUUID=worldUUID,
                    worldCreationService=worldCreationService,
                    worldCreationPlayer=worldCreationPlayer,
                    mapGeneratorSoftware=mapGeneratorSoftware,
                    mapGeneratorName=mapGeneratorName,
                    timeCreated=timeCreated,
                    lastModified=lastModified,
                    lastAccessed=lastAccessed,
                    additionalMetadata=additionalMetadata
                )

                # Check if there are any files left in the zip file
                if len(untouchedFiles) > 0:
                    Logger.warn(f"ObsidianWorldFormat - {len(untouchedFiles)} Unknown Files In OBW File: {untouchedFiles}", module="obsidianworld")
                    unrecognizedFiles: dict[str, io.BytesIO] = {}
                    # Make a copy of each unrecognized file and put them in unrecognizedFiles
                    for filename in untouchedFiles:
                        unrecognizedFiles[filename] = io.BytesIO(zipFile.read(filename))
                    # Add unrecognizedFiles to world
                    setattr(world, "unrecognizedFiles", unrecognizedFiles)

                # Close Zip File
                zipFile.close()

            # Return World
            return world

        def saveWorld(
            self,
            world: World,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager
        ):
            # Set up the metadata about the world
            Logger.debug("Saving Metadata", module="obsidianworld")
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
            worldMetadata["canEdit"] = world.canEdit
            worldMetadata["worldUUID"] = str(world.worldUUID)
            worldMetadata["worldCreationService"] = world.worldCreationService
            worldMetadata["worldCreationPlayer"] = world.worldCreationPlayer
            worldMetadata["mapGeneratorSoftware"] = world.mapGeneratorSoftware
            worldMetadata["mapGeneratorName"] = world.mapGeneratorName
            worldMetadata["timeCreated"] = int(time.mktime(world.timeCreated.timetuple()))
            worldMetadata["lastModified"] = int(time.mktime(world.lastModified.timetuple()))
            worldMetadata["lastAccessed"] = int(time.mktime(world.lastAccessed.timetuple()))

            # Set Generator Info
            if world.generator:
                worldMetadata["generator"] = world.generator.NAME
            else:
                worldMetadata["generator"] = None
            worldMetadata["seed"] = world.seed

            # Generate Additional Metadata
            Logger.debug("Saving Additional Metadata", module="obsidianworld")
            additionalMetadata: dict[tuple[str, str], dict] = {}
            for (metadataSoftware, metadataName), metadata in world.additionalMetadata.items():
                Logger.verbose(f"Saving Additional Metadata: [{metadataSoftware}]{metadataName} - {metadata}", module="obsidianworld")
                # Get metadata writer
                metadataWriter = WorldFormatManager.getMetadataWriter(self, metadataSoftware, metadataName)
                if metadataWriter is None:
                    Logger.warn(f"ObsidianWorldFormat - World Format Does Not Support Writing Metadata: [{metadataSoftware}]{metadataName}", module="obsidianworld")
                    continue
                Logger.verbose(f"Metadata [{metadataSoftware}]{metadataName} uses writer {metadataWriter}", module="obsidianworld]")

                # Create metadata dict
                Logger.debug(f"Generating Additional Metadata: [{metadataSoftware}]{metadataName} - {metadata}", module="obsidianworld")
                additionalMetadata[(metadataSoftware, metadataName)] = metadataWriter(metadata)

            # Clearing Current Save File
            fileIO.truncate(0)
            fileIO.seek(0)

            # Create zip file
            with zipfile.ZipFile(fileIO, "w") as zipFile:
                # Write the metadata file
                Logger.debug("Writing metadata file", module="obsidianworld")
                zipFile.writestr("metadata", json.dumps(worldMetadata, indent=4))
                # Write additional metadata files
                for (metadataSoftware, metadataName), metadataDict in additionalMetadata.items():
                    Logger.debug(f"Writing additional metadata file: {metadataName}", module="obsidianworld")
                    zipFile.writestr(str(Path("extmetadata", metadataSoftware, metadataName)), json.dumps(metadataDict, indent=4))
                # Write the map file
                Logger.debug("Writing map file", module="obsidianworld")
                zipFile.writestr("map", world.gzipMap())
                # Check if there were any unrecognized files
                if hasattr(world, "unrecognizedFiles"):
                    unrecognizedFiles: dict[str, io.BytesIO] = getattr(world, "unrecognizedFiles")
                    Logger.debug(f"Writing {len(unrecognizedFiles)} unrecognized files: {unrecognizedFiles}", module="obsidianworld")
                    for filename, file in unrecognizedFiles.items():
                        zipFile.writestr(filename, file.read())

    #
    # MAP GENERATORS
    #

    @MapGenerator(
        "Flat",
        description="Default Map Generator. Just Flat.",
        version="v1.0.0"
    )
    class FlatGenerator(AbstractMapGenerator["CoreModule"]):
        def __init__(self, *args):
            super().__init__(*args)

        # Default Map Generator (Creates Flat Map Of Grass And Dirt)
        def generateMap(self, sizeX: int, sizeY: int, sizeZ: int, seed: int, generationStatus: MapGeneratorStatus):
            # Generate Map
            mapData = bytearray(0)

            # Pre-generate air, dirt, and grass layers
            sliceAir = bytearray([Blocks.Air.ID]) * (sizeX * sizeZ)
            sliceDirt = bytearray([Blocks.Dirt.ID]) * (sizeX * sizeZ)
            sliceGrass = bytearray([Blocks.Grass.ID]) * (sizeX * sizeZ)

            # Create World
            grassHeight = sizeY // 2
            generationStatus.setStatus(0, "Placing Dirt....")
            for y in range(sizeY):
                if y > grassHeight:
                    mapData.extend(sliceAir)
                elif y == grassHeight:
                    generationStatus.setStatus(y / sizeY, "Planting Grass....")
                    mapData.extend(sliceGrass)
                else:
                    mapData.extend(sliceDirt)

            generationStatus.setDone()
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


# Helper functions for the command generation
class CommandHelper():
    @staticmethod
    def centerMessage(message: str, color: str = "", padCharacter: str = "=") -> str:
        # Calculate the number of padding to add
        maxMessageLength = 64
        padSpace = max(
            maxMessageLength - len(message) - 2 * (len(color) + 1) - 2,
            0  # Maxing at zero in case the final output goes into the negatives
        )
        padLeft = padSpace // 2
        padRight = padSpace - padLeft

        # Generate and return padded message
        return (color + padCharacter * padLeft) + (" " + message + " ") + (color + padCharacter * padRight) + "&f"

    @staticmethod
    def formatList(
        values: Iterable[Any],
        processInput: Callable[[Any], str] = str,
        initialMessage: str = "",
        separator: str = "",
        lineStart: str = "",
        lineEnd: str = "",
        prefix: str = "",
        postfix: str = ""
    ) -> list[str]:
        output = []
        output.append(initialMessage)
        isEmpty = True

        i = iter(values)  # Use an iterable to loop through values
        while (val := next(i, None)):
            isEmpty = False
            # Format Val
            val = prefix + processInput(val) + postfix + separator

            # Check if adding the player name will overflow the max message length
            if len(output[-1]) + len(lineEnd) + len(val) > MAX_MESSAGE_LENGTH:
                output[-1] += lineEnd  # Add whatever postfix is needed
                output.append(lineStart)  # Add a new line for output (prefix)

            # Add Player Name
            output[-1] += val

        # Remove final separator from the last line
        if separator and not isEmpty:
            output[-1] = output[-1][:-len(separator)]

        return output
