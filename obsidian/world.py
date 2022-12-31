from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server

from typing import Optional
from pathlib import Path
import io
import gzip
import struct
import random

from obsidian.log import Logger
from obsidian.player import WorldPlayerManager, Player
from obsidian.blocks import BlockManager, Blocks, AbstractBlock
from obsidian.worldformat import WorldFormats, AbstractWorldFormat
from obsidian.mapgen import (
    MapGenerators,
    AbstractMapGenerator
)
from obsidian.packet import Packets
from obsidian.constants import SERVERPATH
from obsidian.types import format_name
from obsidian.errors import (
    FatalError,
    MapGenerationError,
    BlockError,
    WorldError,
    ClientError,
    WorldSaveError,
    ConverterError
)


class WorldManager:
    def __init__(self, server: Server, ignorelist: list[str] = []):
        self.server: Server = server
        self.worlds: dict[str, World] = dict()
        self.ignorelist: list[str] = ignorelist
        self.persistent: bool = True
        # Defined Later In Init
        # self.worldFormat: AbstractWorldFormat

        # Get worldFormat Using Given World Format Key
        # Loop Through All World Formats
        for worldFormat in WorldFormats._format_dict.values():
            # Check If key Matches With Config Key List
            if format_name(self.server.config.defaultSaveFormat) in worldFormat.KEYS:
                # Set World Format
                self.worldFormat: AbstractWorldFormat = worldFormat
                break
        # Check If World Format Was Found
        else:
            raise FatalError(f"Unknown World Format Key {self.server.config.defaultSaveFormat} Given In Server Config!")
        Logger.info(f"Using World Format {self.worldFormat.NAME}", module="init-world")

        # If World Location Was Not Given, Disable Persistance
        # (Don't Save / Load)
        if self.server.config.worldSaveLocation is None:
            Logger.warn("World Save Location Was Not Defined. Creating Non-Persistent World!!!", module="init-world")
            self.persistent = False

    def getWorld(self, worldName: str, lowerName: bool = True) -> World:
        Logger.debug(f"Getting World {worldName} By Name", module="player")
        # If lowerName is set, automatically lower the world name
        if lowerName:
            worldName = worldName.lower()
        # Check if world is in the server
        if worldName in self.worlds:
            return self.worlds[worldName]
        else:
            raise NameError("World Does Not Exist!")

    def createWorld(
        self,
        worldName: str,
        sizeX: int,
        sizeY: int,
        sizeZ: int,
        seed: Optional[int],
        generator: AbstractMapGenerator,
        persistent: bool = True,
        spawnX: Optional[int] = None,
        spawnY: Optional[int] = None,
        spawnZ: Optional[int] = None,
        spawnPitch: Optional[int] = None,
        spawnYaw: Optional[int] = None,
    ) -> World:
        Logger.info(f"Creating New World {worldName}...", module="world-create")
        # Check If World Already Exists
        if worldName in self.worlds.keys():
            raise WorldError(f"Trying To Generate World With Already Existing Name {worldName}!")

        # Creating Save File If World Is Persistent
        Logger.debug("Creating Save File If World Is Persistent", module="world-create")
        if self.persistent and self.server.config.worldSaveLocation:
            fileIO = self.createWorldFile(self.server.config.worldSaveLocation, worldName)
            Logger.debug(f"World Is Persistent! Created New FileIO {fileIO}", module="world-create")
            pass
        else:
            Logger.debug("World Is Not Persistent!", module="world-create")
            fileIO = None

        # Generate Seed if no seed was passed
        Logger.debug("Generating Seed If No Seed Was Passed", module="world-create")
        if seed is None:
            seed = random.randint(0, 2**64)

        # Create World
        self.worlds[worldName] = World(
            self,  # Pass In World Manager
            worldName,  # Pass In World Name
            sizeX, sizeY, sizeZ,  # Passing World X, Y, Z
            seed,  # Passing In World Seed
            # Generate the actual map
            self.generateMap(
                sizeX,
                sizeY,
                sizeZ,
                seed,
                generator
            ),  # Generating Map Data
            # Spawn Information
            spawnX=spawnX,
            spawnY=spawnY,
            spawnZ=spawnZ,
            spawnPitch=spawnPitch,
            spawnYaw=spawnYaw,
            # World Config Info
            generator=generator,  # Pass In World Generator
            persistent=persistent,  # Pass In Persistent Flag
            fileIO=fileIO  # Pass In FileIO Object (if persistent set)
        )

        # Saving World
        Logger.info(f"Saving World {worldName}", module="world-create")
        self.worlds[worldName].saveMap()
        return self.worlds[worldName]

    def generateMap(self, sizeX: int, sizeY: int, sizeZ: int, seed: int, generator: AbstractMapGenerator, *args, **kwargs) -> bytearray:
        Logger.debug(f"Generating World With Size {sizeX}, {sizeY}, {sizeX} With Generator {generator.NAME}", module="init-world")
        # Call Generate Map Function From Generator
        generatedMap = generator.generateMap(sizeX, sizeY, sizeZ, seed, *args, **kwargs)

        # Verify Map Data Size
        expectedSize = sizeX * sizeY * sizeZ
        if len(generatedMap) != expectedSize:
            raise MapGenerationError(f"Expected Map Size {expectedSize} While Generating World. Got {len(generatedMap)}")

        Logger.debug(f"Generated Map With Final Size Of {len(generatedMap)}", module="init-world")
        # Return Generated Map Bytesarray
        return generatedMap

    def loadWorlds(self) -> bool:
        Logger.debug("Starting Attempt to Load All Worlds", module="world-load")
        if self.persistent and (self.server.config.worldSaveLocation is not None):
            Logger.debug(f"Beginning To Scan Through {self.server.config.worldSaveLocation} Dir", module="world-load")
            # Loop Through All Files Given In World Folder
            for savefile in Path(SERVERPATH, self.server.config.worldSaveLocation).iterdir():
                # Get Pure File Name (No Extentions)
                savename = savefile.stem
                Logger.verbose(f"Checking Extention and Status of World File {savefile}", module="world-load")
                # Check If File Type Matches With The Extentions Provided By worldFormat
                if savefile.suffix[1:] not in self.worldFormat.EXTENTIONS:  # doing [1:] to remove the "."
                    Logger.debug(f"Ignoring World File {savefile}. File Extention Not Known!", module="world-load")
                # Also Check If World Is Ignored
                elif savename in self.ignorelist:
                    Logger.info(f"Ignoring World File {savefile}. World Name Is On Ignore List!", module="world-load")
                # Also Check If World Name Is Already Loaded (Same File Names with Different Extentions)
                elif savename in self.worlds.keys():
                    Logger.warn(f"Ignoring World File {savefile}. World With Similar Name Has Already Been Registered!", module="world-load")
                    Logger.warn(f"World File {self.worlds[savename].name} Conflicts With World File {savefile}!", module="world-load")
                    Logger.askConfirmation()
                else:
                    Logger.debug(f"Detected World File {savefile}. Attempting To Load World", module="world-load")
                    # (Attempt) To Load Up World
                    try:
                        Logger.info(f"Loading World {savename}", module="world-load")
                        fileIO = open(savefile, "rb+")
                        self.worlds[savename] = self.worldFormat.loadWorld(fileIO, self, persistent=self.persistent)
                    except Exception as e:
                        Logger.error(f"Error While Loading World {savefile} - {type(e).__name__}: {e}", module="world-load")
                        Logger.askConfirmation()
            # Check If Default World Is Loaded
            if self.server.config.defaultWorld not in self.worlds.keys():
                # Check if other worlds were loaded as well
                if len(self.worlds.keys()) > 0:
                    Logger.warn(f"Default World {self.server.config.defaultWorld} Not Loaded.", module="world-load")
                    Logger.warn("Checking If World Exists. Consider Changing The Default World and/or File Format In Config.", module="world-load")
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
                    self.server.config.worldSizeX,
                    self.server.config.worldSizeY,
                    self.server.config.worldSizeZ,
                    self.server.config.worldSeed,
                    defaultGenerator,
                    persistent=self.persistent
                )
        else:
            Logger.debug("World Manager Is Non Persistent!", module="world-load")
            # Create Non-Persistent Temporary World
            defaultWorldName = self.server.config.defaultWorld
            defaultGenerator = MapGenerators[self.server.config.defaultGenerator]
            Logger.debug(f"Creating Temporary World {defaultWorldName}", module="world-load")
            self.createWorld(
                defaultWorldName,
                self.server.config.worldSizeX,
                self.server.config.worldSizeY,
                self.server.config.worldSizeZ,
                self.server.config.worldSeed,
                defaultGenerator,
                persistent=False,
            )
        return True  # Returning true to indicate that all worlds were loaded successfully.

    def saveWorlds(self) -> bool:
        Logger.debug("Starting Attempt to Save All Worlds", module="world-save")
        if self.persistent and (self.server.config.worldSaveLocation is not None):
            Logger.info("Saving All Worlds...", module="world-save")
            # Loop through all worlds and attempt to save!
            for worldName, world in self.worlds.items():
                Logger.debug(f"Trying To Save World {worldName}", module="world-save")
                # Check persistance
                if world.persistent:
                    try:
                        # Saving World
                        Logger.info(f"Saving World {worldName}", module="world-save")
                        world.saveMap()
                    except Exception as e:
                        Logger.error(f"Error While Saving World {worldName} - {type(e).__name__}: {e}", module="world-save")
                else:
                    Logger.warn(f"World {worldName} Is Non Persistent! Skipping World Save!", module="world-save")
        else:
            Logger.warn("World Manager Is Non Persistent! Skipping World Save!", module="world-save")
        return True  # Return True to indicate that world save was successful.

    def closeWorlds(self) -> bool:
        Logger.debug("Starting Attempt to Close All Worlds", module="world-close")
        # Loop through all worlds and attempt to close
        for worldName in list(self.worlds.keys()):  # Setting as list so dict size can change mid execution
            try:
                Logger.info(f"Closing World {worldName}", module="world-close")
                # Getting world obj
                world = self.worlds[worldName]

                # Removing world from dict
                Logger.debug("Removed world from dict", module="world-close")
                del self.worlds[worldName]

                # Checking if World and Server is Persistent
                if self.persistent and (self.server.config.worldSaveLocation is not None) and world.persistent and world.fileIO:
                    # Closing worlds fileIO
                    Logger.debug("Closing World FileIO", module="world-close")
                    world.fileIO.close()
            except Exception as e:
                Logger.error(f"Error While Closing World {worldName} - {type(e).__name__}: {e}", module="world-close")
        return True  # Returning True to indicate all worlds were closed

    def createWorldFile(self, savePath: str, worldName: str, worldFormat: Optional[AbstractWorldFormat] = None) -> io.BufferedRandom:
        Logger.debug(f"Attempting to create world file with name {worldName}", module="world-gen")
        # Checking if World is Persistent
        if self.server.config.worldSaveLocation is None or not self.persistent:
            raise WorldSaveError("Trying To Create World File When Server Is Not Persistent")

        # Checking if World Format was Passed In (Setting as default if not)
        if worldFormat is None:
            worldFormat = self.worldFormat

        # Generating File Path
        worldPath = Path(
            SERVERPATH,
            savePath,
            worldName + "." + worldFormat.EXTENTIONS[0]  # Gets the first value in the valid extentions list
        )
        Logger.debug(f"File world path is {worldPath}", module="world-gen")

        # Check if file already exists
        if worldPath.is_file():
            raise WorldSaveError(f"Trying To Create World File {worldPath} That Already Exists")

        return open(worldPath, "wb+")


