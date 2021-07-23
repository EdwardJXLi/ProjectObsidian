from obsidian.module import Dependency, Module, AbstractModule
from obsidian.commands import Command, AbstractCommand
from obsidian.blocks import Block, Blocks
from obsidian.player import Player
from obsidian.modules.core import CoreModule
from obsidian.log import Logger


@Module(
    "LiquidPlace",
    description="Place Liquids Using Alterate Blocks",
    author="RadioactiveHydra",
    version="1.0.0",
    dependencies=[Dependency("core", "1.0.0")]
)
class LiquidPlace(AbstractModule):
    def __init__(self):
        super().__init__()

        # Add a new flag to allow for liquid placing
        Player.place_liquid = False  # type: ignore

        Logger.info("Liquid Place Active!", module="LiquidPlace")

    @Block("RedCloth", override=True)
    class RedClothLiquidPlace(CoreModule.RedCloth):
        def __init__(self):
            super().__init__()

        async def placeBlock(self, ctx: Player, blockX, blockY, blockZ):
            await super().placeBlock(ctx, blockX, blockY, blockZ)
            if ctx.place_liquid:  # type: ignore
                if ctx.worldPlayerManager:
                    await ctx.worldPlayerManager.world.setBlock(
                        blockX,
                        blockY,
                        blockZ,
                        Blocks.StationaryLava.ID,
                        player=ctx,
                        updateSelf=True
                    )

    @Block("OrangeCloth", override=True)
    class OrangeClothLiquidPlace(CoreModule.OrangeCloth):
        def __init__(self):
            super().__init__()

        async def placeBlock(self, ctx: Player, blockX, blockY, blockZ):
            await super().placeBlock(ctx, blockX, blockY, blockZ)
            if ctx.place_liquid:  # type: ignore
                if ctx.worldPlayerManager:
                    await ctx.worldPlayerManager.world.setBlock(
                        blockX,
                        blockY,
                        blockZ,
                        Blocks.FlowingLava.ID,
                        player=ctx,
                        updateSelf=True
                    )

    @Block("UltramarineCloth", override=True)
    class UltramarineClothLiquidPlace(CoreModule.UltramarineCloth):
        def __init__(self):
            super().__init__()

        async def placeBlock(self, ctx: Player, blockX, blockY, blockZ):
            await super().placeBlock(ctx, blockX, blockY, blockZ)
            if ctx.place_liquid:  # type: ignore
                if ctx.worldPlayerManager:
                    await ctx.worldPlayerManager.world.setBlock(
                        blockX,
                        blockY,
                        blockZ,
                        Blocks.StationaryWater.ID,
                        player=ctx,
                        updateSelf=True
                    )

    @Block("CapriCloth", override=True)
    class CapriClothLiquidPlace(CoreModule.CapriCloth):
        def __init__(self):
            super().__init__()

        async def placeBlock(self, ctx: Player, blockX, blockY, blockZ):
            await super().placeBlock(ctx, blockX, blockY, blockZ)
            if ctx.place_liquid:  # type: ignore
                if ctx.worldPlayerManager:
                    await ctx.worldPlayerManager.world.setBlock(
                        blockX,
                        blockY,
                        blockZ,
                        Blocks.FlowingWater.ID,
                        player=ctx,
                        updateSelf=True
                    )

    @Command(
        "LiquidPlace",
        description="Toggle Liquid Placement"
    )
    class TestCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["liquidplace", "lp"]
            )

        async def execute(self, ctx: Player):
            # Check if place_liquid is already enabled
            if not ctx.place_liquid:  # type: ignore
                ctx.place_liquid = True  # type: ignore
                await ctx.sendMessage("&aLiquid Place is Now Enabled!&f")
                await ctx.sendMessage("Use &cRed Wool&f to place &cStill Lava&f.")
                await ctx.sendMessage("Use &6Orange Wool&f to place &6Flowing Lava&f.")
                await ctx.sendMessage("Use &9Blue Wool&f to place &9Still Water&f.")
                await ctx.sendMessage("Use &bCyan Wool&f to place &bFlowing Water&c.")
            else:
                ctx.place_liquid = False  # type: ignore
                await ctx.sendMessage("&eLiquid Place is Now Disabled!&f")
                await ctx.sendMessage("You can now place blocks normally.")

            return None  # Nothing should be returned
