from __future__ import annotations
from os import close
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
from obsidian.blocks import BlockManager, Blocks
from obsidian.worldformat import WorldFormats
from obsidian.mapgen import MapGenerators, AbstractMapGenerator
from obsidian.constants import (
    ClientError,
    FatalError,
    MapGenerationError,
    BlockError,
    WorldError,
    SERVERPATH
)


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
        spawnX: Optional[int] = None,
        spawnY: Optional[int] = None,
        spawnZ: Optional[int] = None,
        spawnPitch: Optional[int] = None,
        spawnYaw: Optional[int] = None,
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
            spawnZ=spawnZ,
            spawnPitch=spawnPitch,
            spawnYaw=spawnYaw
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
            for filename in os.listdir(os.path.join(SERVERPATH, self.server.config.worldSaveLocation)):
                # Get Pure File Name (No Extentions)
                saveName = os.path.splitext(os.path.basename(filename))[0]
                Logger.verbose(f"Checking Extention and Blacklist Status of World File {filename}", module="world-load")
                # Check If File Type Matches With The Extentions Provided By worldFormat
                # Also Check If World Is Blacklisted
                if any([filename.endswith(ext) for ext in self.worldFormat.EXTENTIONS]) and (saveName not in self.server.config.worldBlacklist):
                    Logger.debug(f"Detected World File {filename}. Attempting To Load World", module="world-load")
                    # (Attempt) To Load Up World
                    try:
                        Logger.info(f"Loading World {saveName}", module="world-load")
                        fileIO = open(os.path.join(SERVERPATH, self.server.config.worldSaveLocation, filename), "rb")
                        self.worlds[saveName] = self.worldFormat.loadWorld(fileIO, self, persistant=self.persistant)
                    except Exception as e:
                        Logger.error(f"Error While Loading World {filename} - {type(e).__name__}: {e}", module="world-load")
                        Logger.askConfirmation()
            # Check If Default World Is Loaded
            if self.server.config.defaultWorld not in self.worlds.keys():
                # Check if other worlds were loaded as well
                if len(self.worlds.keys()) > 0:
                    Logger.warn(f"Default World {self.server.config.defaultWorld} Not Loaded.", module="world-load")
                    Logger.warn("Consider Checking If World Exists. Consider Changing The Default World and/or File Format In Config.", module="world-load")
                    # Ask User If They Want To Continue With World Generation
                    Logger.warn(f"Other Worlds Were Detected. Generate New World With Name {self.server.config.defaultWorld}?", module="world-load")
                    Logger.askConfirmation(message="Generate New World?")
                else:
                    Logger.warn("No Existing Worlds Were Detected. Generating New World!", module="world-load")
                # Generate New World
                defaultWorldName = self.server.config.defaultWorld
                defaultGenerator = MapGenerators[self.server.config.defaultGenerator]
                Logger.debug(f"Creating World {defaultWorldName}", module="world-load")
                self.createWorld(
                    defaultWorldName,
                    self.server.config.defaultWorldSizeX,
                    self.server.config.defaultWorldSizeY,
                    self.server.config.defaultWorldSizeZ,
                    defaultGenerator,
                    persistant=self.persistant,
                    grassHeight=16
                )
        else:
            Logger.debug("World Manager Is Non Persistant!", module="world-load")
            # Create Non-Persistant Temporary World
            defaultWorldName = self.server.config.defaultWorld
            defaultGenerator = MapGenerators[self.server.config.defaultGenerator]
            Logger.debug(f"Creating Temporary World {defaultWorldName}", module="world-load")
            self.createWorld(
                defaultWorldName,
                self.server.config.defaultWorldSizeX,
                self.server.config.defaultWorldSizeY,
                self.server.config.defaultWorldSizeZ,
                defaultGenerator,
                persistant=False,
                maxPlayers=self.server.config.worldMaxPlayers,
                grassHeight=self.server.config.defaultWorldSizeY // 2
            )

    def saveWorlds(self):
        Logger.debug("Starting Attempt to Save All Worlds", module="world-save")
        if self.persistant and (self.server.config.worldSaveLocation is not None):
            Logger.info("Saving All Worlds...", module="world-save")
            # Loop through all worlds and attempt to save!
            for worldName, world in self.worlds.items():
                Logger.debug(f"Trying To Save World {worldName}", module="world-save")
                # Check persistance
                if world.persistant:
                    try:
                        # Saving World
                        Logger.info(f"Saving World {worldName}", module="world-save")
                        world.saveMap()
                    except Exception as e:
                        Logger.error(f"Error While Saving World {worldName} - {type(e).__name__}: {e}", module="world-save")
                else:
                    Logger.warn(f"World {worldName} Is Non Persistant! Skipping World Save!", module="world-save")
        else:
            Logger.warn("World Manager Is Non Persistant! Skipping World Save!", module="world-save")

    def closeWorlds(self):
        Logger.debug("Starting Attempt to Close All Worlds", module="world-close")
        Logger.info("Closing All Worlds...", module="world-close")
        # Loop through all worlds and attempt to close
        for worldName in list(self.worlds.keys()):  # Setting as list so dict size can change mid execution
            try:
                Logger.info(f"Closing World {worldName}", module="world-close")
                # Getting world obj
                world = self.worlds[worldName]

                # Removing world from dict
                Logger.debug("Removed world from dict", module="world-close")
                del self.worlds[worldName]

                # Checking if World and Server is Persistant
                if self.persistant and (self.server.config.worldSaveLocation is not None) and world.persistant:
                    # Closing worlds fileIO
                    Logger.debug("Closing World FileIO", module="world-close")
                    world.fileIO.close()
            except Exception as e:
                Logger.error(f"Error While Closing World {worldName} - {type(e).__name__}: {e}", module="world-close")


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
        persistant: bool = False,
        fileIO: Optional[io.BufferedRandom] = None,
        canEdit: bool = True,
        spawnX: Optional[int] = None,
        spawnY: Optional[int] = None,
        spawnZ: Optional[int] = None,
        spawnYaw: Optional[int] = None,
        spawnPitch: Optional[int] = None,
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
        self.spawnX = spawnX
        self.spawnZ = spawnZ
        self.spawnY = spawnY
        self.spawnYaw = spawnYaw
        self.spawnPitch = spawnPitch
        self.mapArray = mapArray
        self.persistant = persistant
        self.fileIO = fileIO
        self.canEdit = canEdit
        self.maxPlayers = maxPlayers
        self.uuid = uuid  # UUID for CW Capability

        # Check if file IO was given if persistant
        if self.persistant:
            if self.fileIO is None:
                # Setting persistance to false because fileIO was not given
                self.persistant = False
                Logger.error(f"World Format {self.worldManager.worldFormat.NAME} Created Persistant World Without Providing FileIO! Please Report To Author! Setting World As Non-Persistant.", "world-load")
                Logger.askConfirmation()
            else:
                Logger.debug(f"Persistant World Has FileIO {self.fileIO}", "world-load")

        # Generate/Set Spawn Coords
        # Set spawnX
        if self.spawnX is None:
            # Generate SpawnX (Set to middle of map)
            self.spawnX = (self.sizeX // 2) * 32 + 51
            Logger.verbose(f"spawnX was not provided. Generated to {self.spawnX}")

        # Set spawnZ
        if self.spawnZ is None:
            # Generate SpawnZ (Set to middle of map)
            self.spawnZ = (self.sizeZ // 2) * 32 + 51
            Logger.verbose(f"spawnZ was not provided. Generated to {self.spawnZ}")

        # Set spawnY
        if self.spawnY is None:
            # Kinda hacky to get the block coords form the in-game coords
            self.spawnY = (self.getHighestBlock(round((self.spawnX - 51) / 32), round((self.spawnZ - 51) / 32)) + 1) * 32 + 51
            Logger.verbose(f"spawnY was not provided. Generated to {self.spawnY}")

        # Set spawnYaw
        if spawnYaw is None:
            # Generate SpawnYaw (0)
            self.spawnYaw = 0
            Logger.verbose(f"spawnYaw was not provided. Generated to {self.spawnYaw}")

        # Set spawnPitch
        if spawnPitch is None:
            # Generate SpawnPitch (0)
            self.spawnPitch = 0
            Logger.verbose(f"spawnYaw was not provided. Generated to {self.spawnYaw}")

        # Initialize WorldPlayerManager
        Logger.info("Initializing World Player Manager", module="init-world")
        self.playerManager = WorldPlayerManager(self)

    def getBlock(self, blockX, blockY, blockZ):
        # Gets Block Obj Of Requested Block
        Logger.verbose(f"Getting World Block {blockX}, {blockY}, {blockZ}", module="world")

        # Check If Block Is Out Of Range
        if blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ:
            raise BlockError(f"Requested Block Is Out Of Range ({blockX}, {blockY}, {blockZ})")
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
            raise BlockError(f"Block Placement Is Out Of Range ({blockX}, {blockY}, {blockZ})")
        self.mapArray[blockX + self.sizeX * (blockZ + self.sizeZ * blockY)] = blockType.ID

    def getHighestBlock(self, blockX, blockZ, start: int = None):
        # Returns the highest block
        # Set and Verify Scan Start Value
        if start is None:
            scanY = self.sizeY - 1
        else:
            if start > self.sizeY:
                Logger.warn(f"Trying To Get Heighest Block From Location Greater Than Map Size (MapHeight: {self.sizeY}, Given: {start})")
                scanY = self.sizeY - 1
            else:
                scanY = start

        # Scan Downwards To Get Heighest Block
        while self.getBlock(blockX, scanY, blockZ) is Blocks.Air:
            if scanY == 0:
                break
            # Scan Downwards
            scanY -= 1

        return scanY

    def saveMap(self):
        if self.persistant:
            Logger.info(f"Attempting To Save World {self.name}", module="world-save")
            self.worldManager.worldFormat.saveWorld(self, self.fileIO, self.worldManager)
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
            Logger.error(f"Invalid GZIP Compression Level Of {compressionLevel}!!!", module="world")
            Logger.askConfirmation()
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
