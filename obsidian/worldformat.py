from __future__ import annotations

from typing import Type, Generic, Callable, TYPE_CHECKING
from dataclasses import dataclass, field

from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.errors import InitRegisterError, ConverterError
from obsidian.log import Logger
from obsidian.types import T

if TYPE_CHECKING:
    from obsidian.world import World, WorldManager
    import io

# World Format Decorator
# Used In @WorldFormat
def WorldFormat(*args, **kwargs):
    return Submodule(WorldFormatManager, *args, **kwargs)


# World Format Skeleton
@dataclass
class AbstractWorldFormat(AbstractSubmodule[T], Generic[T]):
    # Mandatory Values Defined In Packet Init
    EXTENSIONS: list[str] = field(default_factory=list)  # List of file extensions
    METADATA_SUPPORT: bool = False  # Whether or not the world format supports additional metadata
    METADATA_WRITERS: dict[tuple[str, str], Callable] = field(default_factory=dict)  # List of metadata writers
    METADATA_READERS: dict[tuple[str, str], Callable] = field(default_factory=dict)  # List of metadata readers

    def __repr__(self):
        return f"<World Format {self.NAME}>"

    def __str__(self):
        return self.NAME

    def loadWorld(
        self,
        fileIO: io.BufferedRandom,
        worldManager: WorldManager,
        persistent: bool = True,
        *args,
        **kwargs
    ) -> World:
        raise NotImplementedError("World Loading Not Implemented")

    def saveWorld(
        self,
        world: World,
        fileIO: io.BufferedRandom,
        worldManager: WorldManager,
        *args,
        **kwargs
    ):
        raise NotImplementedError("World Saving Not Implemented")

    @staticmethod
    def _convertArgument(_, argument: str) -> AbstractWorldFormat:
        try:
            # Try to grab the world format from the formats list
            return WorldFormatManager.getWorldFormat(argument)
        except KeyError:
            # Raise error if world format not found
            raise ConverterError(f"World Format {argument} Not Found!")


