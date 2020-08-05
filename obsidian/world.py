from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server

from typing import List, Optional
import io
import os
import gzip
import struct

from obsidian.log import Logger
from obsidian.player import WorldPlayerManager, Player
from obsidian.blocks import BlockManager
from obsidian.worldformat import WorldFormats
from obsidian.mapgen import MapGenerators, AbstractMapGenerator
from obsidian.constants import ClientError, FatalError, MapGenerationError, BlockError, WorldError


class WorldManager:
    def __init__(self, server: Server, blacklist: List[str] = []):
        self.server = server
        self.worlds = dict()
        self.blacklist = blacklist
        self.persistant = True
        self.worldFormat = None

        # Get worldFormat Using Given World Format Key
        # Loop Through All World Formats
        for worldFormat in WorldFormats._format_list.values():
            # Check If key Matches With Config Key List
            if self.server.config.defaultSaveFormat.lower() in worldFormat.KEYS:
                # Set World Format
                self.worldFormat = worldFormat

        # Check If World Format Was Set
        if self.worldFormat is None:
            raise FatalError(f"Unknown World Format Key {self.server.config.defaultSaveFormat} Given In Server Config!")
        Logger.info(f"Using World Format {self.worldFormat.NAME}", module="init-world")

        # If World Location Was Not Given, Disable Persistance
        # (Don't Save / Load)
        if self.server.config.worldSaveLocation is None:
            Logger.warn("World Save Location Was Not Defined. Creating Non-Persistant World!!!", module="init-world")
            self.persistant = False

    def createWorld(
        self,
        worldName,
        sizeX,
        sizeY,
        sizeZ,
        generator: AbstractMapGenerator,
        *args,  # Arguments To Be Passed To World Generator
        persistant=True,
        spawnX=0,
        spawnY=0,
        spawnZ=0,
        **kwargs  # Keyword Arguments To Be Passed To World Generator
    ):
        Logger.info(f"Creating New World {worldName}", module="world")
        # Check If World Already Exists
        if worldName in self.worlds.keys():
            raise WorldError(f"Trying To Generate World With Already Existing Name {worldName}!")

        # Create World
        self.worlds[worldName] = World(
            self,  # Pass In World Manager
            worldName,  # Pass In World Name
            sizeX, sizeY, sizeZ,  # Passing World X, Y, Z
            self.generateMap(sizeX, sizeY, sizeZ, generator, *args, **kwargs),  # Generating Map Data
            generator=generator,  # Pass In World Generator
            persistant=persistant,  # Pass In Persistant Flag
            # Spawn Information
            spawnX=spawnX,
            spawnY=spawnY,
            spawnZ=spawnZ
        )

    def generateMap(self, sizeX, sizeY, sizeZ, generator: AbstractMapGenerator, *args, **kwargs):
        Logger.debug(f"Generating World With Size {sizeX}, {sizeY}, {sizeX} With Generator {generator.NAME}", module="init-world")
        # Call Generate Map Function From Generator
        generatedMap = generator.generateMap(sizeX, sizeY, sizeZ, *args, **kwargs)

        # Verify Map Data Size
        expectedSize = sizeX * sizeY * sizeZ
        if len(generatedMap) != expectedSize:
            raise MapGenerationError(f"Expected Map Size {expectedSize} While Generating World. Got {len(generatedMap)}")

        Logger.debug(f"Generated Map With Final Size Of {len(generatedMap)}", module="init-world")
        # Return Generated Map Bytesarray
        return generatedMap

    def loadWorlds(self):
        Logger.debug("Starting Attempt to Load All Worlds", module="world-load")
        if self.persistant and (self.server.config.worldSaveLocation is not None):
            Logger.debug(f"Beginning To Scan Through {self.server.config.worldSaveLocation} Dir", module="world-load")
            # Loop Through All Files Given In World Folder
            for filename in os.listdir(self.server.config.worldSaveLocation):
                Logger.verbose(f"Checking Extention of World File {filename}", module="world-load")
                # Check If File Type Matches With The Extentions Provided By worldFormat
                if any([filename.endswith(ext) for ext in self.worldFormat.EXTENTIONS]):
                    Logger.debug(f"Detected World File {filename}. Attempting To Load World", module="world-load")
                    # (Attempt) To Load Up World
                    try:
                        f = open(os.path.join(self.server.config.worldSaveLocation, filename), "rb")
                        # Get Pure File Name (No Extentions)
                        saveName = os.path.splitext(os.path.basename(f.name))[0]
                        Logger.info(f"Loading World {saveName}", module="world-load")
                        self.worlds[saveName] = WorldFormats.Raw.loadWorld(f, self, persistant=False)
                    except Exception as e:
                        Logger.error(f"Error While Loading World {filename} - {type(e).__name__}: {e}", module="world-load", askConfirmation=True)
        else:
            Logger.debug("World Manager Is Non Persistant!", module="world-load")
            # Create Non-Persistant Temporary World
            defaultWorldName = self.server.config.defaultWorld
            defaultGenerator = MapGenerators[self.server.config.defaultGenerator]
            Logger.debug(f"Creating Temporary World {defaultWorldName}", module="world-load")
            self.createWorld(
                defaultWorldName,
                32, 32, 32,
                defaultGenerator,
                persistant=False,
                spawnX=8 * 32 + 51,
                spawnY=17 * 32 + 51,
                spawnZ=8 * 32 + 51,
                grassHeight=16
            )
        # TODO: Better Handling
        # Check If DefaultWorld Is Loaded
        if self.server.config.defaultWorld not in self.worlds.keys():
            raise WorldError(f"Default World {self.server.config.defaultWorld} Not Loaded. Consider Checking If World Exists And/Or Changing The Default World In Config.")


