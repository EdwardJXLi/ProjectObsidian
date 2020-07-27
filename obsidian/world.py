from __future__ import annotations
from obsidian.blocks import BlockManager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server

from typing import List, Optional
import io
import gzip
import struct

from obsidian.log import Logger
from obsidian.player import WorldPlayerManager, Player
from obsidian.mapgen import MapGenerators, AbstractMapGenerator
from obsidian.constants import ClientError, MapGenerationError, BlockError


class WorldManager:
    def __init__(self, server: Server, blacklist: List[str] = []):
        self.server = server
        self.worlds = dict()
        self.blacklist = blacklist
        self.persistant = True

        # If World Location Was Not Given, Disable Persistance
        # (Don't Save / Load)
        if self.server.config.worldSaveLocation is None:
            Logger.warn("World Save Location Was Not Defined. Creating Non-Persistant World!!!", module="init-world")
            self.persistant = False

    def generateMap(self, sizeX, sizeY, sizeZ, generator: AbstractMapGenerator, *args, **kwargs):
        Logger.debug(f"Generating World With Size {sizeX}, {sizeY}, {sizeX} With Generator {generator.NAME}", module="init-world")
        # Call Generate Map Function From Generator
        generatedMap = generator.generateMap(sizeX, sizeY, sizeZ, *args, **kwargs)

        # Verify Map Data Size
        expectedSize = sizeX * sizeY * sizeZ
        if len(generatedMap) != expectedSize:
            raise MapGenerationError(f"Expected Map Size {expectedSize} While Generating World. Got {len(generatedMap)}")

        # Return Generated Map Bytesarray
        return generatedMap

    def loadWorlds(self):
        if self.persistant:
            # TODO: World File Loading
            raise NotImplementedError("Persistant World Loading Is Not Implemented")
        else:
            defaultWorld = self.server.config.defaultWorld
            Logger.debug(f"Creating Temporary World {defaultWorld}", module="init-world")
            self.worlds[defaultWorld] = World(
                self,  # Pass In World Manager
                MapGenerators.Flat,  # Pass In World Generator
                defaultWorld,  # Pass In World Name
                32, 32, 32,  # Passing World X, Y, Z
                self.generateMap(32, 32, 32, MapGenerators.Flat, grassHeight=16),  # Generating Map Data
                persistant=self.persistant,  # Pass In Persistant Flag
                # Spawn Information
                spawnX=8 * 32 + 51,
                spawnY=17 * 32 + 51,
                spawnZ=8 * 32 + 51
            )


class World:
    def __init__(
        self,
        worldManager: WorldManager,
        generator: AbstractMapGenerator,
        name: str,
        sizeX: int,
        sizeY: int,
        sizeZ: int,
        mapArray: bytearray,
        persistant: bool = True,
        canEdit: bool = True,
        spawnX: int = 0,
        spawnY: int = 0,
        spawnZ: int = 0,
        spawnYaw: int = 0,
        spawnPitch: int = 0,
        maxPlayers: int = 250
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

        # Initialize WorldPlayerManager
        Logger.info("Initializing World Player Manager", module="init-world")
        self.playerManager = WorldPlayerManager(self)

    def getBlock(self, blockX, blockY, blockZ):
        # Gets Block Obj Of Requested Block
        Logger.verbose(f"Getting World Block {blockX}, {blockY}, {blockZ}")

        # Check If Block Is Out Of Range
        if blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ:
            raise BlockError("Requested Block Is Out Of Range")
        return BlockManager.getBlockById(self.mapArray[blockX + self.sizeX * (blockZ + self.sizeZ * blockY)])

    def setBlock(self, blockX, blockY, blockZ, blockType, player: Optional[Player] = None):
        # Handles Block Updates In Server + Checks If Block Placement Is Allowed
        Logger.debug(f"Setting World Block {blockX}, {blockY}, {blockZ} to {blockType.ID}")

        # Checking If User Can Set Blocks
        if player is not None:  # Checking If User Was Passed
            if not self.canEdit:  # Checking If World Is Read-Only
                if not player.opStatus:  # Checking If Player Is Not OP
                    raise ClientError("You Do Not Have Permission To Edit This Block")

        # Check If Block Is Out Of Range
        if blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ:
            raise BlockError("Block Placement Is Out Of Range")
        self.mapArray[blockX + self.sizeX * (blockZ + self.sizeZ * blockY)] = blockType.ID

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
