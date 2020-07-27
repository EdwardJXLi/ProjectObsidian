from __future__ import annotations

from typing import Type, Optional
from dataclasses import dataclass

from obsidian.module import AbstractModule
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, FatalError
from obsidian.log import Logger


# Map Generator Decorator
# Used In @MapGenerator
def MapGenerator(name: str, description: str = None, version: str = None):
    def internal(cls):
        cls.obsidian_map_generator = dict()
        cls.obsidian_map_generator["name"] = name
        cls.obsidian_map_generator["description"] = description
        cls.obsidian_map_generator["version"] = version
        cls.obsidian_map_generator["map_generator"] = cls
        return cls
    return internal


# Map Generator Skeleton
@dataclass
class AbstractMapGenerator:
    # Optional Values Defined In Module Decorator
    NAME: str = ""
    DESCRIPTION: str = ""
    VERSION: str = ""
    # Mandatory Values Defined During Module Initialization
    MODULE: Optional[AbstractModule] = None

    def generateMap(self, sizeX, sizeY, sizeZ, *args, **kwargs):
        return bytearray()


# Internal Map Generator Manager Singleton
class _MapGeneratorManager:
    def __init__(self):
        # Creates List Of Map Generators That Has The Block Generator Name As Keys
        self._generator_list = dict()

    # Registration. Called by Map Generator Decorator
    def register(self, name: str, description: str, version: str, generator: Type[AbstractMapGenerator], module):
        Logger.debug(f"Registering Map Generator {name} From Module {module.NAME}", module="init-" + module.NAME)
        obj = generator()  # type: ignore    # Create Object
        # Checking If MapGenerator Name Is Already In Generators List
        if name in self._generator_list.keys():
            raise InitRegisterError(f"Map Generator {name} Has Already Been Registered!")
        # Attach Name, Direction, and Module As Attribute
        obj.NAME = name
        obj.DESCRIPTION = description
        obj.VERSION = version
        obj.MODULE = module
        self._generator_list[name] = obj

    # Generate a Pretty List of Map Generators
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Map Generator", "Version", "Module"]
            # Loop Through All Map Generators And Add Value
            for _, generator in self._generator_list.items():
                # Adding Special Characters And Handlers
                if generator.VERSION is None:
                    generator.VERSION = "Unknown"

                # Add Row To Table
                table.add_row([generator.NAME, generator.VERSION, generator.MODULE.NAME])
            return table
        except FatalError as e:
            # Pass Down Fatal Error To Base Server
            raise e
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", "server")

    # Property Method To Get Number Of Map Generators
    @property
    def numMapGenerators(self):
        return len(self._generator_list)

    # Handles _MapGeneratorManager["item"]
    def __getitem__(self, mapGenerator: str):
        return self._generator_list[mapGenerator]

    # Handles _MapGeneratorManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Creates Global MapGeneratorManager As Singleton
MapGeneratorManager = _MapGeneratorManager()
# Adds Alias To MapGeneratorManager
MapGenerators = MapGeneratorManager