class World:
    def __init__(
        self,
        worldManager: WorldManager,
        name: str,
        sizeX: int,
        sizeY: int,
        sizeZ: int,
        mapArray: bytearray,
        generator: AbstractMapGenerator = None,
        persistant: bool = True,
        canEdit: bool = True,
        spawnX: int = 0,
        spawnY: int = 0,
        spawnZ: int = 0,
        spawnYaw: int = 0,
        spawnPitch: int = 0,
        maxPlayers: int = 250,
        uuid: str = None
    ):
        # Y is the height
        self.worldManager = worldManager
        self.name = name
        self.generator = generator
        self.sizeX = sizeX
        self.sizeY = sizeY
        self.sizeZ = sizeZ
        self.mapArray = mapArray
        self.persistant = persistant
        self.canEdit = canEdit
        self.spawnX = spawnX
        self.spawnY = spawnY
        self.spawnZ = spawnZ
        self.spawnYaw = spawnYaw
        self.spawnPitch = spawnPitch
        self.maxPlayers = maxPlayers
        self.uuid = uuid  # UUID for CW Capability

        # Initialize WorldPlayerManager
        Logger.info("Initializing World Player Manager", module="init-world")
        self.playerManager = WorldPlayerManager(self)

    def getBlock(self, blockX, blockY, blockZ):
        # Gets Block Obj Of Requested Block
        Logger.verbose(f"Getting World Block {blockX}, {blockY}, {blockZ}", module="world")

        # Check If Block Is Out Of Range
        if blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ:
            raise BlockError("Requested Block Is Out Of Range")
        return BlockManager.getBlockById(self.mapArray[blockX + self.sizeX * (blockZ + self.sizeZ * blockY)])

    def setBlock(self, blockX, blockY, blockZ, blockType, player: Optional[Player] = None):
        # Handles Block Updates In Server + Checks If Block Placement Is Allowed
        Logger.debug(f"Setting World Block {blockX}, {blockY}, {blockZ} to {blockType.ID}", module="world")

        # Checking If User Can Set Blocks
        if player is not None:  # Checking If User Was Passed
            if not self.canEdit:  # Checking If World Is Read-Only
                if not player.opStatus:  # Checking If Player Is Not OP
                    raise ClientError("You Do Not Have Permission To Edit This Block")

        # Check If Block Is Out Of Range
        if blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ:
            raise BlockError("Block Placement Is Out Of Range")
        self.mapArray[blockX + self.sizeX * (blockZ + self.sizeZ * blockY)] = blockType.ID

    def saveMap(self):
        # TODO
        if self.persistant:
            # TODO: World File Saving
            raise NotImplementedError("Persistant World Loading Is Not Implemented")
        else:
            Logger.warn(f"World {self.name} Is Not Persistant! Not Saving.", module="world-save")

    def gzipMap(self, compressionLevel=-1, includeSizeHeader=False):
        # If Gzip Compression Level Is -1, Use Default!
        # includeSizeHeader Dictates If Output Should Include Map Size Header Used For Level Init

        # Check If Compression Is -1 (Use Server gzipCompressionLevel)
        if compressionLevel == -1:
            compressionLevel = self.worldManager.server.config.gzipCompressionLevel
        # Check If Compression Level Is Valid
        elif compressionLevel >= 0 and compressionLevel <= 9:
            pass
        # Invalid Compression Level!
        else:
            Logger.error(f"Invalid GZIP Compression Level Of {compressionLevel}!!!", module="world", askConfirmation=True)
            Logger.warn("Using Fallback Compression Level Of 0", module="world")
            compressionLevel = 0

        Logger.debug(f"Compressing Map {self.name} With Compression Level {compressionLevel}", module="world")
        # Create File Buffer
        buf = io.BytesIO()
        # Check If Size Header Is Needed (Using Bytes For '+' Capabilities)
        header = bytes()
        if includeSizeHeader:
            Logger.debug("Packing Size Header", module="world")
            header = header + bytes(struct.pack('!I', len(self.mapArray)))
        # Gzip World
        with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=compressionLevel) as f:
            f.write(header + bytes(self.mapArray))

        # Extract and Return Gzip Data
        gzipData = buf.getvalue()
        Logger.debug(f"GZipped Map! GZ SIZE: {len(gzipData)}", module="world")
        return gzipData
