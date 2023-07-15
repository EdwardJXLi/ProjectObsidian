from obsidian.module import Module, AbstractModule, Dependency
from obsidian.log import Logger
from obsidian.worldformat import WorldFormat, AbstractWorldFormat
from obsidian.mapgen import MapGenerators
from obsidian.world import World, WorldManager
from obsidian.errors import WorldFormatError

from pathlib import Path
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

            # Check ClassicWorld Version
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
            if "Name" in nbtFile:
                name = nbtFile["Name"].value
                classicube = False
            else:
                Logger.warn("ClassicWorldFormat - Name tag is missing. Using file name as world name!", module="ClassicWorld")
                Logger.warn("ClassicWorldFormat - Also using this information to assume world file is a classicube world!", module="ClassicWorld")
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
                Logger.warn("ClassicWorldFormat - Spawn compound is missing. Using default values!", module="ClassicWorld")
                spawnX = None
                spawnY = None
                spawnZ = None
                spawnYaw = None
                spawnPitch = None

            # If the world is a classicube world, convert block coordinates to player-position coordinates
            if classicube and spawnX is not None and spawnY is not None and spawnZ is not None:
                spawnX = spawnX * 32 + 16
                spawnY = spawnY * 32 + 51
                spawnZ = spawnZ * 32 + 16

            # Parse World Creation Information
            if "CreatedBy" in nbtFile:
                # Parse Player Service. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
                if "Service" in nbtFile["CreatedBy"]:
                    worldCreationService = nbtFile["CreatedBy"]["Service"].value
                else:
                    Logger.warn("ClassicWorldFormat - Service tag is missing from CreatedBy compound. Using default value!", module="ClassicWorld")
                    worldCreationService = None
                # Parse Player Name. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
                if "Username" in nbtFile["CreatedBy"]:
                    worldCreationPlayer = nbtFile["CreatedBy"]["Username"].value
                else:
                    Logger.warn("ClassicWorldFormat - Username tag is missing from CreatedBy compound. Using default value!", module="ClassicWorld")
                    worldCreationPlayer = None
            else:
                Logger.warn("ClassicWorldFormat - CreatedBy compound is missing. Using default values!", module="ClassicWorld")
                worldCreationService = None
                worldCreationPlayer = None

            # Parse Map Generator Information
            if "MapGenerator" in nbtFile:
                # Parse Map Generator Software. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
                if "Software" in nbtFile["MapGenerator"]:
                    mapGeneratorSoftware = nbtFile["MapGenerator"]["Software"].value
                else:
                    Logger.warn("ClassicWorldFormat - Software tag is missing from MapGenerator compound. Using default value!", module="ClassicWorld")
                    mapGeneratorSoftware = None
                # Parse Map Generator Name. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
                if "MapGeneratorName" in nbtFile["MapGenerator"]:
                    mapGeneratorName = nbtFile["MapGenerator"]["MapGeneratorName"].value
                else:
                    Logger.warn("ClassicWorldFormat - MapGeneratorName tag is missing from MapGenerator compound. Using default value!", module="ClassicWorld")
                    mapGeneratorName = None
                # Parse World Seed. THIS IS ACTUALLY NOT PART OF THE SPEC, but some software adds it so we will parse it!
                if "Seed" in nbtFile["MapGenerator"]:
                    seed = nbtFile["MapGenerator"]["Seed"].value
                else:
                    Logger.warn("ClassicWorldFormat - Seed tag is missing from MapGenerator compound. Using default value!", module="ClassicWorld")
                    seed = None
            else:
                Logger.warn("ClassicWorldFormat - MapGenerator compound is missing. Using default values!", module="ClassicWorld")
                mapGeneratorSoftware = None
                mapGeneratorName = None
                seed = None

            # Parse UUID tag. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
            if "UUID" in nbtFile:
                worldUUID = uuid.UUID(bytes=bytes(nbtFile["UUID"].value))
            else:
                Logger.warn("ClassicWorldFormat - UUID tag is missing. Using default value!", module="ClassicWorld")
                worldUUID = None

            # Parse TimeCreated tag. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
            if "TimeCreated" in nbtFile:
                timeCreated = nbtFile["TimeCreated"].value
            else:
                Logger.warn("ClassicWorldFormat - TimeCreated tag is missing. Using default value!", module="ClassicWorld")
                timeCreated = None
            # Parse LastAccessed tag. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
            if "LastAccessed" in nbtFile:
                lastAccessed = nbtFile["LastAccessed"].value
            else:
                Logger.warn("ClassicWorldFormat - LastAccessed tag is missing. Using default value!", module="ClassicWorld")
                lastAccessed = None
            # Parse LastModified tag. This is a "Mandatory" spec as per the wiki, but some software leaves it blank
            if "LastModified" in nbtFile:
                lastModified = nbtFile["LastModified"].value
            else:
                Logger.warn("ClassicWorldFormat - LastModified tag is missing. Using default value!", module="ClassicWorld")
                lastModified = None
            # Finally, add the missing values that obsidian uses
            canEdit = True  # ClassicWorld does not save this information, so we will assume it is editable

            # Try parsing world generator
            if mapGeneratorSoftware == "Obsidian":
                if type(mapGeneratorName) is str and mapGeneratorName in MapGenerators:
                    generator = MapGenerators[mapGeneratorName]
                else:
                    Logger.warn(f"ClassicWorldFormat - Unknown World Generator {mapGeneratorName}.", module="obsidian-map")
                    generator = None  # Continue with no generator
            else:
                Logger.warn(f"ObsidianWorldFormat - Unknown World Generator Software {mapGeneratorSoftware}.", module="obsidian-map")
                generator = None

            # Load Map Data
            Logger.debug("ClassicWorldFormat - Loading Map Data", module="obsidian-map")
            rawData = nbtFile["BlockArray"].value

            # Sanity Check File Size
            if (sizeX * sizeY * sizeZ) != len(rawData):
                raise WorldFormatError(f"ClassicWorldFormat - Invalid Map Data! Expected: {sizeX * sizeY * sizeZ} Got: {len(rawData)}")

            # Create World Data
            return World(
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
            from obsidian.modules.nbtlib import NBTLib

            Logger.warn("Saving to ClassicWorld is still WIP! Expect bugs!", module="ClassicWorld")

            # Begin creating NBT File
            nbtFile = NBTLib.NBTFile()
            nbtFile.name = "ClassicWorld"

            # Write format version
            nbtFile.tags.append(NBTLib.TAG_Byte(name="FormatVersion", value=1))

            # Write world name and UUID
            nbtFile.tags.append(NBTLib.TAG_String(name="Name", value=world.name))
            nbtFile.tags.append(NBTLib.TAG_Byte_Array(name="UUID", buffer=io.BytesIO(world.worldUUID.bytes)))

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
            nbtFile.tags.append(NBTLib.TAG_Byte_Array(name="BlockArray", buffer=io.BytesIO(world.mapArray)))

            # Test it out
            raise NotImplementedError("ClassicWorldFormat - Saving is not implemented yet!")
            print(nbtFile.pretty_tree())
            nbtFile.write_file("test.nbt")
