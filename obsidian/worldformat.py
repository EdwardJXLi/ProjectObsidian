from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.world import World, WorldManager
    import io

from typing import Dict, Type, List, Generic
from dataclasses import dataclass, field

from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, FatalError, T
from obsidian.log import Logger


# World Format Decorator
# Used In @WorldFormat
def WorldFormat(*args, **kwargs):
    return Submodule(WorldFormatManager, *args, **kwargs)


# World Format Skeleton
@dataclass
class AbstractWorldFormat(AbstractSubmodule[T], Generic[T]):
    # Mandatory Values Defined In Packet Init
    KEYS: List[str] = field(default_factory=list)        # List of "keys" that dictate this world format
    EXTENTIONS: List[str] = field(default_factory=list)  # List of file extentions

    def loadWorld(
        self,
        fileIO: io.BufferedRandom,
        worldManager: WorldManager,
        persistant: bool = True,
        *args,
        **kwargs
    ):
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


# Internal World Format Manager Singleton
class _WorldFormatManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("World Format", AbstractWorldFormat)

        # Creates List Of World Formats That Has The World Format Name As Keys
        self._format_dict: Dict[str, AbstractWorldFormat] = dict()

    # Registration. Called by World Format Decorator
    def register(self, worldFormatClass: Type[AbstractWorldFormat], module: AbstractModule):
        Logger.debug(f"Registering World Format {worldFormatClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        worldFormat: AbstractWorldFormat = super()._initSubmodule(worldFormatClass, module)

        # Check if the name has a space. If so, raise warning
        if " " in worldFormatClass.NAME:
            Logger.warn(f"World Format '{worldFormatClass.NAME}' has whitspace in its name!", module=f"{module.NAME}-submodule-init")

        # Handling Special Cases if OVERRIDE is Set
        if worldFormat.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if worldFormat.NAME not in self._format_dict.keys():
                Logger.warn(f"World Format {worldFormat.NAME} From Module {worldFormat.MODULE.NAME} Is Trying To Override A World Format That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"World Format {worldFormat.NAME} Is Overriding World Format {self._format_dict[worldFormat.NAME].NAME}", module=f"{module.NAME}-submodule-init")

        # Checking If World Format Name Is Already In Formats List
        # Ignoring if OVERRIDE is set
        if worldFormat.NAME in self._format_dict.keys() and not worldFormat.OVERRIDE:
            raise InitRegisterError(f"World Format {worldFormat.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Add World Format to World Formats List
        self._format_dict[worldFormat.NAME] = worldFormat

    # Generate a Pretty List of World Formats
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["World Format", "Version", "Module"]
            # Loop Through All World Formats And Add Value
            for _, worldFormat in self._format_dict.items():
                # Add Row To Table
                table.add_row([worldFormat.NAME, worldFormat.VERSION, worldFormat.MODULE.NAME])
            return table
        except FatalError as e:
            # Pass Down Fatal Error To Base Server
            raise e
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

    # Property Method To Get Number Of World Formats
    @property
    def numWorldFormats(self):
        return len(self._format_dict)

    # Handles _WorldFormatManager["item"]
    def __getitem__(self, format: str):
        return self._format_dict[format]

    # Handles _WorldFormatManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Creates Global WorldFormatManager As Singleton
WorldFormatManager = _WorldFormatManager()
# Adds Alias To WorldFormatManager
WorldFormats = WorldFormatManager
