from obsidian.module import Dependency, Module, AbstractModule
from obsidian.blocks import Block
from obsidian.player import Player
from obsidian.modules.core import CoreModule

from typing import Optional


@Module(
    "StonePlaceTest",
    description="Prints A Message In Chat When a Stone is Placed",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class CoreModule(AbstractModule):
    def __init__(self):
        super().__init__()

    @Block("SpecialStone", override=True)
    class SpecialStone(CoreModule.CoreBlockStone):
        def __init__(self):
            super().__init__(ID=1)

        async def placeBlock(self, ctx: Optional[Player], blockX, blockY, blockZ):
            await super().placeBlock(ctx, blockX, blockY, blockZ)
            await ctx.sendMessage("STONE PLACED!")
