from obsidian.module import Module, AbstractModule, Dependency
from obsidian.log import Logger
from obsidian.world import WorldMetadata
from obsidian.worldformat import WorldFormat, WorldFormatManager, AbstractWorldFormat
from obsidian.mapgen import MapGenerators
from obsidian.world import World, WorldManager
from obsidian.errors import WorldFormatError

from pathlib import Path
import datetime
import time
import io
import uuid

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
class ClassicWorldModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @WorldFormat(
        "ClassicWorld",
        description="ClassicWorld World Format",
        version="v1.0.0"
    )
    class ClassicWorldFormat(AbstractWorldFormat["ClassicWorldModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                EXTENSIONS=["cw"],
                METADATA_SUPPORT=True
            )

        # Helper function to convert classicworld naming to obsidian naming
        # For example:
        # SomeSoftware -> someSoftware
        # TestThing1 -> testThing1
        # ABC -> ABC
        # CAPITALS -> CAPITALS
        @staticmethod
        def convertNameToObsidian(name: str) -> str:
            # If name is all caps, return it
            if name.isupper():
                return name

            # If the first character is uppercase, make it lowercase
            return name[0].lower() + name[1:]

        # Helper function to convert obsidian naming to classicworld naming
        # For example:
        # someSoftware -> SomeSoftware
        # testThing1 -> TestThing1
        # ABC -> ABC
        # CAPITALS -> CAPITALS
        @staticmethod
        def convertNameToCW(name: str) -> str:
            # If name is all caps, return it
            if name.isupper():
                return name

            # If the first character is lowercase, make it uppercase
            return name[0].upper() + name[1:]

        def loadWorld(
            self,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager,
            persistent: bool = True
        ):
            from obsidian.modules.nbtlib import NBTLib

            # Open, read, and parse NBT file
            Logger.debug("Reading ClassicWorld NBT File", module="classicworld")
            fileIO.seek(0)
            nbtFile = NBTLib.NBTFile(fileobj=fileIO)

            # Check ClassicWorld Version
            Logger.debug("Checking ClassicWorld Version", module="classicworld")
            version = nbtFile["FormatVersion"].value
            if version != 1:
                raise WorldFormatError(f"ClassicWorld version {version} is not supported!")

            # Get world information out of Metadata
            # Load critical values

            '''
            Keep track on whether or not this is a classicube world, because for some odd reason
            classicube worlds dont follow the classicworld spec!

            The main differences are:
            - "Name" tag is missing
            - "MapGenerator" compound is missing "Software" and "MapGeneratorName"
            - "MapGenerator" compound has extra "Seed" tag
            - "CreatedBy" compound is completely missing
            - "TimeCreated", "LastAccessed", and "LastModified" tags are missing as well
            - Spawn X, Y, Z should be player-position units, but are instead in block units

            It is the last difference that is the headache, as it means that the X Y Z values
            of the spawn can either be in player-position units or block units, and there is no
            way to tell which is which. Keeping track on whether or not this is a classicube world
            works around this, albeit ugly...
            '''

            # Get world name and determine if this is a classicube world
            Logger.debug("Parsing and Reading World Metadata", module="classicworld")
            if "Name" in nbtFile:
                name = nbtFile["Name"].value
                classicube = False
            else:
                Logger.warn("Name tag is missing. Using file name as world name!", module="classicworld")
                Logger.warn("Also using this information to assume world file is a classicube world!", module="classicworld")
                name = Path(fileIO.name).stem
                classicube = True

            # Get important map information
            sizeX = nbtFile["X"].value
            sizeY = nbtFile["Y"].value
            sizeZ = nbtFile["Z"].value

            # Parse spawn information
            if "Spawn" in nbtFile:
                spawnX = nbtFile["Spawn"]["X"].value
                spawnY = nbtFile["Spawn"]["Y"].value
                spawnZ = nbtFile["Spawn"]["Z"].value
                spawnYaw = nbtFile["Spawn"]["H"].value
                spawnPitch = nbtFile["Spawn"]["P"].value
            else:
                Logger.warn("Spawn compound is missing. Using default values!", module="classicworld")
                spawnX = None
                spawnY = None
                spawnZ = None
                spawnYaw = None
                spawnPitch = None

            # If the world is a classicube world, convert block coordinates to player-position coordinates
            if classicube and spawnX is not None and spawnY is not None and spawnZ is not None:
                Logger.warn("Applying Classicube Spawn Coordinates Fix! If your spawn is messed up, this is probably why!", module="classicworld")
                spawnX = spawnX * 32 + 16
                spawnY = spawnY * 32 + 51
                spawnZ = spawnZ * 32 + 16

            # Parse World Creation Information. This is optional field!
            if "CreatedBy" in nbtFile:
                # Parse Player Service. This is optional field!
                if "Service" in nbtFile["CreatedBy"]:
                    worldCreationService = nbtFile["CreatedBy"]["Service"].value
                else:
                    Logger.info("Service tag is missing from CreatedBy compound. Using default value!", module="classicworld")
                    worldCreationService = None
                # Parse Player Name. This is optional field!
                if "Username" in nbtFile["CreatedBy"]:
                    worldCreationPlayer = nbtFile["CreatedBy"]["Username"].value
                else:
                    Logger.info("Username tag is missing from CreatedBy compound. Using default value!", module="classicworld")
                    worldCreationPlayer = None
            else:
                Logger.info("CreatedBy compound is missing. Using default values!", module="classicworld")
                worldCreationService = None
                worldCreationPlayer = None

            # Parse Map Generator Information. This is optional field!
            if "MapGenerator" in nbtFile:
                # Parse Map Generator Software. This is optional field!
                if "Software" in nbtFile["MapGenerator"]:
                    mapGeneratorSoftware = nbtFile["MapGenerator"]["Software"].value
                else:
                    Logger.info("Software tag is missing from MapGenerator compound. Using default value!", module="classicworld")
                    mapGeneratorSoftware = None
                # Parse Map Generator Name. This is optional field!
                if "MapGeneratorName" in nbtFile["MapGenerator"]:
                    mapGeneratorName = nbtFile["MapGenerator"]["MapGeneratorName"].value
                else:
                    Logger.info("MapGeneratorName tag is missing from MapGenerator compound. Using default value!", module="classicworld")
                    mapGeneratorName = None
                # Parse World Seed. THIS IS ACTUALLY NOT PART OF THE SPEC, but some software adds it so we will parse it!
                if "Seed" in nbtFile["MapGenerator"]:
                    seed = nbtFile["MapGenerator"]["Seed"].value
                else:
                    Logger.info("Seed tag is missing from MapGenerator compound. Using default value!", module="classicworld")
                    seed = None
            else:
                Logger.info("MapGenerator compound is missing. Using default values!", module="classicworld")
                mapGeneratorSoftware = None
                mapGeneratorName = None
                seed = None

            # Parse UUID tag. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
            if "UUID" in nbtFile:
                worldUUID = uuid.UUID(bytes=bytes(nbtFile["UUID"].value))
            else:
                Logger.info("UUID tag is missing. Using default value!", module="classicworld")
                worldUUID = None

            # Parse TimeCreated tag. This is optional field!
            if "TimeCreated" in nbtFile:
                timeCreated = datetime.datetime.fromtimestamp(nbtFile["TimeCreated"].value)
            else:
                Logger.info("TimeCreated tag is missing. Using default value!", module="classicworld")
                timeCreated = None
            # Parse LastAccessed tag. This is optional field!
            if "LastAccessed" in nbtFile:
                lastAccessed = datetime.datetime.fromtimestamp(nbtFile["LastAccessed"].value)
            else:
                Logger.info("LastAccessed tag is missing. Using default value!", module="classicworld")
                lastAccessed = None
            # Parse LastModified tag. This is optional field!
            if "LastModified" in nbtFile:
                lastModified = datetime.datetime.fromtimestamp(nbtFile["LastModified"].value)
            else:
                Logger.info("LastModified tag is missing. Using default value!", module="classicworld")
                lastModified = None
            # Finally, add the missing values that obsidian uses
            canEdit = True  # ClassicWorld does not save this information, so we will assume it is editable

            # Try parsing world generator
            Logger.debug("Parsing World Generator", module="classicworld")
            if mapGeneratorSoftware == "Obsidian":
                if type(mapGeneratorName) is str and mapGeneratorName in MapGenerators:
                    generator = MapGenerators[mapGeneratorName]
                else:
                    Logger.info(f"Unknown World Generator {mapGeneratorName}.", module="classicworld")
                    generator = None  # Continue with no generator
            else:
                Logger.info(f"Unknown World Generator Software {mapGeneratorSoftware}.", module="classicworld")
                generator = None

            # Load Additional Metadata
            Logger.debug("Loading Additional Metadata", module="classicworld")
            additionalMetadata: dict[tuple[str, str], WorldMetadata] = {}
            unrecognizedMetadata: dict[tuple[str, str], NBTLib.TAG_Compound] = {}
            # Loop through each software and process its metadata
            for _metadataSoftware, softwareNbt in nbtFile["Metadata"].items():
                Logger.verbose(f"Loading Additional Metadata For Software: [{_metadataSoftware}]", module="classicworld")
                # For each software, loop through its sub-compounds and process them
                for _metadataName, metadataNbt in softwareNbt.items():
                    Logger.verbose(f"Loading Additional Metadata For: [{_metadataSoftware}]{_metadataName}", module="classicworld")
                    # Convert classicworld naming to obsidian naming
                    metadataSoftware = self.convertNameToObsidian(_metadataSoftware)
                    metadataName = self.convertNameToObsidian(_metadataName)
                    # Get the metadata reader
                    metadataReader = WorldFormatManager.getMetadataReader(self, metadataSoftware, metadataName)
                    if metadataReader is None:
                        Logger.warn(f"World Format Does Not Support Reading Metadata: [{metadataSoftware}]{metadataName}", module="classicworld")
                        unrecognizedMetadata[(metadataSoftware, metadataName)] = metadataNbt
                        continue
                    Logger.verbose(f"Metadata [{metadataSoftware}]{metadataName} uses reader [{metadataReader}]")

                    # Read metadata file
                    Logger.debug(f"Loading Additional Metadata: [{metadataSoftware}]{metadataName} - {metadataNbt}", module="classicworld")
                    additionalMetadata[(metadataSoftware, metadataName)] = metadataReader(metadataNbt)

            # Warn if there were unknown metadata types
            if len(unrecognizedMetadata) > 0:
                Logger.warn(f"There were {len(unrecognizedMetadata)} unrecognized metadata types: {list(unrecognizedMetadata.keys())}", module="classicworld")

            # Load Map Data
            Logger.debug("Loading Map Data", module="classicworld")
            rawData = nbtFile["BlockArray"].value

            # Sanity Check File Size
            Logger.debug("Sanity Checking Map Data", module="classicworld")
            if (sizeX * sizeY * sizeZ) != len(rawData):
                raise WorldFormatError(f"ClassicWorldFormat - Invalid Map Data! Expected: {sizeX * sizeY * sizeZ} Got: {len(rawData)}")

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
                timeCreated=timeCreated,
                lastModified=lastModified,
                lastAccessed=lastAccessed,
                additionalMetadata=additionalMetadata
            )

            # Save unrecognized metadata types to world
            setattr(world, "classicworldUnrecognizedMetadata", unrecognizedMetadata)

            # Return World
            return world

        def saveWorld(
            self,
            world: World,
            fileIO: io.BufferedRandom,
            worldManager: WorldManager
        ):
            from obsidian.modules.nbtlib import NBTLib

            # Begin creating NBT File
            Logger.debug("Creating NBT File", module="classicworld")
            nbtFile = NBTLib.NBTFile()
            nbtFile.name = "ClassicWorld"

            Logger.debug("Writing World Metadata", module="classicworld")

            # Write format version
            nbtFile.tags.append(NBTLib.TAG_Byte(name="FormatVersion", value=1))

            # Write world name and UUID
            nbtFile.tags.append(NBTLib.TAG_String(name="Name", value=world.name))
            nbtFile.tags.append(NBTLib.TAG_Byte_Array(name="UUID"))
            nbtFile["UUID"].value = world.worldUUID.bytes

            # Write world size
            nbtFile.tags.append(NBTLib.TAG_Short(name="X", value=world.sizeX))
            nbtFile.tags.append(NBTLib.TAG_Short(name="Y", value=world.sizeY))
            nbtFile.tags.append(NBTLib.TAG_Short(name="Z", value=world.sizeZ))

            # Generate and write CreatedBy compound
            createdBy = NBTLib.TAG_Compound(name="CreatedBy")
            createdBy.tags.append(NBTLib.TAG_String(name="Service", value=world.worldCreationService or "Unknown"))
            createdBy.tags.append(NBTLib.TAG_String(name="Username", value=world.worldCreationPlayer or "Unknown"))
            nbtFile.tags.append(createdBy)

            # Generate and write MapGenerator compound
            mapGenerator = NBTLib.TAG_Compound(name="MapGenerator")
            mapGenerator.tags.append(NBTLib.TAG_String(name="Software", value=world.mapGeneratorSoftware or "Unknown"))
            mapGenerator.tags.append(NBTLib.TAG_String(name="MapGeneratorName", value=world.mapGeneratorName or "Unknown"))
            mapGenerator.tags.append(NBTLib.TAG_Int(name="Seed", value=world.seed))
            nbtFile.tags.append(mapGenerator)

            # Write time information
            nbtFile.tags.append(NBTLib.TAG_Long(name="TimeCreated", value=int(time.mktime(world.timeCreated.timetuple()))))
            nbtFile.tags.append(NBTLib.TAG_Long(name="LastAccessed", value=int(time.mktime(world.lastAccessed.timetuple()))))
            nbtFile.tags.append(NBTLib.TAG_Long(name="LastModified", value=int(time.mktime(world.lastModified.timetuple()))))

            # Generate and write Spawn information
            spawn = NBTLib.TAG_Compound(name="Spawn")
            spawn.tags.append(NBTLib.TAG_Short(name="X", value=world.spawnX))
            spawn.tags.append(NBTLib.TAG_Short(name="Y", value=world.spawnY))
            spawn.tags.append(NBTLib.TAG_Short(name="Z", value=world.spawnZ))
            spawn.tags.append(NBTLib.TAG_Byte(name="H", value=world.spawnYaw))
            spawn.tags.append(NBTLib.TAG_Byte(name="P", value=world.spawnPitch))
            nbtFile.tags.append(spawn)

            # Write map data
            Logger.debug("Writing Map Data", module="classicworld")
            nbtFile.tags.append(NBTLib.TAG_Byte_Array(name="BlockArray"))
            nbtFile["BlockArray"].value = world.mapArray

            # Write Metadata
            Logger.debug("Writing Additional Metadata", module="classicworld")
            metadataNbt = NBTLib.TAG_Compound(name="Metadata")

            # Loop through metadata and write it to file
            for (metadataSoftware, metadataName), metadata in world.additionalMetadata.items():
                # Convert obsidian naming to classicworld naming
                _metadataSoftware = self.convertNameToCW(metadataSoftware)
                _metadataName = self.convertNameToCW(metadataName)
                Logger.verbose(f"Writing Additional Metadata For: [{metadataSoftware}]{metadataName}", module="classicworld")

                # Get metadata writer
                metadataWriter = WorldFormatManager.getMetadataWriter(self, metadataSoftware, metadataName)
                if metadataWriter is None:
                    Logger.warn(f"World Format Does Not Support Writing Metadata: [{metadataSoftware}]{metadataName}", module="classicworld")
                    continue
                Logger.verbose(f"Metadata [{metadataSoftware}]{metadataName} uses writer [{metadataWriter}]")

                # Check if software compound exists. If not, create it.
                if _metadataSoftware not in metadataNbt:
                    Logger.verbose(f"CW Metadata Software Compound Does Not Exist. Creating It: {_metadataSoftware}", module="classicworld")
                    metadataNbt[_metadataSoftware] = NBTLib.TAG_Compound(name=_metadataSoftware)
                metadataSoftwareNbt = metadataNbt[_metadataSoftware]

                # Write metadata
                Logger.debug(f"Generating Additional Metadata: [{metadataSoftware}]{metadataName} - {metadata}", module="classicworld")
                metadataSoftwareNbt[_metadataName] = metadataWriter(metadata)

            # If world has any unrecognized metadata, write it to file
            if hasattr(world, "classicworldUnrecognizedMetadata"):
                unrecognizedMetadata: dict[tuple[str, str], NBTLib.TAG_Compound] = getattr(world, "classicworldUnrecognizedMetadata")
                Logger.debug(f"Writing {len(unrecognizedMetadata)} unrecognized metadata entries: {unrecognizedMetadata}", module="classicworld")
                for (metadataSoftware, metadataName), unrecognizedNbt in unrecognizedMetadata.items():
                    # Convert obsidian naming to classicworld naming
                    _metadataSoftware = self.convertNameToCW(metadataSoftware)
                    _metadataName = self.convertNameToCW(metadataName)
                    Logger.verbose(f"Writing Unrecognized Metadata For: [{metadataSoftware}]{metadataName}", module="classicworld")

                    # Check if software compound exists. If not, create it.
                    if _metadataSoftware not in metadataNbt:
                        Logger.verbose(f"CW Metadata Software Compound Does Not Exist. Creating It: {_metadataSoftware}", module="classicworld")
                        metadataNbt[_metadataSoftware] = NBTLib.TAG_Compound(name=_metadataSoftware)
                    metadataSoftwareNbt = metadataNbt[_metadataSoftware]

                    # Write unknown metadata
                    Logger.debug(f"Writing Unrecognized Metadata: [{metadataSoftware}]{metadataName} - {unrecognizedNbt}", module="classicworld")
                    metadataSoftwareNbt[_metadataName] = unrecognizedNbt

            # Write metadata to file
            nbtFile.tags.append(metadataNbt)

            # Write NBT File
            fileIO.truncate(0)
            fileIO.seek(0)
            nbtFile.write_file(fileobj=fileIO)
