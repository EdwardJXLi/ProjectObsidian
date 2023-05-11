from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server

from typing import Optional
from pathlib import Path
from threading import Lock
import io
import gzip
import uuid
import struct
import random
import datetime

from obsidian.log import Logger
from obsidian.player import WorldPlayerManager, Player
from obsidian.blocks import BlockManager, Blocks, AbstractBlock
from obsidian.worldformat import WorldFormats, AbstractWorldFormat
from obsidian.mapgen import (
    MapGenerators,
    AbstractMapGenerator,
    MapGeneratorStatus
)
from obsidian.packet import Packets
from obsidian.constants import SERVER_PATH
from obsidian.types import formatName
from obsidian.errors import (
    FatalError,
    MapGenerationError,
    MapSaveError,
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
        self.persistent: bool = self.server.config.persistentWorlds
        self.lock: Lock = Lock()
        # Defined Later In Init
        # self.worldFormat: AbstractWorldFormat

        # Get worldFormat Using Given World Format Key
        # Loop Through All World Formats
        for worldFormat in WorldFormats._formatDict.values():
            # Check If key Matches With Config Key List
            if formatName(self.server.config.defaultSaveFormat) in worldFormat.KEYS:
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
        spawnYaw: Optional[int] = None,
        spawnPitch: Optional[int] = None,
        worldCreationPlayer: Optional[str] = None
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

        # Generate the world map
        worldMap = self.generateMap(
            sizeX,
            sizeY,
            sizeZ,
            seed,
            generator
        )

        # Create World
        self.worlds[worldName] = World(
            self,  # Pass In World Manager
            worldName,  # Pass In World Name
            sizeX, sizeY, sizeZ,  # Passing World X, Y, Z
            seed,  # Passing In World Seed
            worldMap,  # Passing In World Map
            # Spawn Information
            spawnX=spawnX,
            spawnY=spawnY,
            spawnZ=spawnZ,
            spawnYaw=spawnYaw,
            spawnPitch=spawnPitch,
            # World Config Info
            generator=generator,  # Pass In World Generator
            persistent=persistent,  # Pass In Persistent Flag
            fileIO=fileIO,  # Pass In FileIO Object (if persistent set)
            # Misc World Info
            worldUUID=uuid.uuid4(),  # Generate World UUID
            worldCreationService="Obsidian",  # Set World Creation Service
            worldCreationPlayer=worldCreationPlayer or "ObsidianPlayer",  # Set World Creation Player
            timeCreated=datetime.datetime.now(),  # Set World Creation Time
            lastModified=datetime.datetime.now(),  # Set World Last Modified Time
            lastAccessed=datetime.datetime.now()  # Set World Last Accessed Time
        )

        # Saving World
        Logger.info(f"Saving World {worldName}", module="world-create")
        self.worlds[worldName].saveMap()
        return self.worlds[worldName]

    def generateMap(
        self,
        sizeX: int,
        sizeY: int,
        sizeZ: int,
        seed: int,
        generator: AbstractMapGenerator,
        *args,
        generationStatus: Optional[MapGeneratorStatus] = None,
        **kwargs
    ) -> bytearray:
        Logger.debug(f"Generating World With Size {sizeX}, {sizeY}, {sizeX} With Generator {generator.NAME}", module="init-world")
        # Create a generation status object to pass around
        if not generationStatus:
            generationStatus = MapGeneratorStatus(generator)

        # Call Generate Map Function From Generator
        try:
            # Generate Map
            generatedMap = generator.generateMap(sizeX, sizeY, sizeZ, seed, generationStatus, *args, **kwargs)

            # Verify Map Data Size
            expectedSize = sizeX * sizeY * sizeZ
            if len(generatedMap) != expectedSize:
                raise MapGenerationError(f"Expected Map Size {expectedSize} While Generating World. Got {len(generatedMap)}")
        except Exception as e:
            # Announce to the status object that an error occurred, then raise same error
            generationStatus.setError(e)
            raise e

        # Set the final map for generationStatus
        # Used if the map is needed anywhere else outside current thread
        generationStatus.setFinalMap(generatedMap)

        # Check if generationStatus was even finalized
        if not generationStatus.done:
            Logger.warn(f"Map Generator {generator.NAME} never set generationStatus.done() to True!", module="init-world")
            # Announce to the status object that generation is done
            generationStatus.setDone()

        Logger.debug(f"Generated Map With Final Size Of {len(generatedMap)}", module="init-world")

        # Return Generated Map bytearray
        return generatedMap

    def loadWorlds(self, reload: bool = False) -> bool:
        Logger.debug("Starting Attempt to Load All Worlds", module="world-load")
        if self.server.config.worldSaveLocation is not None:

            # Open Lock
            with self.lock:
                Logger.debug(f"Beginning To Scan Through {self.server.config.worldSaveLocation} Dir", module="world-load")
                # Loop Through All Files Given In World Folder
                for saveFile in Path(SERVER_PATH, self.server.config.worldSaveLocation).iterdir():
                    # Get Pure File Name (No Extensions)
                    saveName = saveFile.stem
                    Logger.verbose(f"Checking Extension and Status of World File {saveFile}", module="world-load")
                    # Check If File Type Matches With The Extensions Provided By worldFormat
                    if saveFile.suffix[1:] not in self.worldFormat.EXTENSIONS:  # doing [1:] to remove the "."
                        Logger.debug(f"Ignoring World File {saveFile}. File Extension Not Known!", module="world-load")
                    # Also Check If World Is Ignored
                    elif saveName in self.ignorelist:
                        Logger.info(f"Ignoring World File {saveFile}. World Name Is On Ignore List!", module="world-load")

                    # Also Check If World Name Is Already Loaded (Same File Names with Different Extensions)
                    elif saveName in self.worlds.keys():
                        if not reload:
                            Logger.warn(f"Ignoring World File {saveFile}. World With Similar Name Has Already Been Registered!", module="world-load")
                            Logger.warn(f"World File {self.worlds[saveName].name} Conflicts With World File {saveFile}!", module="world-load")
                            Logger.askConfirmation()
                        else:
                            Logger.warn(f"Ignoring World File {saveFile}. World Already Loaded!", module="world-load")
                    else:
                        Logger.debug(f"Detected World File {saveFile}. Attempting To Load World", module="world-load")

                        # Checking if a backup world was made/
                        # If so, that indicates an unclean shutdown
                        backupFile = saveFile.with_suffix(saveFile.suffix + ".bak")
                        if backupFile.exists():
                            Logger.warn(f"Detected Backup File {backupFile}. This means that the world was not cleanly saved!", module="world-load")
                            Logger.askConfirmation("Do you want to attempt to recover the world from the backup?")
                            Logger.warn("Attempting To Recover World From Backup", module="world-load")
                            # Attempting to recover world from backup
                            try:
                                Logger.info(f"Recovering World {saveName} From Backup", module="world-load")
                                # Replace the original file with the backup
                                with open(saveFile, "wb") as fileIO:
                                    fileIO.write(backupFile.read_bytes())
                                # Remove backup file
                                backupFile.unlink()
                            except Exception as e:
                                Logger.error(f"Error While Recovering World {saveName} From Backup - {type(e).__name__}: {e}", module="world-load")
                                Logger.askConfirmation("Skipping world load. Keeping backup intact.")

                        # (Attempt) To Load Up World
                        try:
                            Logger.info(f"Loading World {saveName}", module="world-load")
                            fileIO = open(saveFile, "rb+")
                            self.worlds[saveName] = self.worldFormat.loadWorld(fileIO, self, persistent=self.persistent)
                        except Exception as e:
                            Logger.error(f"Error While Loading World {saveFile} - {type(e).__name__}: {e}", module="world-load")
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
            Logger.warn("World Manager does not have a world save location!", module="world-load")
            # Create Non-Persistent Temporary World
            defaultWorldName = self.server.config.defaultWorld
            defaultGenerator = MapGenerators[self.server.config.defaultGenerator]
            Logger.warn(f"Creating temporary world {defaultWorldName}", module="world-load")
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
        # Keep track on whether error occurs during save.
        errorDuringSave = False

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
                        errorDuringSave = True
                else:
                    Logger.warn(f"World {worldName} Is Non Persistent! Skipping World Save!", module="world-save")
        else:
            Logger.warn("World Manager Is Non Persistent! Skipping World Save!", module="world-save")

        # If error occurred during save, raise an error indicating the world save failed
        if errorDuringSave:
            raise MapSaveError("Error Occurred During World Save! Check Logs For More Info!")

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
            SERVER_PATH,
            savePath,
            worldName + "." + worldFormat.EXTENSIONS[0]  # Gets the first value in the valid extensions list
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
        logoutLocations: Optional[dict[str, tuple[int, int, int, int, int]]] = None,
        worldUUID: Optional[uuid.UUID] = None,
        worldCreationService: Optional[str] = None,
        worldCreationPlayer: Optional[str] = None,
        timeCreated: Optional[datetime.datetime] = None,
        lastModified: Optional[datetime.datetime] = None,
        lastAccessed: Optional[datetime.datetime] = None
    ):
        # Y is the height
        self.worldManager: WorldManager = worldManager
        self.name: str = name
        self.generator: Optional[AbstractMapGenerator] = generator
        self.sizeX: int = sizeX
        self.sizeY: int = sizeY
        self.sizeZ: int = sizeZ
        self.seed: int = seed

        # Set rest of input arguments
        self.mapArray: bytearray = mapArray
        self.persistent: bool = persistent
        self.fileIO: Optional[io.BufferedRandom] = fileIO
        self.canEdit: bool = canEdit
        self.maxPlayers: int = maxPlayers

        # Generate/Set Spawn Coords
        self.generateSpawnCoords(
            resetCoords=resetWorldSpawn,
            spawnX=spawnX,
            spawnY=spawnY,
            spawnZ=spawnZ,
            spawnYaw=spawnYaw,
            spawnPitch=spawnPitch,
            logoutLocations=logoutLocations)

        # Set spawn locations
        if logoutLocations is None:
            Logger.verbose("Logout Location was not provided. Generating Empty List.", "world-load")
            self.logoutLocations = dict()
        else:
            self.logoutLocations = logoutLocations

        # For the extra info that Obsidian does not use, generate with default ones
        self.worldUUID: uuid.UUID = worldUUID or uuid.uuid4()
        self.worldCreationService: str = worldCreationService or "Obsidian"
        self.worldCreationPlayer: str = worldCreationPlayer or "ObsidianPlayer"
        self.timeCreated: datetime.datetime = timeCreated or datetime.datetime.now()
        self.lastModified: datetime.datetime = lastModified or datetime.datetime.now()
        self.lastAccessed: datetime.datetime = lastAccessed or datetime.datetime.now()

        # Check if file IO was given if persistent
        if self.persistent:
            if self.fileIO is None:
                # Setting persistance to false because fileIO was not given
                self.persistent = False
                Logger.error(f"World Format {self.worldManager.worldFormat.NAME} Created Persistent World Without Providing FileIO! Please Report To Author! Setting World As Non-Persistent.", "world-load")
                Logger.askConfirmation()
            else:
                Logger.debug(f"Persistent World Has FileIO {self.fileIO}", "world-load")

        # Initialize WorldPlayerManager
        Logger.info("Initializing World Player Manager", module="init-world")
        self.playerManager = WorldPlayerManager(self)

    def generateSpawnCoords(
        self,
        resetCoords: bool = False,
        spawnX: Optional[int] = None,
        spawnY: Optional[int] = None,
        spawnZ: Optional[int] = None,
        spawnYaw: Optional[int] = None,
        spawnPitch: Optional[int] = None,
        logoutLocations: Optional[dict[str, tuple[int, int, int, int, int]]] = None
    ) -> None:
        # Generate spawn coords using an iterative system
        # Set spawnX
        if spawnX is None or resetCoords:
            # Generate SpawnX (Set to middle of map)
            self.spawnX = (self.sizeX // 2) * 32 + 16
            Logger.verbose(f"spawnX was not provided. Generated to {self.spawnX}", "world-load")
        else:
            self.spawnX = spawnX

        # Set spawnZ
        if spawnZ is None or resetCoords:
            # Generate SpawnZ (Set to middle of map)
            self.spawnZ = (self.sizeZ // 2) * 32 + 16
            Logger.verbose(f"spawnZ was not provided. Generated to {self.spawnZ}", "world-load")
        else:
            self.spawnZ = spawnZ

        # Set spawnY
        if spawnY is None or resetCoords:
            # Kinda hacky to get the block coords form the in-game coords
            self.spawnY = (self.getHighestBlock(round((self.spawnX - 51) / 32) + 1, round((self.spawnZ - 51) / 32) + 1) + 1) * 32 + 51
            Logger.verbose(f"spawnY was not provided. Generated to {self.spawnY}", "world-load")
        else:
            self.spawnY = spawnY

        # Set spawnYaw
        if spawnYaw is None or resetCoords:
            # Generate SpawnYaw (0)
            self.spawnYaw = 0
            Logger.verbose(f"spawnYaw was not provided. Generated to {self.spawnYaw}", "world-load")
        else:
            self.spawnYaw = spawnYaw

        # Set spawnPitch
        if spawnPitch is None or resetCoords:
            # Generate SpawnPitch (0)
            self.spawnPitch = 0
            Logger.verbose(f"spawnYaw was not provided. Generated to {self.spawnYaw}", "world-load")
        else:
            self.spawnPitch = spawnPitch

    def canEditBlock(self, player: Player, block: AbstractBlock) -> bool:
        # Checking If User Can Set Blocks
        if not self.canEdit:  # Checking If World Is Read-Only
            if not player.opStatus:  # Checking If Player Is Not OP
                # Check If Air Exists (Prevents Crash if Stuff Wacky)
                if "Air" in Blocks._blockDict:
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

        # SetBlock Successful!
        return True

    def getHighestBlock(self, blockX: int, blockZ: int, start: Optional[int] = None) -> int:
        # Returns the highest block
        # Set and Verify Scan Start Value
        if start is None:
            scanY = self.sizeY - 1
        else:
            if start > self.sizeY:
                Logger.warn(f"Trying To Get Highest Block From Location Greater Than Map Size (MapHeight: {self.sizeY}, Given: {start})")
                scanY = self.sizeY - 1
            else:
                scanY = start

        # Scan Downwards To Get Highest Block
        while self.getBlock(blockX, scanY, blockZ) is Blocks.Air:
            if scanY == 0:
                break
            # Scan Downwards
            scanY -= 1

        return scanY

    def saveMap(self) -> bool:
        # If World Is Not Persistent, Do Not Save and raise exception
        if self.persistent is False:
            raise MapSaveError("Cannot Save Non-Persistent World")

        with self.worldManager.lock:
            if self.persistent and self.fileIO:
                Logger.info(f"Attempting To Save World {self.name}", module="world-save")
                savePath = Path(self.fileIO.name)
                backupPath = savePath.with_suffix(savePath.suffix + ".bak")

                # Make a backup of the current world
                if self.worldManager.server.config.backupBeforeSave:
                    Logger.debug(f"Creating Temporary Backup Of World {self.name}", module="world-save")

                    # Check If Backup File Already Exists
                    if backupPath.exists():
                        Logger.warn(f"Backup File Already Exists For World {self.name}.", module="world-save")
                        Logger.warn("This usually means there was an unclean previous save.", module="world-save")

                    # Create and Save Backup File
                    with open(backupPath, "wb+") as backupFile:
                        self.worldManager.worldFormat.saveWorld(self, backupFile, self.worldManager)

                # Save the world to file
                self.worldManager.worldFormat.saveWorld(self, self.fileIO, self.worldManager)

                # Check is save was successful
                if self.worldManager.server.config.verifyMapAfterSave:
                    self.verifyWorldSave()

                    Logger.info("World Save Verification Successful!", module="world-save")

                # If a backup file was deleted, remove it.
                if self.worldManager.server.config.backupBeforeSave:
                    Logger.debug(f"Removing backup file for world {self.name}", module="world-save")
                    backupPath.unlink()

                return True
            else:
                Logger.warn(f"World {self.name} Is Not Persistent! Not Saving.", module="world-save")
                return False

    def verifyWorldSave(self) -> None:
        Logger.info(f"Verifying World Save For World {self.name}", module="world-save")

        # Check if fileIO is still defined
        if not self.fileIO:
            raise MapSaveError("World Save Verification Failed! FileIO Is Not Defined! This Should Not Happen!")

        # Try loading back the world file and check if any errors occurs.
        try:
            self.worldManager.worldFormat.loadWorld(self.fileIO, self.worldManager)

            # TODO: we could do more sanity checks, like map content,
            # but lets not do that for now as there is a lot of concurrency issues with that...
        except Exception as e:
            Logger.error(f"World Save Verification Failed! Error While Verifying World Save For World {self.name}!", module="world-save-verify")
            raise MapSaveError(e)

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
    def _convertArgument(ctx: Server, argument: str) -> World:
        worldName = argument.lower()
        if worldName in ctx.worldManager.worlds:
            if world := ctx.worldManager.worlds.get(worldName):
                return world

        # Raise error if world not found
        raise ConverterError(f"World {worldName} Not Found!")
