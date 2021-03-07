from __future__ import annotations

from typing import Type, Optional
from dataclasses import dataclass

from obsidian.module import AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, BlockError, FatalError
from obsidian.log import Logger


# Block Decorator
# Used In @Block
def Block(name: str, description: Optional[str] = None, version: Optional[str] = None, override: bool = False):
    def internal(cls):
        Logger.verbose(f"Registered Block {name} version {version}", module="submodule-import")

        # Set Class Variables
        cls.NAME = name
        cls.DESCRIPTION = description
        cls.VERSION = version
        cls.OVERRIDE = override
        cls.MANAGER = BlockManager

        # Set Obsidian Submodule to True -> Notifies Init that This Class IS a Submodule
        cls.obsidian_submodule = True

        # Return cls Obj for Decorator
        return cls
    return internal


# Block Skeleton
@dataclass
class AbstractBlock(AbstractSubmodule):
    ID: int = 5


# Internal Block Manager Singleton
class _BlockManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("Block")

        # TODO Rename these!
        # Creates List Of Blocks That Has The Block Name As Keys
        self._block_list = dict()
        # Create Cache Of Block Ids to Obj
        self._blocks = dict()

    # Registration. Called by Block Decorator
    def register(self, blockClass: Type[AbstractBlock], module: AbstractModule):
        Logger.debug(f"Registering Block {blockClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        block: AbstractBlock = super()._initSubmodule(blockClass, module)

        # Handling Special Cases if OVERRIDE is Set
        if block.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if (block.ID not in self._blocks) and (block.NAME not in self._block_list.keys()):
                Logger.warn(f"Block {block.NAME} (ID: {block.ID}) From Module {block.MODULE.NAME} Is Trying To Override A Block That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"Block {block.NAME} Is Overriding Block {self._block_list[block.NAME].NAME} (ID: {block.ID})", module=f"{module.NAME}-submodule-init")

        # Checking If Block Name Is Already In Blocks List
        # Ignoring if OVERRIDE is set
        if block.NAME in self._block_list.keys() and not block.OVERRIDE:
            raise InitRegisterError(f"Block {block.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Add Block To Cache
        Logger.verbose(f"Adding BlockId {block.ID} To Block Cache", module=f"{module.NAME}-submodule-init")
        # If Block Id Already Registered, Error
        # Ignoring if OVERRIDE is set
        if block.ID not in self._blocks or block.OVERRIDE:
            self._blocks[block.ID] = block
        else:
            raise InitRegisterError(f"Block Id {block.ID} Has Been Already Registered. Conflicting Blocks Are '{self._blocks[block.ID].NAME} ({self._blocks[block.ID].MODULE.NAME})' and '{block.NAME} ({block.MODULE.NAME})'")

        # Add Block to Blocks List
        self._block_list[block.NAME] = block

    # Generate a Pretty List of Blocks
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Blocks", "BlockId", "Module"]
            # Loop Through All Blocks And Add Value
            for _, block in self._block_list.items():
                # Add Row To Table
                table.add_row([block.NAME, block.ID, block.MODULE.NAME])
            return table
        except FatalError as e:
            # Pass Down Fatal Error To Base Server
            raise e
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

    # Property Method To Get Number Of Blocks
    @property
    def numBlocks(self):
        return len(self._block_list)

    # Generate a List of All Block Ids
    def getAllBlockIds(self):
        return list(self._blocks.keys())

    # Function To Get Block Object From BlockId
    def getBlockById(self, blockId):
        if blockId in self._blocks.keys():
            return self._blocks[blockId]
        else:
            raise BlockError(f"Block with BlockID {blockId} Not Found.")

    # Handles _BlockManager["item"]
    def __getitem__(self, block: str):
        return self._block_list[block]

    # Handles _BlockManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Creates Global BlockManager As Singleton
BlockManager = _BlockManager()
# Adds Alias To BlockManager
Blocks = BlockManager
