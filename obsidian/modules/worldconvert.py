from obsidian.module import Module, AbstractModule, Dependency
from obsidian.log import Logger
from obsidian.commands import Command, AbstractCommand, CommandError
from obsidian.world import WorldManager
from obsidian.worldformat import WorldFormatManager, WorldFormats
from obsidian.player import Player
from obsidian.constants import SERVER_PATH

from typing import Optional
from pathlib import Path


@Module(
    "World Converter",
    description="Helper commands for converting worlds between different formats",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class WorldConverterModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @Command(
        "ConvertWorld",
        description="Converts world from one format to another format.",
        version="v1.0.0"
    )
    class ConvertWorldCommand(AbstractCommand["WorldConverterModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["convertworld"], OP=True)

        async def execute(self, ctx: Player, worldFile: str, formatName: Optional[str] = None):
            from obsidian.modules.core import CommandHelper

            # If no world format is passed, use current world format.
            # Else, get the requested world format.
            if formatName:
                if formatName in WorldFormatManager:
                    newWorldFormat = WorldFormats[formatName]
                else:
                    raise CommandError(f"&cWorld format '{formatName}' does not exist!")
            else:
                if ctx.worldPlayerManager is not None:
                    newWorldFormat = ctx.worldPlayerManager.world.worldManager.worldFormat
                else:
                    raise CommandError("&cYou are not in a world!")

            # Get world format extension
            newFormatExt = "." + newWorldFormat.EXTENSIONS[0]

            # Get the world to be converted
            if ctx.server.config.worldSaveLocation:
                oldWorldPath = Path(SERVER_PATH, ctx.server.config.worldSaveLocation, worldFile)
                newWorldPath = Path(SERVER_PATH, ctx.server.config.worldSaveLocation, Path(worldFile).stem + newFormatExt)
            else:
                raise CommandError("&cworldSaveLocation in server configuration is not set!")

            # Check if world exists and if new world does not exist
            if not oldWorldPath.exists():
                raise CommandError(f"&cWorld '{oldWorldPath.name}' does not exist!")
            if newWorldPath.exists():
                await ctx.sendMessage(f"&cWorld '{newWorldPath.name}' already exists!")
                await ctx.sendMessage("Type &aoverwrite &fto overwrite it.")

                resp = await ctx.getNextMessage()

                if resp.lower() != "overwrite":
                    raise CommandError("&cWorld conversion cancelled!")

            # Detect type of old world format
            try:
                oldWorldFormat = WorldFormats.getWorldFormatFromExtension(oldWorldPath.suffix[1:])
            except KeyError:
                raise CommandError(f"&cWorld format '{oldWorldPath.suffix[1:]}' is not supported!")

            # Send user warning converting
            Logger.warn("User is about to convert world from one format to another!", module="format-convert")
            Logger.warn("This is a risky procedure! Use with caution!", module="format-convert")
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage("&e[WARNING]", colour="&4"))

            # Add Warning
            output.append("&c[WARNING]&f You are about to perform a conversion")
            output.append("&c[WARNING]&f from one world format to another!")
            output.append("&c[WARNING]&f Formats may not be compatible with each other,")
            output.append("&c[WARNING]&f and &cDATA MAY BE LOST IN THE PROCESS&f!")
            output.append("&c[WARNING]&f Always make backups before continuing!")
            output.append("Type &aacknowledge &fto continue")

            # Add Footer
            output.append(CommandHelper.centerMessage("&e[WARNING]", colour="&4"))

            # Send warning message
            await ctx.sendMessage(output)

            # Get next user input
            resp = await ctx.getNextMessage()

            # Check if user acknowledged
            if resp != "acknowledge":
                raise CommandError("&cWorld conversion cancelled!")

            # Give information on world to be converted
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage("&eWorld Format Conversion", colour="&2"))

            # Add World Information
            output.append(f"&3[Current World File]&f {oldWorldPath.name}")
            output.append(f"&3[Current World Format]&f {oldWorldFormat.NAME}")
            output.append(f"&3[Current Format Adapter Version]&f {oldWorldFormat.VERSION}")
            output.append(f"&b[New World File]&f {newWorldPath.name}")
            output.append(f"&b[New World Format]&f {newWorldFormat.NAME}")
            output.append(f"&b[New Format Adapter Version]&f {newWorldFormat.VERSION}")
            output.append("&7World Path Location")
            output.append(str(oldWorldPath.parent))
            output.append("Type &aacknowledge &fto continue")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eConverter Version: {self.VERSION}", colour="&2"))

            # Send Message
            await ctx.sendMessage(output)

            # Get next user input
            resp = await ctx.getNextMessage()

            # Check if user acknowledged
            if resp != "acknowledge":
                raise CommandError("&cWorld conversion cancelled!")

            # Start Conversion Process
            await ctx.sendMessage("&aStarting World Conversion Process...")
            oldWorldFile = open(oldWorldPath, "rb+")
            newWorldFile = open(newWorldPath, "wb+")
            oldWorldFile.seek(0)
            newWorldFile.seek(0)

            # Wrap in try except to catch errors
            try:
                # Create a temporary world manager
                await ctx.sendMessage("&aCreating Temporary World Manager...")
                tempWorldManager = WorldManager(ctx.server)

                # Load old world
                await ctx.sendMessage("&aLoading World from Old Format...")
                oldWorld = oldWorldFormat.loadWorld(oldWorldFile, tempWorldManager)

                # Save to new world
                await ctx.sendMessage("&aSaving World to New Format...")
                newWorldFormat.saveWorld(oldWorld, newWorldFile, tempWorldManager)
            except Exception as e:
                # Handle error by printing to chat and returning to user
                Logger.error(str(e), module="format-convert")
                await ctx.sendMessage("&cSomething went wrong while converting the world!")
                await ctx.sendMessage(f"&c{str(e)}")
                await ctx.sendMessage("&cPlease check the console for more information!")

            # Clean up open files
            await ctx.sendMessage("&aCleaning Up...")
            oldWorldFile.close()
            newWorldFile.flush()
            newWorldFile.close()

            # Send Final Messages
            await ctx.sendMessage("&aWorld Conversion Completed!")
            await ctx.sendMessage(f"&d{oldWorldPath.name} &a-> &d{newWorldPath.name}")
            await ctx.sendMessage("Use &a/reloadworlds &fto add the new world to the server!")


# TODO: Make WorldConverter work standalone!
