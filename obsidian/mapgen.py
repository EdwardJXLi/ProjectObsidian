from __future__ import annotations

from typing import Dict, Type
from dataclasses import dataclass

from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, FatalError
from obsidian.log import Logger


# Map Generator Decorator
# Used In @MapGenerator
def MapGenerator(*args, **kwargs):
    return Submodule(MapGeneratorManager, *args, **kwargs)


# Map Generator Skeleton
@dataclass
class AbstractMapGenerator(AbstractSubmodule):
    def generateMap(self, sizeX: int, sizeY: int, sizeZ: int, *args, **kwargs):
        raise NotImplementedError("Map Generation Not Implemented")


# Internal Map Generator Manager Singleton
class _MapGeneratorManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("Map Generator", AbstractMapGenerator)

        # Creates List Of Map Generators That Has The Generator Name As Keys
        self._generator_list: Dict[str, AbstractMapGenerator] = dict()

    # Registration. Called by Map Generator Decorator
    def register(self, mapGenClass: Type[AbstractMapGenerator], module: AbstractModule):
        Logger.debug(f"Registering Map Generator {mapGenClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        mapGen: AbstractMapGenerator = super()._initSubmodule(mapGenClass, module)

        # Handling Special Cases if OVERRIDE is Set
        if mapGen.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if mapGen.NAME not in self._generator_list.keys():
                Logger.warn(f"Map Generator {mapGen.NAME} From Module {mapGen.MODULE.NAME} Is Trying To Override A Map Generator That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"Map Generator {mapGen.NAME} Is Overriding Map Generator {self._generator_list[mapGen.NAME].NAME}", module=f"{module.NAME}-submodule-init")

        # Checking If Map Generator Name Is Already In Generators List
        # Ignoring if OVERRIDE is set
        if mapGen.NAME in self._generator_list.keys() and not mapGen.OVERRIDE:
            raise InitRegisterError(f"Map Generator {mapGen.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Add Map Generator to Map Generators List
        self._generator_list[mapGen.NAME] = mapGen

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
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

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