# Internal World Format Manager Singleton
class _WorldFormatManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("World Format", AbstractWorldFormat)

        # Creates List Of World Formats That Has The World Format Name As Keys
        self._formatDict: dict[str, AbstractWorldFormat] = {}

    # Registration. Called by World Format Decorator
    def register(self, worldFormatClass: Type[AbstractWorldFormat], module: AbstractModule) -> AbstractWorldFormat:
        Logger.debug(f"Registering World Format {worldFormatClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        worldFormat: AbstractWorldFormat = super()._initSubmodule(worldFormatClass, module)

        # Check if the name has a space. If so, raise warning
        if " " in worldFormatClass.NAME:
            Logger.warn(f"World Format '{worldFormatClass.NAME}' has white space in its name!", module=f"{module.NAME}-submodule-init")

        # Handling Special Cases if OVERRIDE is Set
        if worldFormat.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if worldFormat.NAME not in self._formatDict:
                Logger.warn(
                    f"World Format {worldFormat.NAME} From Module {worldFormat.MODULE.NAME} Is Trying To Override A World Format That Does Not Exist! " + \
                    "If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init"
                )
            else:
                Logger.debug(f"World Format {worldFormat.NAME} Is Overriding World Format {self._formatDict[worldFormat.NAME].NAME}", module=f"{module.NAME}-submodule-init")

        # Checking If World Format Name Is Already In Formats List
        # Ignoring if OVERRIDE is set
        if worldFormat.NAME in self._formatDict and not worldFormat.OVERRIDE:
            raise InitRegisterError(f"World Format {worldFormat.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Add World Format to World Formats List
        self._formatDict[worldFormat.NAME] = worldFormat

        return worldFormat

    def registerMetadataReader(self, worldFormat: AbstractWorldFormat, metadataSoftware: str, metadataName: str, reader: Callable):
        Logger.debug(f"Registering metadata reader [{metadataSoftware}]{metadataName} for world format {worldFormat.NAME}", module="worldformat")
        # Check if world format supports metadata
        if not worldFormat.METADATA_SUPPORT:
            Logger.warn(f"Trying to add metadata reader [{metadataSoftware}]{metadataName} to world format {worldFormat.NAME} that does not support metadata!", module="worldformat")

        # Check if metadata type already has a reader
        if (metadataSoftware, metadataName) in worldFormat.METADATA_READERS:
            raise InitRegisterError(f"Metadata Type [{metadataSoftware}]{metadataName} already has a reader for world format {worldFormat.NAME}!")

        # Add reader to list
        worldFormat.METADATA_READERS[(metadataSoftware, metadataName)] = reader

    def registerMetadataWriter(self, worldFormat: AbstractWorldFormat, metadataSoftware: str, metadataName: str, writer: Callable):
        Logger.debug(f"Registering metadata writer [{metadataSoftware}]{metadataName} for world format {worldFormat.NAME}", module="worldformat")
        # Check if world format supports metadata
        if not worldFormat.METADATA_SUPPORT:
            Logger.warn(f"Trying to add metadata writer [{metadataSoftware}]{metadataName} to world format {worldFormat.NAME} that does not support metadata!", module="worldformat")

        # Check if metadata type already has a writer
        if (metadataSoftware, metadataName) in worldFormat.METADATA_WRITERS:
            raise InitRegisterError(f"Metadata Type [{metadataSoftware}]{metadataName} already has a writer for world format {worldFormat.NAME}!")

        # Add writer to list
        worldFormat.METADATA_WRITERS[(metadataSoftware, metadataName)] = writer

    def getMetadataReader(self, worldFormat: AbstractWorldFormat, metadataSoftware: str, metadataName: str):
        Logger.debug(f"Getting metadata reader for [{metadataSoftware}]{metadataName}", module="worldformat")
        if (metadataSoftware, metadataName) not in worldFormat.METADATA_READERS:
            return None

        return worldFormat.METADATA_READERS[(metadataSoftware, metadataName)]

    def getMetadataWriter(self, worldFormat: AbstractWorldFormat, metadataSoftware: str, metadataName: str):
        Logger.debug(f"Getting metadata writer for [{metadataSoftware}]{metadataName}", module="worldformat")
        if (metadataSoftware, metadataName) not in worldFormat.METADATA_WRITERS:
            return None

        return worldFormat.METADATA_WRITERS[(metadataSoftware, metadataName)]

    # Generate a Pretty List of World Formats
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["World Format", "Version", "Module"]
            # Loop Through All World Formats And Add Value
            for _, worldFormat in self._formatDict.items():
                # Add Row To Table
                table.add_row([worldFormat.NAME, worldFormat.VERSION, worldFormat.MODULE.NAME])
            return table
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")
            return None

    # Function To Get World Format Object From File Extension
    def getWorldFormatFromExtension(self, ext: str) -> AbstractWorldFormat:
        for fmt in self._formatDict.values():
            if ext in fmt.EXTENSIONS:
                return fmt
        raise KeyError(f"World Format With Extension {ext} Not Found!")

    # Function To Get World Format Object From Format Name
    def getWorldFormat(self, fmt: str, ignoreCase: bool = True) -> AbstractWorldFormat:
        if ignoreCase:
            for fName, fObject in self._formatDict.items():
                if fName.lower() == fmt.lower():
                    return fObject
            raise KeyError(fmt)
        return self._formatDict[fmt]

    # Handles _WorldFormatManager["item"]
    def __getitem__(self, *args, **kwargs) -> AbstractWorldFormat:
        return self.getWorldFormat(*args, **kwargs)

    # Handles _WorldFormatManager.item
    def __getattr__(self, *args, **kwargs) -> AbstractWorldFormat:
        return self.getWorldFormat(*args, **kwargs)

    # Get Number Of World Formats
    def __len__(self) -> int:
        return len(self._formatDict)

    # Check if world format exists
    def __contains__(self, fmt: str) -> bool:
        return fmt in self._formatDict


# Creates Global WorldFormatManager As Singleton
WorldFormatManager = _WorldFormatManager()
# Adds Alias To WorldFormatManager
WorldFormats = WorldFormatManager
