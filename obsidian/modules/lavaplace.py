from obsidian.module import Dependency, Module, AbstractModule
from obsidian.blocks import Block, Blocks
from obsidian.player import Player
from obsidian.modules.core import CoreModule

from typing import Optional


@Module(
    "LavaPlace",
    description="Quick hack to place down lava blocks",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class LavaPlace(AbstractModule):
    def __init__(self):
        super().__init__()

    @Block("OrangeCloth", override=True)
    class LavaFlagBlock(CoreModule.OrangeCloth):
        def __init__(self):
            super().__init__()

        async def placeBlock(self, ctx: Optional[Player], blockX, blockY, blockZ):
            await super().placeBlock(ctx, blockX, blockY, blockZ)
            if ctx:
                if ctx.worldPlayerManager:
                    await ctx.worldPlayerManager.world.setBlock(blockX, blockY, blockZ, Blocks.StationaryLava.ID, player=ctx, updateSelf=True)
