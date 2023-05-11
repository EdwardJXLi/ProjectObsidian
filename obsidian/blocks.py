from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.player import Player

from typing import Type, Generic
from dataclasses import dataclass

from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.errors import InitRegisterError, BlockError, ClientError, ConverterError
from obsidian.log import Logger
from obsidian.types import T


# Block Decorator
# Used In @Block
def Block(*args, **kwargs):
    return Submodule(BlockManager, *args, **kwargs)


# Block Skeleton
@dataclass
class AbstractBlock(AbstractSubmodule[T], Generic[T]):
    ID: int = 0

    async def placeBlock(self, ctx: Player, blockX: int, blockY: int, blockZ: int):
        # Check edge case in which player is not connected to any world.
        if ctx.worldPlayerManager is None:
            Logger.warn("Player is trying to place blocks while not being connected to any world. Skipping block placement", module="abstract-block")
            return

        # Checking If User Can Set Blocks
        if not ctx.worldPlayerManager.world.canEditBlock(ctx, self):
            raise ClientError("You Don't Have Permission To Edit This Block!")

        # Setting Block in World
        await ctx.worldPlayerManager.world.setBlock(blockX, blockY, blockZ, self.ID, player=ctx)

    @staticmethod
    def _convertArgument(_, argument: str) -> AbstractBlock:
        if argument in BlockManager:
            # Try to grab the block from the blocks list
            return BlockManager.getBlock(argument)
        else:
            # Raise error if block not found
            raise ConverterError(f"Block {argument} Not Found!")


# Internal Block Manager Singleton
class _BlockManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("Block", AbstractBlock)

        # Creates List Of Blocks That Has The Block Name As Keys
        self._blockDict: dict[str, AbstractBlock] = dict()
        # Create Cache Of Block Ids to Obj
        self._blockIds: dict[int, AbstractBlock] = dict()

    # Registration. Called by Block Decorator
    def register(self, blockClass: Type[AbstractBlock], module: AbstractModule) -> AbstractBlock:
        Logger.debug(f"Registering Block {blockClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        block: AbstractBlock = super()._initSubmodule(blockClass, module)

        # Check if the name has a space. If so, raise warning
        if " " in block.NAME:
            Logger.warn(f"Block '{block.NAME}' has white space in its name!", module=f"{module.NAME}-submodule-init")

        # Handling Special Cases if OVERRIDE is Set
        if block.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if (block.ID not in self._blockIds) and (block.NAME not in self._blockDict.keys()):
                Logger.warn(f"Block {block.NAME} (ID: {block.ID}) From Module {block.MODULE.NAME} Is Trying To Override A Block That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"Block {block.NAME} Is Overriding Block {self._blockIds[block.ID].NAME} (ID: {block.ID})", module=f"{module.NAME}-submodule-init")

        # Checking If Block Name Is Already In Blocks List
        # Ignoring if OVERRIDE is set
        if block.NAME in self._blockDict.keys() and not block.OVERRIDE:
            raise InitRegisterError(f"Block {block.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Add Block To Cache
        Logger.verbose(f"Adding BlockId {block.ID} To Block Cache", module=f"{module.NAME}-submodule-init")
        # If Block Id Already Registered, Error
        # Ignoring if OVERRIDE is set
        if block.ID not in self._blockIds or block.OVERRIDE:
            self._blockIds[block.ID] = block
        else:
            raise InitRegisterError(f"Block Id {block.ID} Has Been Already Registered. Conflicting Blocks Are '{self._blockIds[block.ID].NAME} ({self._blockIds[block.ID].MODULE.NAME})' and '{block.NAME} ({block.MODULE.NAME})'")

        # Add Block to Blocks List
        self._blockDict[block.NAME] = block

        return block

    # Generate a Pretty List of Blocks
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Blocks", "BlockId", "Module"]
            # Loop Through All Blocks And Add Value
            for _, block in self._blockDict.items():
                # Add Row To Table
                table.add_row([block.NAME, block.ID, block.MODULE.NAME])
            return table
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

    # Generate a List of All Block Ids
    def getAllBlockIds(self) -> list[int]:
        return list(self._blockIds.keys())

    # Function To Get Block Object From BlockId
    def getBlockById(self, blockId: int) -> AbstractBlock:
        if blockId in self._blockIds.keys():
            return self._blockIds[blockId]
        else:
            raise BlockError(f"Block with BlockID {blockId} Not Found.")

    # Function To Get Block Object From Block Name
    def getBlock(self, block: str) -> AbstractBlock:
        return self._blockDict[block]

    # Handles _BlockManager["item"]
    def __getitem__(self, *args, **kwargs) -> AbstractBlock:
        return self.getBlock(*args, **kwargs)

    # Handles _BlockManager.item
    def __getattr__(self, *args, **kwargs) -> AbstractBlock:
        return self.getBlock(*args, **kwargs)

    # Get Number Of Blocks
    def __len__(self) -> int:
        return len(self._blockDict)

    # Check if block exists
    def __contains__(self, block: str) -> bool:
        return block in self._blockDict


# Creates Global BlockManager As Singleton
BlockManager = _BlockManager()
# Adds Alias To BlockManager
Blocks = BlockManager
