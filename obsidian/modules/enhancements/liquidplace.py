from obsidian.module import Dependency, Module, AbstractModule
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player
from obsidian.errors import ClientError
from obsidian.blocks import Blocks
from obsidian.modules.core import CoreModule
from obsidian.mixins import Override, addAttribute
from obsidian.log import Logger


@Module(
    "LiquidPlace",
    description="Place Liquids Using Alterate Blocks",
    author="RadioactiveHydra",
    version="1.3.0",
    dependencies=[Dependency("core")]
)
class LiquidPlaceModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

        addAttribute(Player, "placeLiquids", default=False)

        Logger.info("Liquid Place Active!", module="LiquidPlace")

        # Override Block Placing to Place Liquids!
        @Override(CoreModule.RedCloth.placeBlock)
        async def placeStationaryLava(block_self, *args, **kwargs):
            await self.placeLiquid(block_self, *args, liquidType=Blocks.StationaryLava, **kwargs)

        @Override(CoreModule.OrangeCloth.placeBlock)
        async def placeFlowingLava(block_self, *args, **kwargs):
            await self.placeLiquid(block_self, *args, liquidType=Blocks.FlowingLava, **kwargs)

        @Override(CoreModule.UltramarineCloth.placeBlock)
        async def placeStationaryWater(block_self, *args, **kwargs):
            await self.placeLiquid(block_self, *args, liquidType=Blocks.StationaryWater, **kwargs)

        @Override(CoreModule.CapriCloth.placeBlock)
        async def placeFlowingWater(block_self, *args, **kwargs):
            await self.placeLiquid(block_self, *args, liquidType=Blocks.FlowingWater, **kwargs)

    # Method to Place Custom Liquids
    async def placeLiquid(self, block_self, ctx, blockX, blockY, blockZ, liquidType):
        if ctx.placeLiquids:
            if ctx.worldPlayerManager:
                # Check if user has permission to set blocks
                if not ctx.worldPlayerManager.world.canEditBlock(ctx, block_self):
                    raise ClientError("You Don't Have Permission To Edit This Block!")
                # Set the block to stationary lava
                await ctx.worldPlayerManager.world.setBlock(
                    blockX,
                    blockY,
                    blockZ,
                    liquidType,
                    player=ctx,
                    updateSelf=True
                )
        else:
            return await block_self.placeBlock(ctx, blockX, blockY, blockZ)

    @Command(
        "ToggleLiquidPlace",
        description="Toggle Liquid Placement",
        version="v1.0.0"
    )
    class ToggleLiquidPlaceCommand(AbstractCommand["LiquidPlaceModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["liquidplace", "lp"]
            )

        async def execute(self, ctx):
            # Check if place_liquid is already enabled
            if not ctx.placeLiquids:
                ctx.placeLiquids = True
                await ctx.sendMessage("&aLiquid Place is Now Enabled!&f")
                await ctx.sendMessage("Use &cRed Wool&f to place &cStill Lava&f.")
                await ctx.sendMessage("Use &6Orange Wool&f to place &6Flowing Lava&f.")
                await ctx.sendMessage("Use &9Blue Wool&f to place &9Still Water&f.")
                await ctx.sendMessage("Use &bCyan Wool&f to place &bFlowing Water&f.")
            else:
                ctx.placeLiquids = False
                await ctx.sendMessage("&eLiquid Place is Now Disabled!&f")
                await ctx.sendMessage("You can now place blocks normally.")

            return None  # Nothing should be returned
