from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.player import Player

from typing import Type, Optional
from dataclasses import dataclass

from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, BlockError, FatalError, ClientError
from obsidian.log import Logger


# Block Decorator
# Used In @Block
def Block(*args, **kwargs):
    return Submodule(BlockManager, *args, **kwargs)


# Block Skeleton
@dataclass
class AbstractBlock(AbstractSubmodule):
    ID: int = 0

    async def placeBlock(self, ctx: Optional[Player], blockX: int, blockY: int, blockZ: int):
        # Checking If User Can Set Blocks
        if ctx is not None:  # Checking If User Was Passed
            if not ctx.worldPlayerManager.world.canEdit:  # Checking If World Is Read-Only
                if not ctx.opStatus:  # Checking If Player Is Not OP
                    # Check If Air Exists (Prevents Crash if Stuff Wacky)
                    if "Air" in Blocks._block_list:
                        if self.ID == Blocks.Air.ID:
                            raise ClientError("You Do Not Have Permission To Break This Block")
                        else:
                            raise ClientError("You Do Not Have Permission To Place This Block")
                    else:
                        raise ClientError("You Do Not Have Permission To Modify This Block")

        # Setting Block in World
        await ctx.worldPlayerManager.world.setBlock(blockX, blockY, blockZ, self.ID, player=ctx)


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
                Logger.debug(f"Block {block.NAME} Is Overriding Block {self._blocks[block.ID].NAME} (ID: {block.ID})", module=f"{module.NAME}-submodule-init")

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
    def getBlockById(self, blockId: int):
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
