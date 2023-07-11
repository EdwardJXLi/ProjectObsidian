from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.world import World, WorldManager
    import io

from typing import Type, Generic, Callable
from dataclasses import dataclass, field

from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.errors import InitRegisterError, ConverterError
from obsidian.log import Logger
from obsidian.types import T


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
    METADATA_WRITERS: dict[str, Callable] = field(default_factory=dict)  # List of metadata writers
    METADATA_READERS: dict[str, Callable] = field(default_factory=dict)  # List of metadata readers

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

    def registerMetadataReader(self, metadataName: str, reader: Callable):
        Logger.debug(f"Registering metadata reader {metadataName} for world format {self.NAME}", module="worldformat")
        # Check if world format supports metadata
        if not self.METADATA_SUPPORT:
            Logger.warn(f"Trying to add metadata reader {metadataName} to world format {self.NAME} that does not support metadata!", module="worldformat")

        # Check if metadata type already has a reader
        if metadataName in self.METADATA_READERS:
            raise InitRegisterError(f"Metadata Type {metadataName} already has a reader for world format {self.NAME}!")

        # Add reader to list
        self.METADATA_READERS[metadataName] = reader

    def registerMetadataWriter(self, metadataName: str, writer: Callable):
        Logger.debug(f"Registering metadata writer {metadataName} for world format {self.NAME}", module="worldformat")
        # Check if world format supports metadata
        if not self.METADATA_SUPPORT:
            Logger.warn(f"Trying to add metadata writer {metadataName} to world format {self.NAME} that does not support metadata!", module="worldformat")

        # Check if metadata type already has a writer
        if metadataName in self.METADATA_WRITERS:
            raise InitRegisterError(f"Metadata Type {metadataName} already has a writer for world format {self.NAME}!")

        # Add writer to list
        self.METADATA_WRITERS[metadataName] = writer

    def getMetadataReader(self, metadataName: str):
        if metadataName not in self.METADATA_READERS:
            return None

        return self.METADATA_READERS[metadataName]

    def getMetadataWriter(self, metadataName: str):
        if metadataName not in self.METADATA_WRITERS:
            return None

        return self.METADATA_WRITERS[metadataName]

    @staticmethod
    def _convertArgument(_, argument: str) -> AbstractWorldFormat:
        if argument in WorldFormatManager:
            # Try to grab the world format from the formats list
            return WorldFormatManager.getWorldFormat(argument)
        else:
            # Raise error if world format not found
            raise ConverterError(f"World Format {argument} Not Found!")


# Internal World Format Manager Singleton
class _WorldFormatManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("World Format", AbstractWorldFormat)

        # Creates List Of World Formats That Has The World Format Name As Keys
        self._formatDict: dict[str, AbstractWorldFormat] = dict()

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
            if worldFormat.NAME not in self._formatDict.keys():
                Logger.warn(f"World Format {worldFormat.NAME} From Module {worldFormat.MODULE.NAME} Is Trying To Override A World Format That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"World Format {worldFormat.NAME} Is Overriding World Format {self._formatDict[worldFormat.NAME].NAME}", module=f"{module.NAME}-submodule-init")

        # Checking If World Format Name Is Already In Formats List
        # Ignoring if OVERRIDE is set
        if worldFormat.NAME in self._formatDict.keys() and not worldFormat.OVERRIDE:
            raise InitRegisterError(f"World Format {worldFormat.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Add World Format to World Formats List
        self._formatDict[worldFormat.NAME] = worldFormat

        return worldFormat

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

    # Function To Get World Format Object From File Extension
    def getWorldFormatFromExtension(self, ext: str) -> AbstractWorldFormat:
        for format in self._formatDict.values():
            if ext in format.EXTENSIONS:
                return format
        raise KeyError(f"World Format With Extension {ext} Not Found!")

    # Function To Get World Format Object From Format Name
    def getWorldFormat(self, format: str) -> AbstractWorldFormat:
        return self._formatDict[format]

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
    def __contains__(self, format: str) -> bool:
        return format in self._formatDict


# Creates Global WorldFormatManager As Singleton
WorldFormatManager = _WorldFormatManager()
# Adds Alias To WorldFormatManager
WorldFormats = WorldFormatManager
