from typing import List, Type, Optional
from dataclasses import dataclass

from obsidian.log import Logger
from obsidian.module import AbstractModule
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, WorldGenerationError, FatalError


#
# WORLD MANAGER
#


class WorldManager:
    def __init__(self, server, blacklist: List[str] = []):
        self.server = server
        self.worlds = dict()
        self.blacklist = blacklist
        self.persistant = True

        # If World Location Was Not Given, Disable Persistance
        # (Don't Save / Load)
        if self.server.worldSaveLocation is None:
            Logger.warn("World Save Location Was Not Defined. Creating Non-Persistant World!!!", module="init-world")
            self.persistant = False

    def generateWorld(self, sizeX, sizeY, sizeZ, *args, generator: str = "Flat", **kwargs):
        Logger.debug(f"Generating World With Size {sizeX}, {sizeY}, {sizeX} With Generator {generator}", module="init-world")
        if generator in WorldGenerators._generator_list.keys():
            generatedWorld = WorldGenerators[generator].generateWorld(sizeX, sizeY, sizeZ, *args, **kwargs)
            size = sizeX * sizeY * sizeZ
            # Verify World Data Size
            if len(generatedWorld) == size:
                return generatedWorld
            else:
                raise WorldGenerationError(f"Expected World Size {size} While Generating Word. Got {len(generatedWorld)}")
        else:
            raise WorldGenerationError(f"Unrecognized World Generation Type {generator} While Generating World")

    def loadWorlds(self):
        if self.persistant:
            # TODO: World Loading
            pass
        else:
            Logger.debug(f"Creating Temporary World {self.server.defaultWorld}", module="init-world")
            self.worlds[self.server.defaultWorld] = World(
                256, 256, 256,  # Passing World X, Y, Z
                self.generateWorld(256, 256, 256)  # Generating World Data
            )


class World:
    def __init__(self, sizeX: int, sizeY: int, sizeZ: int, mapArray: bytearray):
        self.sizeX = sizeX
        self.sizeY = sizeY
        self.sizeZ = sizeZ
        self.mapArray = mapArray


#
# WORLD GENERATOR
#


# World Generator Decorator
# Used In @WorldGenerator
def WorldGenerator(name: str, description: str = None, version: str = None):
    def internal(cls):
        cls.obsidian_world_generator = dict()
        cls.obsidian_world_generator["name"] = name
        cls.obsidian_world_generator["description"] = description
        cls.obsidian_world_generator["version"] = version
        cls.obsidian_world_generator["world_generator"] = cls
        return cls
    return internal


# World Generator Skeleton
@dataclass
class AbstraceWorldGenerator:
    NAME: str = ""
    DESCRIPTION: str = ""
    VERSION: str = ""
    MODULE: Optional[AbstractModule] = None

    def generateWorld(self, sizeX, sizeY, sizeZ, *args, **kwargs):
        return bytearray()


# Internal World Generator Manager Singleton
class _WorldGeneratorManager:
    def __init__(self):
        # Creates List Of World Generators That Has The Module Name As Keys
        self._generator_list = dict()

    # Registration. Called by World Generator Decorator
    def register(self, name: str, description: str, version: str, generator: Type[AbstraceWorldGenerator], module):
        Logger.debug(f"Registering World Generator {name} From Module {module.NAME}", module="init-" + module.NAME)
        obj = generator()  # type: ignore    # Create Object
        # Checking If WorldGenerator Name Is Already In Generators List
        if name in self._generator_list.keys():
            raise InitRegisterError(f"World Generator {name} Has Already Been Registered!")
        # Attach Name, Direction, and Module As Attribute
        obj.NAME = name
        obj.DESCRIPTION = description
        obj.VERSION = version
        obj.MODULE = module
        self._generator_list[name] = obj

    # Generate a Pretty List of World Generators
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["World Generator", "Version", "Module"]
            # Loop Through All World Generators And Add Value
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

    # Property Method To Get Number Of World Generators
    @property
    def numWorldGenerators(self):
        return len(self._generator_list)

    # Handles _WorldGeneratorManager["item"]
    def __getitem__(self, worldGenerator: str):
        return self._generator_list[worldGenerator]

    # Handles _WorldGeneratorManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Creates Global WorldGeneratorManager As Singleton
WorldGeneratorManager = _WorldGeneratorManager()
# Adds Alias To WorldGeneratorManager
WorldGenerators = WorldGeneratorManager
