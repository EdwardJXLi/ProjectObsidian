from pathlib import Path
from os import listdir
from os.path import isfile

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.commands import AbstractCommand, Command
from obsidian.cpe import CPEExtension
from obsidian.log import Logger
from obsidian.player import Player
from obsidian.errors import CommandError
from obsidian.blocks import AbstractBlock
from obsidian.constants import MODULES_FOLDER

BUILDING_COMMANDS_FOLDER = str(Path(__file__).parent / "BuildingCommands")
FONTS_FOLDER = str(Path(BUILDING_COMMANDS_FOLDER, "fonts"))

from typing import Optional, cast


@Module(
    "BuildingCommands",
    description="Adds commands for building.",
    author="Rainb0wSkeppy",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class BuildingCommandsModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    # Cuboid Command
    @Command(
        "Cuboid",
        description="Creates a cube of the selected block",
        version="v1.0.0"
    )
    class CuboidCommand(AbstractCommand["BuildingCommandsModule"]):
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

            # Convert 1 to the minimum value, and 2 to the maximum value
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            z1, z2 = min(z1, z2), max(z1, z2)

            # Calculate Block Updates
            blockUpdates: dict[tuple[int, int, int], AbstractBlock] = {}
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    for z in range(z1, z2 + 1):
                        blockUpdates[(x, y, z)] = block

            # Apply block updates to server
            await world.bulkBlockUpdate(blockUpdates)

            # Send final message to player
            await ctx.sendMessage(f"&aCuboid of size {len(blockUpdates)} created!")

    # Replace Command
    @Command(
        "Replace",
        description="Replaces a block with another type of block in a cuboid",
        version="v1.0.0"
    )
    class ReplaceCommand(AbstractCommand["BuildingCommandsModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["replace", "re"],
                OP=True
            )

        async def execute(self, ctx: Player, from_: AbstractBlock, to: Optional[AbstractBlock] = None):
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
            if to is None:
                if ctx.supports(CPEExtension("HeldBlock", 1)):
                    to = cast(AbstractBlock, getattr(ctx, "heldBlock"))
                else:
                    raise CommandError("You must specify a block to replace with!")

            # Convert 1 to the minimum value, and 2 to the maximum value
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            z1, z2 = min(z1, z2), max(z1, z2)

            # Calculate Block Updates
            blockUpdates: dict[tuple[int, int, int], AbstractBlock] = {}
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    for z in range(z1, z2 + 1):
                        if world.getBlock(x, y, z).ID == from_.ID:
                            blockUpdates[(x, y, z)] = to

            # Apply block updates to server
            await world.bulkBlockUpdate(blockUpdates)

            # Get c
            cuboidSize = (x2 - x1 + 1) * (y2 - y1 + 1) * (z2 - z1 + 1)

            # Send final message to player
            await ctx.sendMessage(f"&aReplaced {len(blockUpdates)} blocks in a cuboid of size {cuboidSize}!")

    @Command(
        "Line",
        description="Creates a line of the selected block",
        version="v1.0.0"
    )
    class LineCommand(AbstractCommand["BuildingCommandsModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["line", "ln"],
                OP=True
            )

        async def execute(self, ctx: Player, block: Optional[AbstractBlock] = None):
            if ctx.worldPlayerManager is not None:
                world = ctx.worldPlayerManager.world
            else:
                raise CommandError("You are not in a world!")

            # Get first corner
            await ctx.sendMessage("&aPlease select the first point")
            x1, y1, z1, _ = await ctx.getNextBlockUpdate()
            await ctx.sendMessage(f"&bFirst point selected at ({x1}, {y1}, {z1})")

            # Get second corner
            await ctx.sendMessage("&aPlease select the second point")
            x2, y2, z2, _ = await ctx.getNextBlockUpdate()
            await ctx.sendMessage(f"&bSecond point selected at ({x2}, {y2}, {z2})")

            # If block is None, set it to the current block held.
            # If player does not support held block CPE, raise error
            if block is None:
                if ctx.supports(CPEExtension("HeldBlock", 1)):
                    block = cast(AbstractBlock, getattr(ctx, "heldBlock"))
                else:
                    raise CommandError("You must specify a block to use!")

            # Calculate Block Updates
            blockUpdates: dict[tuple[int, int, int], AbstractBlock] = {}

            # Calculate Bresenham's Line Algorithm
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            dz = abs(z2 - z1)

            xs = 1 if x1 < x2 else -1
            ys = 1 if y1 < y2 else -1
            zs = 1 if z1 < z2 else -1

            if dx >= dy and dx >= dz:
                p1 = 2 * dy - dx
                p2 = 2 * dz - dx

                while x1 != x2:
                    x1 += xs

                    if p1 >= 0:
                        y1 += ys
                        p1 -= 2 * dx

                    if p2 >= 0:
                        z1 += zs
                        p2 -= 2 * dx

                    p1 += 2 * dy
                    p2 += 2 * dz

                    blockUpdates[(x1, y1, z1)] = block
            elif dy >= dx and dy >= dz:
                p1 = 2 * dx - dy
                p2 = 2 * dz - dy

                while y1 != y2:
                    y1 += ys

                    if p1 >= 0:
                        x1 += xs
                        p1 -= 2 * dy

                    if p2 >= 0:
                        z1 += zs
                        p2 -= 2 * dy

                    p1 += 2 * dx
                    p2 += 2 * dz

                    blockUpdates[(x1, y1, z1)] = block
            else:
                p1 = 2 * dy - dz
                p2 = 2 * dx - dz

                while z1 != z2:
                    z1 += zs

                    if p1 >= 0:
                        y1 += ys
                        p1 -= 2 * dz

                    if p2 >= 0:
                        x1 += xs
                        p2 -= 2 * dz

                    p1 += 2 * dy
                    p2 += 2 * dx

                    blockUpdates[(x1, y1, z1)] = block

            # Apply block updates to server
            await world.bulkBlockUpdate(blockUpdates)

            # Send final message to player
            await ctx.sendMessage(f"&aLine of size {len(blockUpdates)} created!")

    # Write Command
    @Command(
        "Write",
        description="Writes text using the selected block",
        version="v1.0.0"
    )
    class WriteCommand(AbstractCommand["BuildingCommandsModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["write", "writetext"],
                OP=True
            )

            self.noMonoFonts = {}
            self.noMonoWidth = {}
            self.monoFonts   = {}
            
            # Check if the PIL library is installed
            # TODO: Fix this code
            try:
                import PIL
                import PIL.Image

                globals()["PIL"] = PIL

                self.enableTextDrawing = True
                self.loadAllFonts()
            
                Logger.verbose(f"Using PIL version {PIL.Image.__version__}", module="buildingcommands")
            except ImportError:
                self.enableTextDrawing = False
                Logger.warning("The PIL library is not installed! Please install it to use /Write!")

        def loadFont(self, isMonospaced: bool, fontSize: int, path: str):
            if isMonospaced:
                Logger.verbose(f"Loaded monospace font {path}, size {fontSize}", module="buildingcommands")
                
                self.monoFonts[fontSize] = PIL.Image.open(path)
            else:
                Logger.verbose(f"Loaded non-monospace font {path}, size {fontSize}", module="buildingcommands")
                
                self.noMonoFonts[fontSize] = PIL.Image.open(path)
                self.noMonoWidth[fontSize] = []
                
                for i in range(256):
                    char_x = (i %  16) * fontSize
                    char_y = (i // 16) * fontSize

                    width = 0

                    for x in range(fontSize):
                        isColumnEmpty = True

                        for y in range(fontSize):
                            if self.noMonoFonts[fontSize].getpixel((char_x + x, char_y + y)) == 1:
                                isColumnEmpty = False

                        if not isColumnEmpty:
                            width = x + 1
                    
                    Logger.verbose(f"Character #{i} is {width} pixels wide", module="buildingcommands")
                    self.noMonoWidth[fontSize].append(width)
        
        def loadAllFonts(self):
            for i in listdir(FONTS_FOLDER):
                p = str(Path(FONTS_FOLDER, i))
                
                if isfile(p):
                    if i.startswith("mono"):
                        fontSize = int(i.partition("mono")[2].rpartition(".png")[0])
                        self.loadFont(True, fontSize, p)
                        
                    elif i.startswith("nomono"):
                        fontSize = int(i.partition("nomono")[2].rpartition(".png")[0])
                        self.loadFont(False, fontSize, p)

        def unloadFont(self, isMonospaced: bool, fontSize: int):
            if isMonospaced:
                self.monoFonts[fontSize].close()
                del self.monoFonts[fontSize]
            elif isMonospaced:
                self.noMonoFonts[fontSize].close()
                del self.noMonoFonts[fontSize]
                del self.noMonoWidth[fontSize]

        def unloadAllFonts(self):
            for i in self.monoFonts:
                self.unloadFont(True, i)
                
            for i in self.noMonoFonts:
                self.unloadFont(False, i)

        async def execute(self, ctx: Player, isMonospaced: bool, fontSize: int, text: str):
            if not self.enableTextDrawing:
                raise CommandError(f"Text drawing is disabled because the PIL module is not installed!")
            
            block = None
            
            if ctx.worldPlayerManager is not None:
                world = ctx.worldPlayerManager.world
            else:
                raise CommandError("You are not in a world!")

            if isMonospaced:
                if fontSize not in self.monoFonts:
                    raise CommandError(f"{fontSize} is not a valid font size!")
            else:
                if fontSize not in self.noMonoFonts:
                    raise CommandError(f"{fontSize} is not a valid font size!")

            # Get bottom left corner
            await ctx.sendMessage("&aPlease select the bottom left corner")
            x1, y1, z1, _ = await ctx.getNextBlockUpdate()
            await ctx.sendMessage(f"&bBottom left corner selected at ({x1}, {y1}, {z1})")
            
            # Get direction
            await ctx.sendMessage("&aPlease select the direction")
            x2, y2, z2, _ = await ctx.getNextBlockUpdate()
            await ctx.sendMessage(f"&bDirection selected at ({x2}, {y2}, {z2})")

            if x2 - x1 > abs(z2 - z1):
                dx = 1
                dz = 0
            elif z2 - z1 > abs(x2 - x1):
                dx = 0
                dz = 1
            elif x1 - x2 > abs(z2 - z1):
                dx = -1
                dz = 0
            elif z1 - z2 > abs(x2 - x1):
                dx = 0
                dz = -1
            else:
                raise CommandError("No direction was specified!")

            # If block is None, set it to the current block held.
            # If player does not support held block CPE, raise error
            if block is None:
                if ctx.supports(CPEExtension("HeldBlock", 1)):
                    block = cast(AbstractBlock, getattr(ctx, "heldBlock"))
                else:
                    raise CommandError("You must specify a block to use!")

            # Calculate Block Updates
            blockUpdates: dict[tuple[int, int, int], AbstractBlock] = {}

            if isMonospaced:
                for i in text:
                    char = ord(i)
                    char_x = (char %  16) * fontSize // 2
                    char_y = (char // 16) * fontSize
                    
                    for x in range(fontSize // 2):
                        for y in range(fontSize):
                            if self.monoFonts[fontSize].getpixel((char_x + x, char_y + y)) == 1:
                                blockUpdates[(x1, y1 + fontSize - y - fontSize // 6 - 1, z1)] = block

                        x1 += dx
                        z1 += dz
            else:
                for i in text:
                    char = ord(i)
                    char_x = (char %  16) * fontSize
                    char_y = (char // 16) * fontSize

                    for x in range(self.noMonoWidth[fontSize][char]):
                        for y in range(fontSize):
                            if self.noMonoFonts[fontSize].getpixel((char_x + x, char_y + y)) == 1:
                                blockUpdates[(x1, y1 + fontSize - y - fontSize // 6 - 1, z1)] = block
        
                        x1 += dx
                        z1 += dz
                    x1 += dx
                    z1 += dz

            # Apply block updates to server
            await world.bulkBlockUpdate(blockUpdates)
