from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.world import World, WorldManager
    import io

from typing import Type, Optional, List
from dataclasses import dataclass

from obsidian.module import AbstractModule
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, FatalError
from obsidian.log import Logger


# World Format Decorator
# Used In @WorldFormat
def WorldFormat(name: str, description: str = None, version: str = None):
    def internal(cls):
        cls.obsidian_world_format = dict()
        cls.obsidian_world_format["name"] = name
        cls.obsidian_world_format["description"] = description
        cls.obsidian_world_format["version"] = version
        cls.obsidian_world_format["format"] = cls
        return cls
    return internal


# World Format Skeleton
@dataclass
class AbstractWorldFormat:
    # Mandatory Values Defined In Packet Init
    KEYS: List[str]        # List of "keys" that dictate this world format
    EXTENTIONS: List[str]  # List of file extentions
    # Mandatory Values Defined In Module Decorator
    NAME: str = ""
    # Optional Values Defined In Module Decorator
    DESCRIPTION: str = ""
    VERSION: str = ""
    # Mandatory Values Defined During Module Initialization
    MODULE: Optional[AbstractModule] = None

    def loadWorld(
        self,
        fileIO: io.BufferedRandom,
        worldManager: WorldManager,
        persistant: bool = True
    ):
        return None

    def saveWorld(
        self,
        world: World,
        fileIO: io.BufferedRandom,
        worldManager: WorldManager
    ):
        return None


# Internal World Format Manager Singleton
class _WorldFormatManager:
    def __init__(self):
        # Creates List Of World Formats That Has The World Format Name As Keys
        self._format_list = dict()

    # Registration. Called by World Format Decorator
    def register(self, name: str, description: str, version: str, format: Type[AbstractWorldFormat], module):
        Logger.debug(f"Registering World Format {name} From Module {module.NAME}", module="init-" + module.NAME)
        obj = format()  # type: ignore    # Create Object
        # Checking If World Format Name Is Already In World Formats List
        if name in self._format_list.keys():
            raise InitRegisterError(f"World Format {name} Has Already Been Registered!")
        # Attach Name, Direction, and Module As Attribute
        obj.NAME = name
        obj.DESCRIPTION = description
        obj.VERSION = version
        obj.MODULE = module
        self._format_list[name] = obj

    # Generate a Pretty List of World Formats
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["World Format", "Version", "Module"]
            # Loop Through All World Formats And Add Value
            for _, worldFormat in self._format_list.items():
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
        return len(self._format_list)

    def getAllWorldFormatIds(self):
        return [obj.ID for obj in self._format_list.values()]

    # Handles _WorldFormatManager["item"]
    def __getitem__(self, format: str):
        return self._format_list[format]

    # Handles _WorldFormatManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Creates Global WorldFormatManager As Singleton
WorldFormatManager = _WorldFormatManager()
# Adds Alias To WorldFormatManager
WorldFormats = WorldFormatManager
