from __future__ import annotations

from typing import Type, Optional
from dataclasses import dataclass

from obsidian.module import AbstractModule
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, BlockError, FatalError
from obsidian.log import Logger


# Block Decorator
# Used In @Block
def Block(name: str, blockId: int):
    def internal(cls):
        cls.obsidian_block = dict()
        cls.obsidian_block["name"] = name
        cls.obsidian_block["blockId"] = blockId
        cls.obsidian_block["block"] = cls
        return cls
    return internal


# Block Skeleton
@dataclass
class AbstractBlock:
    # Optional Values Defined In Module Decorator
    NAME: str = ""
    ID: int = 0  # Block Id
    # Mandatory Values Defined During Module Initialization
    MODULE: Optional[AbstractModule] = None


# Internal Block Manager Singleton
class _BlockManager:
    def __init__(self):
        # Creates List Of Blocks That Has The Block Name As Keys
        self._block_list = dict()
        # Create Cache Of Block Ids to Obj
        self._blocks = dict()

    # Registration. Called by Block Decorator
    def register(self, name: str, blockId: int, block: Type[AbstractBlock], module):
        Logger.debug(f"Registering Block {name} From Module {module.NAME}", module="init-" + module.NAME)
        obj = block()  # type: ignore    # Create Object
        # Checking If Block Name Is Already In Blocks List
        if name in self._block_list.keys():
            raise InitRegisterError(f"Block {name} Has Already Been Registered!")

        # Add Block To Cache
        Logger.debug(f"Adding BlockId {blockId} To Block Cache", module="init-" + module.NAME)
        # If Block Id Already Registered, Error
        if blockId not in self._blocks:
            self._blocks[blockId] = obj
        else:
            raise InitRegisterError(f"Block Id {blockId} Has Been Already Registered. Conflicting Blocks Are '{self._blocks[blockId].NAME} ({self._blocks[blockId].MODULE.NAME})' and '{name} ({module.NAME})'")

        # Attach Name, Direction, and Module As Attribute
        obj.NAME = name
        obj.ID = blockId
        obj.MODULE = module
        self._block_list[name] = obj

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

    def getAllBlockIds(self):
        return [obj.ID for obj in self._block_list.values()]

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
