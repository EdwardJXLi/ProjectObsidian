from __future__ import annotations

from typing import Type, Generic, Optional
from dataclasses import dataclass
import asyncio

from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.errors import InitRegisterError, ConverterError
from obsidian.types import T
from obsidian.log import Logger


# Map Generator Decorator
# Used In @MapGenerator
def MapGenerator(*args, **kwargs):
    return Submodule(MapGeneratorManager, *args, **kwargs)


# Map generation status
# Used for live updates in multithreaded map generation
class MapGeneratorStatus:
    def __init__(self, generator, printUpdates: bool = True):
        # Base level information on generators
        self.generator = generator

        # Initialize variables to default values
        self.done: bool = False
        self.status: str = "Starting Map Generation..."
        self.progress: float = 0

        # Flag to dictate if status updates should be printed to term
        self.printUpdates = printUpdates

        # Error Handling for Map Generation
        self.error: Optional[Exception] = None

        # Final Map Output for Listeners
        self._map: Optional[bytearray] = None

        # Flow control helpers
        self._event = asyncio.Event()

        # Print intial status
        if self.printUpdates:
            Logger.info(f"{self.generator.NAME}: {self.status} ({int(self.progress * 100)}%)", module="mapgen")

    # Sets generation status and progress, announces update to all waiting threads.
    def setStatus(self, progress: float, status: str = "Generating Map...", announce: bool = True):
        # Sanity Check Input
        if not 0.00 <= progress <= 1.00:
            raise IndexError("Progress must be a float between 0.00 (0%) and 1.00 (100%)!")
        if progress == 1.00:
            Logger.warn("Progress should not be set to 1.0 (100%) directly. Use setDone() instead!", module="mapgen")

        # Set Status and Progress
        self.status = status
        self.progress = progress

        # Print out map generation status
        if self.printUpdates:
            Logger.info(f"{self.generator.NAME}: {self.status} ({int(self.progress * 100)}%)", module="mapgen")

        # Announce progress to all waiting listeners
        if announce:
            # Quickly set and clear event to announce update
            # This should be fine, but if it causes issues, a sleep might be needed
            self._event.set()
            self._event.clear()

    # Sets generation status to done.
    def setDone(self, status: str = "Map Generation Completed!"):
        if not self.done:
            # Set status and progress to done
            self.done = True
            self.status = status
            self.progress = 1.00

            # Print out map generation status
            if self.printUpdates:
                Logger.info(f"{self.generator.NAME}: {self.status} ({int(self.progress * 100)}%)", module="mapgen")

            # Announce progress to all waiting listeners
            self._event.set()
        else:
            Logger.warn("Map Generation Already Completed!", module="mapgen")

    # Sets error for when a map generation fails
    def setError(self, error: Exception):
        # Set the error to the error in question, so it can be thrown again
        self.error = error
        Logger.error(f"{self.generator.NAME}: Map Generation Failed! - {self.error}", module="mapgen")

        # Disable printing of updates since it has now crashed.
        # Prevents duplicate messages from setDone
        self.printUpdates = False

        # Set status to done with error status
        self.setDone(status=f"Map Generation Failed: {str(error)}")

    # Gets generation progress
    def getStatus(self):
        # Block thread until status updates
        if self.error:
            # Raise error if error is set
            raise self.error
        else:
            # Else, return the current status
            return self.done, self.progress, self.status

    # Waits for status to update
    # TODO: Maybe make a non-async version of this?
    async def waitForStatus(self):
        # Block thread until status updates
        if self.error:
            # Raise error if error is set
            raise self.error
        elif self.done:
            # If done, no need to wait
            return self.done, self.progress, self.status
        else:
            # Else, wait for status to update
            await self._event.wait()
            return self.done, self.progress, self.status


# Map Generator Skeleton
@dataclass
class AbstractMapGenerator(AbstractSubmodule[T], Generic[T]):
    def generateMap(
        self,
        sizeX: int,
        sizeY: int,
        sizeZ: int,
        seed: int,
        generationStatus: MapGeneratorStatus,
        *args,
        **kwargs
    ) -> bytearray:
        raise NotImplementedError("Map Generation Not Implemented")

    @staticmethod
    def _convert_arg(_, argument: str) -> AbstractMapGenerator:
        try:
            # Try to grab the mag generator from the generators list
            return MapGeneratorManager.getMapGenerator(argument)
        except KeyError:
            # Raise error if map generator not found
            raise ConverterError(f"Map Generator {argument} Not Found!")


# Internal Map Generator Manager Singleton
class _MapGeneratorManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("Map Generator", AbstractMapGenerator)

        # Creates List Of Map Generators That Has The Generator Name As Keys
        self._generator_dict: dict[str, AbstractMapGenerator] = dict()

    # Registration. Called by Map Generator Decorator
    def register(self, mapGenClass: Type[AbstractMapGenerator], module: AbstractModule) -> AbstractMapGenerator:
        Logger.debug(f"Registering Map Generator {mapGenClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        mapGen: AbstractMapGenerator = super()._initSubmodule(mapGenClass, module)

        # Check if the name has a space. If so, raise warning
        if " " in mapGenClass.NAME:
            Logger.warn(f"Map Generator '{mapGenClass.NAME}' has white space in its name!", module=f"{module.NAME}-submodule-init")

        # Handling Special Cases if OVERRIDE is Set
        if mapGen.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if mapGen.NAME not in self._generator_dict.keys():
                Logger.warn(f"Map Generator {mapGen.NAME} From Module {mapGen.MODULE.NAME} Is Trying To Override A Map Generator That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"Map Generator {mapGen.NAME} Is Overriding Map Generator {self._generator_dict[mapGen.NAME].NAME}", module=f"{module.NAME}-submodule-init")

        # Checking If Map Generator Name Is Already In Generators List
        # Ignoring if OVERRIDE is set
        if mapGen.NAME in self._generator_dict.keys() and not mapGen.OVERRIDE:
            raise InitRegisterError(f"Map Generator {mapGen.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Add Map Generator to Map Generators List
        self._generator_dict[mapGen.NAME] = mapGen

        return mapGen

    # Generate a Pretty List of Map Generators
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Map Generator", "Version", "Module"]
            # Loop Through All Map Generators And Add Value
            for _, generator in self._generator_dict.items():
                # Adding Special Characters And Handlers
                if generator.VERSION is None:
                    generator.VERSION = "Unknown"

                # Add Row To Table
                table.add_row([generator.NAME, generator.VERSION, generator.MODULE.NAME])
            return table
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

    # Property Method To Get Number Of Map Generators
    @property
    def numMapGenerators(self) -> int:
        return len(self._generator_dict)

    # Function To Get Map Generator Object From Generator Name
    def getMapGenerator(self, generator: str) -> AbstractMapGenerator:
        return self._generator_dict[generator]

    # Handles _MapGeneratorManager["item"]
    def __getitem__(self, *args, **kwargs) -> AbstractMapGenerator:
        return self.getMapGenerator(*args, **kwargs)

    # Handles _MapGeneratorManager.item
    def __getattr__(self, *args, **kwargs) -> AbstractMapGenerator:
        return self.getMapGenerator(*args, **kwargs)


# Creates Global MapGeneratorManager As Singleton
MapGeneratorManager = _MapGeneratorManager()
# Adds Alias To MapGeneratorManager
MapGenerators = MapGeneratorManager
