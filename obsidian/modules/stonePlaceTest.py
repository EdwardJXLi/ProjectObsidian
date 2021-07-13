from obsidian.module import Dependency, Module, AbstractModule
from obsidian.blocks import Block
from obsidian.player import Player
from obsidian.modules.core import CoreModule

from typing import Optional


@Module(
    "StonePlaceTest1",
    description="WASD Prints A Message In Chat When a Stone is Placed",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class CoreModule(AbstractModule):
    def __init__(self):
        super().__init__()

    @Block("Stone", override=True)
    class SpecialStoneX(CoreModule.Stone):
        def __init__(self):
            super().__init__()

        async def placeBlock(self, ctx: Optional[Player], blockX, blockY, blockZ):
            await super().placeBlock(ctx, blockX, blockY, blockZ)
            if ctx:
                await ctx.sendMessage("STONE PLACED???")