class World:
    def __init__(
        self,
        worldManager: WorldManager,
        name: str,
        sizeX: int,
        sizeY: int,
        sizeZ: int,
        seed: int,
        mapArray: bytearray,
        spawnX: Optional[int] = None,
        spawnY: Optional[int] = None,
        spawnZ: Optional[int] = None,
        spawnYaw: Optional[int] = None,
        spawnPitch: Optional[int] = None,
        resetWorldSpawn: bool = False,
        generator: Optional[AbstractMapGenerator] = None,
        persistent: bool = False,
        fileIO: Optional[io.BufferedRandom] = None,
        canEdit: bool = True,
        maxPlayers: int = 250,
        logoutLocations: Optional[dict[str, tuple[int, int, int, int, int]]] = None
    ):
        # Y is the height
        self.worldManager: WorldManager = worldManager
        self.name: str = name
        self.generator: Optional[AbstractMapGenerator] = generator
        self.sizeX: int = sizeX
        self.sizeY: int = sizeY
        self.sizeZ: int = sizeZ
        self.seed: int = seed
        self.spawnX: Optional[int] = spawnX
        self.spawnY: Optional[int] = spawnY
        self.spawnZ: Optional[int] = spawnZ
        self.spawnYaw: Optional[int] = spawnYaw
        self.spawnPitch: Optional[int] = spawnPitch
        self.mapArray: bytearray = mapArray
        self.persistent: bool = persistent
        self.fileIO: Optional[io.BufferedRandom] = fileIO
        self.canEdit: bool = canEdit
        self.maxPlayers: int = maxPlayers
        self.logoutLocations: Optional[dict[str, tuple[int, int, int, int, int]]] = logoutLocations

        # Check if file IO was given if persistent
        if self.persistent:
            if self.fileIO is None:
                # Setting persistance to false because fileIO was not given
                self.persistent = False
                Logger.error(f"World Format {self.worldManager.worldFormat.NAME} Created Persistent World Without Providing FileIO! Please Report To Author! Setting World As Non-Persistent.", "world-load")
                Logger.askConfirmation()
            else:
                Logger.debug(f"Persistent World Has FileIO {self.fileIO}", "world-load")

        # Generate/Set Spawn Coords
        self.generateSpawnCoords(resetCoords=resetWorldSpawn)

        # Initialize WorldPlayerManager
        Logger.info("Initializing World Player Manager", module="init-world")
        self.playerManager = WorldPlayerManager(self)

    def generateSpawnCoords(
        self,
        resetCoords: bool = False
    ) -> None:
        # Generate spawn coords using an iterative system
        # Set spawnX
        if self.spawnX is None or resetCoords:
            # Generate SpawnX (Set to middle of map)
            self.spawnX = (self.sizeX // 2) * 32 + 51
            Logger.verbose(f"spawnX was not provided. Generated to {self.spawnX}", "world-load")

        # Set spawnZ
        if self.spawnZ is None or resetCoords:
            # Generate SpawnZ (Set to middle of map)
            self.spawnZ = (self.sizeZ // 2) * 32 + 51
            Logger.verbose(f"spawnZ was not provided. Generated to {self.spawnZ}", "world-load")

        # Set spawnY
        if self.spawnY is None or resetCoords:
            # Kinda hacky to get the block coords form the in-game coords
            self.spawnY = (self.getHighestBlock(round((self.spawnX - 51) / 32) + 1, round((self.spawnZ - 51) / 32) + 1) + 1) * 32 + 51
            Logger.verbose(f"spawnY was not provided. Generated to {self.spawnY}", "world-load")

        # Set spawnYaw
        if self.spawnYaw is None or resetCoords:
            # Generate SpawnYaw (0)
            self.spawnYaw = 0
            Logger.verbose(f"spawnYaw was not provided. Generated to {self.spawnYaw}", "world-load")

        # Set spawnPitch
        if self.spawnPitch is None or resetCoords:
            # Generate SpawnPitch (0)
            self.spawnPitch = 0
            Logger.verbose(f"spawnYaw was not provided. Generated to {self.spawnYaw}", "world-load")

        # Set spawn locations
        if self.logoutLocations is None:
            Logger.verbose("Logout Location was not provided. Generating Empty List.", "world-load")
            self.logoutLocations = dict()

    def canEditBlock(self, player: Player, block: AbstractBlock) -> bool:
        # Checking If User Can Set Blocks
        if not self.canEdit:  # Checking If World Is Read-Only
            if not player.opStatus:  # Checking If Player Is Not OP
                # Check If Air Exists (Prevents Crash if Stuff Wacky)
                if "Air" in Blocks._block_dict:
                    if block.ID == Blocks.Air.ID:
                        raise ClientError("You Do Not Have Permission To Break This Block")
                    else:
                        raise ClientError("You Do Not Have Permission To Place This Block")
                else:
                    raise ClientError("You Do Not Have Permission To Modify This Block")
        # else, everything is ay okay
        return True

    def getBlock(self, blockX: int, blockY: int, blockZ: int) -> AbstractBlock:
        # Gets Block Obj Of Requested Block
        Logger.verbose(f"Getting World Block {blockX}, {blockY}, {blockZ}", module="world")

        # Check If Block Is Out Of Range
        if blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ:
            raise BlockError(f"Requested Block Is Out Of Range ({blockX}, {blockY}, {blockZ})")
        return BlockManager.getBlockById(self.mapArray[blockX + self.sizeX * (blockZ + self.sizeZ * blockY)])

    async def setBlock(self, blockX: int, blockY: int, blockZ: int, blockId: int, player: Optional[Player] = None, sendPacket: bool = True, updateSelf: bool = False) -> bool:
        # Handles Block Updates In Server + Checks If Block Placement Is Allowed
        Logger.debug(f"Setting World Block {blockX}, {blockY}, {blockZ} to {blockId}", module="world")

        # Check If Block Is Out Of Range
        if blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ:
            raise BlockError(f"Block Placement Is Out Of Range ({blockX}, {blockY}, {blockZ})")

        # Setting Block in MapArray
        self.mapArray[blockX + self.sizeX * (blockZ + self.sizeZ * blockY)] = blockId

        if sendPacket:
            # Sending Block Update Update Packet To All Players
            await self.playerManager.sendWorldPacket(
                Packets.Response.SetBlock,
                blockX,
                blockY,
                blockZ,
                blockId,
                # not sending to self as that may cause some de-sync issues
                ignoreList=[player] if player is not None and not updateSelf else []
            )

        # Setblock Successful!
        return True

    def getHighestBlock(self, blockX: int, blockZ: int, start: Optional[int] = None) -> int:
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

    def saveMap(self) -> bool:
        if self.persistent and self.fileIO:
            Logger.info(f"Attempting To Save World {self.name}", module="world-save")
            self.worldManager.worldFormat.saveWorld(self, self.fileIO, self.worldManager)
            return True
        else:
            Logger.warn(f"World {self.name} Is Not Persistent! Not Saving.", module="world-save")
            return False

    def gzipMap(self, compressionLevel: int = -1, includeSizeHeader: bool = False) -> bytes:
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

    @staticmethod
    def _convert_arg(ctx: Server, argument: str) -> World:
        worldName = argument.lower()
        if worldName in ctx.worldManager.worlds:
            if world := ctx.worldManager.worlds.get(worldName):
                return world

        # Raise error if world not found
        raise ConverterError(f"World {worldName} Not Found!")
