from obsidian.module import Module, AbstractModule, Dependency
from obsidian.commands import AbstractCommand, Command
from obsidian.cpe import CPEExtension
from obsidian.player import Player
from obsidian.errors import CommandError
from obsidian.blocks import AbstractBlock

from typing import Optional, cast


@Module(
    "BasicCuboid",
    description="Allows for basic cuboid commands.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class BasicCuboidModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    # Cuboid COmmand
    @Command(
        "Cuboid",
        description="Creates a cube of the selected block",
        version="v1.0.0"
    )
    class CuboidCommand(AbstractCommand["BasicCuboidModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["cuboid"],
                OP=True
            )

        async def execute(self, ctx: Player, block: Optional[AbstractBlock] = None):
            if ctx.worldPlayerManager is not None:
                world = ctx.worldPlayerManager.world
            else:
                raise CommandError("You are not in a world!")

            # Get first corner
            await ctx.sendMessage("&aPlease select the first corner")
            x1, y1, z1, _ = await ctx.getNextBlockUpdate()
            await ctx.sendMessage(f"&bFirst corner selected at ({x1}, {y1}, {z1})")

            # Get second corner
            await ctx.sendMessage("&aPlease select the second corner")
            x2, y2, z2, _ = await ctx.getNextBlockUpdate()
            await ctx.sendMessage(f"&bSecond corner selected at ({x2}, {y2}, {z2})")

            # If block is None, set it to the current block held.
            # If player does not support held block CPE, raise error
            if block is None:
                if ctx.supports(CPEExtension("HeldBlock", 1)):
                    block = cast(AbstractBlock, getattr(ctx, "heldBlock"))
                else:
                    raise CommandError("You must specify a block to use!")

            # Calculate Block Updates
            blockUpdates: dict[tuple[int, int, int], AbstractBlock] = {}
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    for z in range(min(z1, z2), max(z1, z2) + 1):
                        blockUpdates[(x, y, z)] = block

            # Apply block updates to server
            await world.bulkBlockUpdate(blockUpdates)

            # Send final message to player
            await ctx.sendMessage(f"&aCuboid of size {len(blockUpdates)} created!")
