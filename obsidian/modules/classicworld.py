from obsidian.module import Module, AbstractModule, Dependency
from obsidian.log import Logger
from obsidian.worldformat import WorldFormat, AbstractWorldFormat
from obsidian.mapgen import MapGenerators
from obsidian.world import World, WorldManager
from obsidian.errors import WorldFormatError

import io
import uuid
import random
import datetime

'''
ClassicWorld World Format Support as documented at https://wiki.vg/ClassicWorld_file_format
'''


@Module(
    "ClassicWorld",
    description="ClassicWorld World Format Support",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core"), Dependency("nbtlib")]
)
class ClassicWorld(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @WorldFormat(
        "ClassicWorld",
        description="ClassicWorld World Format",
        version="v1.0.0"
    )
    class ClassicWorldFormat(AbstractWorldFormat["ClassicWorld"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                EXTENSIONS=["cw"]
            )

        def loadWorld(
            self,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager,
            persistent: bool = True
        ):
            from obsidian.modules.nbtlib import NBTLib

            Logger.warn("Loading from ClassicWorld is still WIP! Expect bugs!", module="ClassicWorld")

            # Open, read, and parse NBT file
            Logger.debug("Reading ClassicWorld NBT File", module="ClassicWorld")
            fileIO.seek(0)
            nbtFile = NBTLib.NBTFile(fileobj=fileIO)

            print(nbtFile)

            # Check ClassicWorld Version
            version = nbtFile["FormatVersion"].value
            if version != 1:
                raise WorldFormatError(f"ClassicWorld version {version} is not supported!")

            # Get world information out of Metadata
            # Load critical values
            if "Name" in nbtFile:
                name = nbtFile["Name"].value
            else:
                name = "Unknown"
            sizeX = nbtFile["X"].value
            sizeY = nbtFile["Y"].value
            sizeZ = nbtFile["Z"].value
            # Optional Values
            spawnX = nbtFile["Spawn"]["X"].value * 32 + 16
            spawnY = nbtFile["Spawn"]["Y"].value * 32 + 51
            spawnZ = nbtFile["Spawn"]["Z"].value * 32 + 16
            spawnYaw = nbtFile["Spawn"]["H"].value
            spawnPitch = nbtFile["Spawn"]["P"].value
            print(spawnX, spawnY, spawnZ, spawnYaw, spawnPitch)
            # Misc Values
            seed = random.randint(0, 2**64)  # TODO
            canEdit = True  # TODO
            worldUUID = uuid.UUID(bytes=bytes(nbtFile["UUID"].value))  # TODO
            worldCreationService = "Unknown"  # TODO
            worldCreationGenerator = "Unknown"  # TODO
            worldCreationPlayer = "Unknown"  # TODO
            timeCreated = datetime.datetime.fromtimestamp(0)  # TODO
            lastModified = datetime.datetime.fromtimestamp(0)  # TODO
            lastAccessed = datetime.datetime.fromtimestamp(0)  # TODO

            # Try parsing world generator
            if worldCreationGenerator in MapGenerators:
                generator = MapGenerators[worldCreationGenerator]
            else:
                Logger.warn("ClassicWorldFormat - Unknown World Generator.")
                generator = None  # Continue with no generator

            # Load Map Data
            Logger.debug("Loading Map Data", module="obsidian-map")
            rawData = nbtFile["BlockArray"].value

            # Sanity Check File Size
            if (sizeX * sizeY * sizeZ) != len(rawData):
                raise WorldFormatError(f"ObsidianWorldFormat - Invalid Map Data! Expected: {sizeX * sizeY * sizeZ} Got: {len(rawData)}")

            # Create World Data
            return World(
                worldManager,  # Pass In World Manager
                name,
                sizeX, sizeY, sizeZ,
                seed,
                rawData,
                spawnX=spawnX,
                spawnY=spawnY,
                spawnZ=spawnZ,
                spawnYaw=spawnYaw,
                spawnPitch=spawnPitch,
                generator=generator,
                persistent=persistent,  # Pass In Persistent Flag
                fileIO=fileIO,  # Pass In File Reader/Writer
                canEdit=canEdit,
                worldUUID=worldUUID,
                worldCreationService=worldCreationService,
                worldCreationPlayer=worldCreationPlayer,
                timeCreated=timeCreated,
                lastModified=lastModified,
                lastAccessed=lastAccessed,
                additionalMetadata=None
            )

        def saveWorld(
            self,
            world: World,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager
        ):
            raise NotImplementedError("ClassicWorldFormat.saveWorld() is not implemented!")
