from pathlib import Path
import struct
import io

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.log import Logger
from obsidian.worldformat import WorldFormat, AbstractWorldFormat
from obsidian.world import World, WorldManager
from obsidian.errors import WorldFormatError


@Module(
    "MCYetiWorld",
    description="MCYetiWorld World Format Support",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class MCYetiWorldModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    # Info on format version
    FORMAT_VERSION = 3

    @WorldFormat(
        "MCYetiWorld",
        description="MCYetiWorld World Format",
        version="v1.0.0"
    )
    class MCYetiWorldFormat(AbstractWorldFormat["MCYetiWorldModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                EXTENSIONS=["ylv"],
                METADATA_SUPPORT=False
            )

        def loadWorld(
            self,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager,
            persistent: bool = True
        ):
            # Print warning about MCYeti
            Logger.warn("MCYeti World Format Support is Experimental! Use At Your Own Risk!", module="mcyetiworld")

            # Start at the beginning of the file
            fileIO.seek(0)

            # Read Word Size
            Logger.debug("Reading World Size", module="mcyetiworld")
            sizeX, sizeY, sizeZ = struct.unpack("!hhh", fileIO.read(6))
            worldSize = sizeX * sizeY * sizeZ

            # Read spawn
            Logger.debug("Reading Spawn", module="mcyetiworld")
            spawnX, spawnY, spawnZ = struct.unpack("!hhh", fileIO.read(6))
            # Convert block coord to player coords
            spawnX = spawnX * 32 + 16
            spawnY = spawnY * 32 + 51
            spawnZ = spawnZ * 32 + 16

            # Read build permissions
            Logger.debug("Reading Build Permissions", module="mcyetiworld")
            buildPermLevel = struct.unpack("!B", fileIO.read(1))[0]

            # Check if buildPermLevel is 0. If not, assume that regular people dont have perms.
            if buildPermLevel == 0:
                canEdit = True
            else:
                Logger.warn(f"Build permission for this world is set to {buildPermLevel}.", module="mcyetiworld")
                Logger.warn("Obsidian does not support fine-grain permissions at this moment, so assuming read-only!", module="mcyetiworld")
                canEdit = False

            # Read visit permissions
            Logger.debug("Reading Visit Permissions", module="mcyetiworld")
            visitPermLevel = struct.unpack("!B", fileIO.read(1))[0]

            # Check if visit perms is False. If so, warn that obsidian does not support it.
            if visitPermLevel != 0:
                Logger.warn(f"Visit permission for this world is set to {visitPermLevel}.", module="mcyetiworld")
                Logger.warn("Obsidian does not support this info at this moment!", module="mcyetiworld")

            # Read format version
            Logger.debug("Reading Format Version", module="mcyetiworld")
            formatVersion = struct.unpack("!h", fileIO.read(2))[0]

            # Check format version
            if formatVersion != MCYetiWorldModule.FORMAT_VERSION:
                raise WorldFormatError(f"MCYetiWorld - Unsupported Format Version! Expected {MCYetiWorldModule.FORMAT_VERSION}, Got {formatVersion}")

            # Seak read to 512 and start reading raw data
            fileIO.seek(512)
            rawData = bytearray(fileIO.read(worldSize))

            # Using filename as world name
            name = Path(fileIO.name).stem

            # Create and Return New World Data
            return World(
                worldManager,  # Pass In World Manager
                name,
                sizeX, sizeY, sizeZ,
                rawData,
                spawnX=spawnX,
                spawnY=spawnY,
                spawnZ=spawnZ,
                worldFormat=self,
                persistent=persistent,  # Pass In Persistent Flag
                fileIO=fileIO,  # Pass In File Reader/Writer
                canEdit=canEdit
            )

        def saveWorld(
            self,
            world: World,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager
        ):
            # Print warning about MCYeti
            Logger.warn("MCYeti World Format Support is Experimental! Use At Your Own Risk!", module="mcyetiworld")
            Logger.warn("MCYeti also does not support many of the extended features that ObsidianWorld or ClassicWorld supports!")
            Logger.warn("Data will be lost saving to MCYet! You have been warned!", module="mcyetiworld")

            # Seek file head and initialize file
            fileIO.seek(0)
            fileIO.truncate(0)

            # Write world size
            Logger.debug("Writing World Size", module="mcyetiworld")
            fileIO.write(struct.pack("!hhh", world.sizeX, world.sizeY, world.sizeZ))

            # Convert spawn to block coordinates and write it
            Logger.debug("Writing Spawn", module="mcyetiworld")
            spawnX = world.spawnX // 32
            spawnY = world.spawnY // 32
            spawnZ = world.spawnZ // 32
            fileIO.write(struct.pack("!hhh", spawnX, spawnY, spawnZ))

            # Write build permissions
            Logger.debug("Writing Build Permissions", module="mcyetiworld")
            if world.canEdit:
                buildPermLevel = 0
            else:
                Logger.warn("Obsidian does not support fine-grain permissions at this moment!", module="mcyetiworld")
                Logger.warn("Defaulting to permission level 1!", module="mcyetiworld")
                buildPermLevel = 1
            fileIO.write(struct.pack("!B", buildPermLevel))

            # Write visit permissions. Obsidian does not support this, so default to 0
            Logger.debug("Writing Visit Permissions", module="mcyetiworld")
            fileIO.write(struct.pack("!B", 0))

            # Write format version
            Logger.debug("Writing Format Version", module="mcyetiworld")
            fileIO.write(struct.pack("!h", MCYetiWorldModule.FORMAT_VERSION))

            # Seek to 512 and begin writing world info
            fileIO.seek(512)
            fileIO.write(world.mapArray)

            # Done
            Logger.debug("Done Writing World", module="mcyetiworld")
