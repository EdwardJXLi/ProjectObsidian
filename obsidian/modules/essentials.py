from typing import Optional
import inspect
import random
import math

from obsidian.module import Module, AbstractModule, ModuleManager, Dependency
from obsidian.constants import PY_VERSION, __version__
from obsidian.types import _formatUsername, _formatIp
from obsidian.player import Player
from obsidian.world import World
from obsidian.mapgen import AbstractMapGenerator, MapGeneratorStatus, MapGenerator
from obsidian.commands import AbstractCommand, Command, Commands, CommandManager, _typeToString
from obsidian.blocks import Blocks
from obsidian.errors import (
    ServerError,
    BlockError,
    CommandError,
    ConverterError
)
from obsidian.packet import (
    Packets,
)

# Load Command Helper
from obsidian.modules.core import CommandHelper


@Module(
    "Essentials",
    description="Central Module For Additional Obsidian Features.",
    author="Obsidian",
    version=__version__,
    dependencies=[Dependency("core")]
)
class EssentialsModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    #
    # MAP GENERATORS
    #

    @MapGenerator(
        "Random",
        description="Generates map out of random blocks",
        version="v1.0.0"
    )
    class RandomGenerator(AbstractMapGenerator["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args)

        # Generates a world of all random blocks
        def generateMap(self, sizeX: int, sizeY: int, sizeZ: int, seed: int, generationStatus: MapGeneratorStatus):
            # Initialize helper variables
            rand = random.Random(seed)
            allBlocks = Blocks.getAllBlockIds()

            # Generate Map
            mapData = bytearray()
            totalBlocks = sizeX * sizeY * sizeZ
            for i in range(totalBlocks):
                mapData.append(rand.choice(allBlocks))

                # Update status every 1000000 blocks
                if i % 1000000 == 0:
                    generationStatus.setStatus(i / totalBlocks, f"Placed {i} blocks...")

            generationStatus.setDone()
            return mapData

    #
    # COMMANDS
    #

    @Command(
        "Help",
        description="Generates a help command for users",
        version="v1.0.0"
    )
    class HelpCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["help", "commands", "cmds", "ls"])

        async def execute(self, ctx: Player, *, pageNumOrQuery: int | str = 1):
            # If command is not an int, assume its a command name and print help for that
            if isinstance(pageNumOrQuery, str):
                # Check if rightmost value is part of the module/command name or a page number
                # This will cause some edge cases where it will fail, but its better than nothing
                if pageNumOrQuery.rsplit(" ", 1)[-1].isnumeric():
                    query = pageNumOrQuery.rsplit(" ", 1)[0]
                    pageNum = int(pageNumOrQuery.rsplit(" ", 1)[1])
                else:
                    query = pageNumOrQuery
                    pageNum = 1
                # Check if query is 'all'
                if query.lower() == "all":
                    return await Commands.CommandList.execute(ctx)
                # Try to get query as a module
                try:
                    module = ModuleManager.SUBMODULE._convertArgument(ctx.server, query)
                except ConverterError:
                    module = None
                # Try to get query as a command
                try:
                    command = CommandManager.SUBMODULE._convertArgument(ctx.server, query)
                except ConverterError:
                    command = None
                # If both conditions match, raise a warning
                if module and command:
                    await ctx.sendMessage(f"&9[NOTICE] &f{query} is both a plugin name and a module name.")
                    await ctx.sendMessage("&9[NOTICE] &fTo get help as a command, please use &e/helpcmd")
                # Process First as a plugin
                if module:
                    return await Commands.HelpPlugin.execute(ctx, module=module, page=pageNum)
                if command:
                    return await Commands.HelpCmd.execute(ctx, cmd=command)
                raise CommandError(f"{query} is not a plugin or a command.")

            # Generate and Parse list of commands
            cmdList = CommandManager._commandDict
            # If user is not OP, filter out OP and Disabled commands
            if not ctx.opStatus:
                cmdList = {k: v for k, v in cmdList.items() if (not v.OP) and (v.NAME not in ctx.playerManager.server.config.disabledCommands)}

            # Alias pageOrQuery to just page
            page = pageNumOrQuery

            # Get information on the number of commands, pages, and commands per page
            numCommands = len(cmdList)  # This should never be zero as it should always count itself!
            commandsPerPage = 4
            numPages = math.ceil(numCommands / commandsPerPage)
            currentPage = page - 1

            # Check if user input was valid
            if page > numPages or page <= 0:
                raise CommandError(f"There are only {numPages} pages of commands!")

            # Get a list of commands registered
            commands = tuple(cmdList.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&eHelp Page {page}/{numPages}", color="&2"))
            output.append("&7Use /help [n] to get the nth page of help.&f")
            output.append("&7Use /help [query] for help on a plugin or command.&f")

            # Add command information
            for cmdName, cmd in commands[currentPage * commandsPerPage:currentPage * commandsPerPage + commandsPerPage]:
                helpMessage = f"&d[{cmdName}] &e/{cmd.ACTIVATORS[0]}"
                if cmd.OP:
                    helpMessage = "&4[OP] " + helpMessage
                if cmd.NAME in ctx.server.config.disabledCommands:
                    helpMessage = "&4[DISABLED] " + helpMessage
                if len(cmd.ACTIVATORS) > 1:
                    helpMessage += f" &7(Aliases: {', '.join(['/'+c for c in cmd.ACTIVATORS][1:])})"
                helpMessage += "&f"
                output.append(helpMessage)
                output.append(f"{cmd.DESCRIPTION}")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eTotal Commands: {numCommands}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "HelpPlugin",
        description="Gets help for commands from plugin",
        version="v1.0.0"
    )
    class HelpPluginCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["helpplugin", "pluginhelp"])

        async def execute(self, ctx: Player, module: AbstractModule, page: int = 1):
            # Generate and Parse list of commands
            cmdList = CommandManager._commandDict
            # Filter to commands from only one plugin
            cmdList = {k: v for k, v in cmdList.items() if v.MODULE == module}
            # If user is not OP, filter out OP and Disabled commands
            if not ctx.opStatus:
                cmdList = {k: v for k, v in cmdList.items() if (not v.OP) and (v.NAME not in ctx.playerManager.server.config.disabledCommands)}

            # Get information on the number of commands, pages, and commands per page
            numCommands = len(cmdList)
            commandsPerPage = 4
            numPages = math.ceil(numCommands / commandsPerPage)
            currentPage = page - 1

            # If there are no commands, return error
            if numCommands == 0:
                raise CommandError(f"Plugin {module.NAME} has no commands!")

            # Check if user input was valid
            if page > numPages or page <= 0:
                raise CommandError(f"There are only {numPages} pages of commands!")

            # Get a list of commands registered
            commands = tuple(cmdList.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&eHelp Page {page}/{numPages}", color="&2"))
            output.append(f"&d > Commands From {module.NAME}")

            # Add command information
            for cmdName, cmd in commands[currentPage * commandsPerPage:currentPage * commandsPerPage + commandsPerPage]:
                helpMessage = f"&d[{cmdName}] &e/{cmd.ACTIVATORS[0]}"
                if cmd.OP:
                    helpMessage = "&4[OP] " + helpMessage
                if cmd.NAME in ctx.server.config.disabledCommands:
                    helpMessage = "&4[DISABLED] " + helpMessage
                if len(cmd.ACTIVATORS) > 1:
                    helpMessage += f" &7(Aliases: {', '.join(['/'+c for c in cmd.ACTIVATORS][1:])})"
                helpMessage += "&f"
                output.append(helpMessage)
                output.append(f"{cmd.DESCRIPTION}")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&e{module.NAME} Commands: {numCommands}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "HelpCmd",
        description="Detailed help message for a specific command",
        version="v1.0.0"
    )
    class HelpCmdCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["helpcmd", "cmdhelp"])

        async def execute(self, ctx: Player, cmd: AbstractCommand):
            # Generate command output
            output = []

            # If command is an operator-only command and if user is not operator, return error
            if cmd.OP and not ctx.opStatus:
                raise CommandError("You do not have permission to view this command!")

            # Add Header
            output.append(CommandHelper.centerMessage(f"&eCommand Information: {cmd.NAME}", color="&2"))

            # Add Command Description
            if cmd.DESCRIPTION:
                output.append(f"&d[Description]&f {cmd.DESCRIPTION}")

            # Add Command Version
            if cmd.VERSION:
                output.append(f"&d[Version]&f {cmd.VERSION}")

            # If Command has a Documentation String, Add it on!
            if cmd.__doc__:
                output.append("&d[Documentation]")
                output += [line.strip() for line in cmd.__doc__.strip().splitlines()]

            # Generate Command Usage
            paramUsages = []
            # Loop through all arguments ** except for first ** (that is the ctx)
            for name, param in list(inspect.signature(cmd.execute).parameters.items())[1:]:
                paramStr = ""
                # Code recycled from parseargs
                # Normal Arguments (Nothing Special)
                if param.kind == param.POSITIONAL_OR_KEYWORD:
                    # Required arguments use ""
                    if param.default == inspect._empty:
                        paramStr += f"&b{name}"
                        if param.annotation != inspect._empty:
                            paramStr += f"&7({_typeToString(param.annotation)})"
                    # Optional arguments use []
                    else:
                        paramStr += f"&b[{name}"
                        if param.annotation != inspect._empty:
                            paramStr += f"&7({_typeToString(param.annotation)})"
                        paramStr += f"&b=&6{param.default}&b]"
                # Capture arguments use {}
                elif param.kind in (param.VAR_POSITIONAL, param.KEYWORD_ONLY):
                    paramStr += f"&b{{{name}..."
                    if param.annotation != inspect._empty:
                        paramStr += f"&7({_typeToString(param.annotation)})"
                    paramStr += "&b}"
                else:
                    # This should not really happen
                    raise ServerError(f"Unknown argument type {param.kind} while generating help command")

                # Add the formatted text to the list of other formatted texts
                paramUsages.append(paramStr)

            output += CommandHelper.formatList(paramUsages, initialMessage=f"&d[Usage] &e/{cmd.ACTIVATORS[0]} ", separator=" ", lineStart="&d ->")

            # Append list of aliases (if they exist)
            if len(cmd.ACTIVATORS) > 1:
                output += CommandHelper.formatList(cmd.ACTIVATORS[1:], initialMessage="&d[Aliases] &e", separator=", ", lineStart="&e", prefix="/")

            # If command is operator only, add a warning
            if cmd.OP:
                output.append("&4[NOTICE] &fThis Command Is For Operators and Admins Only!")

            # If command is disabled only, add a warning
            if cmd.NAME in ctx.server.config.disabledCommands:
                output.append("&4[NOTICE] &fThis Command Is DISABLED!")

            output.append(CommandHelper.centerMessage(f"&ePlugin: {cmd.MODULE.NAME} v. {cmd.MODULE.VERSION}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "CommandList",
        description="Generates a list of all commands",
        version="v1.0.0"
    )
    class CommandListCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["cmdlist", "commandlist", "listcmd", "listcmds", "helpall"])

        async def execute(self, ctx: Player, showAlias: bool = False):
            # Generate and Parse list of commands
            cmdList = CommandManager._commandDict
            # If user is not OP, filter out OP and Disabled commands
            if not ctx.opStatus:
                cmdList = {k: v for k, v in cmdList.items() if (not v.OP) and (v.NAME not in ctx.playerManager.server.config.disabledCommands)}

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage("&eListing All Commands", color="&2"))
            output.append("&7Use /help [query] for help on a plugin or command.&f")
            output.append("&7Use /cmdlist True  to show all command and aliases.&f")

            # Generate List of Commands
            if not showAlias:
                output += CommandHelper.formatList(cmdList.values(), processInput=lambda c: str(c.ACTIVATORS[0]), initialMessage="&e", separator=", ", lineStart="&e")
            else:
                fullCommandsList = []
                for command in cmdList.values():
                    for i, activator in enumerate(command.ACTIVATORS):
                        if i == 0:
                            fullCommandsList.append(f"&e{activator}")
                        else:
                            fullCommandsList.append(f"&6{activator}")
                output.append("&d[Showing all commands including aliases]")
                output += CommandHelper.formatList(fullCommandsList, initialMessage="&e", separator=", ", lineStart="&e")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eTotal Commands: {len(cmdList)}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ServerInfo",
        description="Detailed information about the server",
        version="v1.0.0"
    )
    class ServerInfoCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["server", "info", "about", "serverinfo", "aboutserver"])

        async def execute(self, ctx: Player):
            # Generate plugin output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&eServer Information: {ctx.server.name}", color="&2"))

            # Add Player Information
            output.append(f"&d[Server Name]&f {ctx.server.name}")
            output.append("&d[Server Software]&f Powered By: &a>> &dProject&5Obsidian &a<<")
            output.append(f"&d[Server Version]&f {__version__}")
            output.append(f"&d[Modules]&f {len(ModuleManager)} Modules Loaded. &7(/modules for more info)")
            if ctx.server.playerManager.maxSize is not None:
                output.append(f"&d[Players Online]&f {len(ctx.server.playerManager.players)}/{ctx.server.playerManager.maxSize} &7(/list for more info)")
            else:
                output.append(f"&d[Players Online]&f {len(ctx.server.playerManager.players)} &7(/list for more info)")
            output.append(f"&d[Worlds]&f {len(ctx.server.worldManager.worlds)} Worlds Loaded. &7(/worlds for more info)")
            output.append(f"&d[Commands]&f {len(CommandManager)} Commands Loaded. &7(/help for more info)")
            if ctx.server.supportsCPE:
                output.append("&d[Client Extensions]&f &aCPE Enabled! &7(/cpe for more info)")
            else:
                output.append("&d[Client Extensions]&f &6CPE Disabled!")
            output.append("&7Use /software to learn more about ProjectObsidian.")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eServer Software: ProjectObsidian {__version__}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "SoftwareInfo",
        description="Detailed information about ProjectObsidian, the server software",
        version="v1.0.0"
    )
    class SoftwareInfoCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["software", "obsidian", "softwareinfo", "obsidianinfo"])

        async def execute(self, ctx: Player):
            # Generate plugin output
            output = []

            # Add Header
            output.append("&2" + "=" * 53)
            # The extra space is to pad the extra missing
            output.append(f"{' ' * 31}&a>>>  &dProject&5Obsidian  &a<<<")
            output.append(CommandHelper.centerMessage(f"&bVersion: {__version__}&f  |  &a{PY_VERSION}", padCharacter="  "))
            output.append("&2" + "=" * 53)

            # Add additional information about the software
            output.append(f"&dSupports: c0.30 &f| &9Protocol: v7 &f| &aPlayers Online: {len(ctx.server.playerManager.players)}")

            # Add description
            output.append("&eProjectObsidian is an experimental heavily-modular")
            output.append("&eMinecraft Classic Server software written in 100% Python.")

            # Add github link
            output.append("&a[GitHub]&f https://github.com/EdwardJXLi/ProjectObsidian")

            # Add Disclaimer
            output.append("&c=== [Disclaimer] ===")
            output.append("&7ProjectObsidian is not affiliated with Microsoft or Mojang")
            output.append("&7and contains absolutely no source code from Minecraft.")

            # Add Footer
            output.append(CommandHelper.centerMessage("Created by RadioactiveHydra/EdwardJXLi", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "SoftwareVersion",
        description="Prints out version of ProjectObsidian",
        version="v1.0.0"
    )
    class SoftwareVersionCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["version"])

        async def execute(self, ctx: Player):
            # Send Version of ProjectObsidian
            await ctx.sendMessage(f"&dProject&5Obsidian &fv. &b{__version__} &fon &a{PY_VERSION}&f")

    @Command(
        "CPEList",
        description="Lists CPE Extensions supported by the client and server",
        version="v1.0.0"
    )
    class CPEListCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["cpe", "cpelist", "cpeinfo", "cpeextensions", "cpeext"])

        async def execute(self, ctx: Player):
            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage("&eCPE Extensions", color="&2"))
            output.append("&7Use /modules to see all the modules loaded on the server")

            # Add additional info on client and server
            output.append(f"&7Server Software: ProjectObsidian {__version__}")
            output.append(f"&7Client Software: {ctx.clientSoftware}")

            # Check if server supports CPE
            if ctx.server.supportsCPE:
                # Get CPE Extensions
                serverCpeExtensions = ctx.server.getSupportedCPE()

                # List CPE support on the server
                output += CommandHelper.formatList(serverCpeExtensions, processInput=lambda ext: f"{ext[0]}[v{ext[1]}]", initialMessage="&3[Server Supports]&6 ", separator=", ", lineStart="&6")

                # Check if client supports CPE
                if ctx.supportsCPE:
                    # Get full list of CPE Extensions
                    clientCpeExtensions = ctx._extensions

                    # List CPE support on the client
                    output += CommandHelper.formatList(clientCpeExtensions, processInput=lambda ext: f"{ext[0]}[v{ext[1]}]", initialMessage="&b[Client Supports]&e ", separator=", ", lineStart="&e")

                    # Get list of mutually supported CPE Extensions
                    mutualCpeExtensions = ctx.getSupportedCPE()

                    # List mutually supported CPE Extensions
                    output += CommandHelper.formatList(mutualCpeExtensions, processInput=lambda ext: f"{ext[0]}[v{ext[1]}]", initialMessage="&9[Mutual Support]&f ", separator=", ", lineStart="&f")
                else:
                    output.append("&b[Client Supports]&f &cCPE is not supported by your client!")
                    output.append("&9[Mutual Support]&f &cN/A")
            else:
                output.append("&3[Server Supports]&f &cCPE is disabled on this server!")
                output.append("&b[Client Supports]&f &cN/A")
                output.append("&9[Mutual Support]&f &cN/A")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eServer CPE Support: {ctx.server.supportsCPE}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "PluginsList",
        description="Lists all plugins/modules installed",
        version="v1.0.0"
    )
    class PluginsCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["plugins", "modules"])

        async def execute(self, ctx: Player, page: int = 1):
            # Get information on the number of modules, pages, and modules per page
            numModules = len(ModuleManager._moduleDict)  # This should never be zero as it should always count itself!
            modulesPerPage = 8
            numPages = math.ceil(numModules / modulesPerPage)
            currentPage = page - 1

            # Check if user input was valid
            if page > numPages or page <= 0:
                raise CommandError(f"There are only {numPages} pages of modules!")

            # Get a list of modules registered
            modules = tuple(ModuleManager._moduleDict.items())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&eHelp Page {page}/{numPages}", color="&2"))
            output.append("&7Use /plugins [n] to get the nth page of plugins.&f")
            output.append("&7Use /plugin [plugin] for additional info on a plugin.&f")

            # Add command information
            for moduleName, module in modules[currentPage * modulesPerPage:currentPage * modulesPerPage + modulesPerPage]:
                output.append(f"&e{moduleName}: &f{module.DESCRIPTION}")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eTotal Modules: {numModules}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "PluginInfo",
        description="Detailed help message for a specific plugin",
        version="v1.0.0"
    )
    class PluginInfoCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["plugin", "module", "plugininfo", "moduleinfo"])

        async def execute(self, ctx: Player, plugin: AbstractModule):
            # Generate plugin output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&ePlugin Information: {plugin.NAME}", color="&2"))

            # Add Plugin Description
            if plugin.DESCRIPTION:
                output.append(f"&d[Description]&f {plugin.DESCRIPTION}")

            # Add Plugin Author
            if plugin.AUTHOR:
                output.append(f"&d[Author]&f {plugin.AUTHOR}")

            # Add Plugin Version
            if plugin.VERSION:
                output.append(f"&d[Version]&f {plugin.VERSION}")

            # If Plugin has a Documentation String, Add it on!
            if plugin.__doc__:
                output.append("&d[Documentation]")
                output += [line.strip() for line in plugin.__doc__.strip().splitlines()]

            # If the plugin has dependencies, Add it on!
            if len(plugin.DEPENDENCIES):
                output.append("&d[Dependencies]")
                output += CommandHelper.formatList(
                    plugin.DEPENDENCIES,
                    processInput=lambda d: f"&b[{d.NAME} &7| v.{d.VERSION}&b]" if d.VERSION else f"&b[{d.NAME} &7| Any&b]",
                    separator=", ",
                    lineStart="")

            # Add # of Submodules
            output.append(f"&d[Submodules] &f{len(plugin.SUBMODULES)}")

            output.append(CommandHelper.centerMessage(f"&ePlugins Installed: {len(ModuleManager._moduleDict)}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListPlayers",
        description="Lists all players in specific world",
        version="v1.0.0"
    )
    class ListPlayersCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["list", "plist", "players", "listplayers"])

        async def execute(self, ctx: Player, world: Optional[World | Player] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    manager = ctx.worldPlayerManager
                else:
                    raise CommandError("You are not in a world!")
            elif isinstance(world, Player):
                if world.worldPlayerManager is not None:
                    manager = world.worldPlayerManager
                else:
                    raise CommandError("You are not in a world!")
            elif isinstance(world, World):
                manager = world.playerManager
            else:
                raise ServerError("bruh")

            # Get a list of players
            playersList = manager.getPlayers()

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&ePlayers Online: {len(set(playersList))}/{manager.world.maxPlayers}", color="&2"))
            output.append("&7Use /listall to see players in all worlds")
            output.append("&7Use /player [name] to see additional details about a player")

            # Generate Player List Output
            output += CommandHelper.formatList(playersList, processInput=lambda p: str(p.name), initialMessage="&e", separator=", ", lineStart="&e")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eWorld Name: {manager.world.name}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListAllPlayers",
        description="Lists all players in all worlds",
        version="v1.0.0"
    )
    class ListAllPlayersCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["listall", "pall", "online"])

        async def execute(self, ctx: Player):
            # Generate command output
            output = []

            # Add Header (Different depending on if server max size is set)
            if ctx.server.playerManager.maxSize is not None:
                output.append(
                    CommandHelper.centerMessage(
                        f"&ePlayers Online: {len(ctx.server.playerManager.players)}/{ctx.server.playerManager.maxSize} | Worlds: {len(ctx.server.worldManager.worlds)}",
                        color="&2"
                    )
                )
            else:
                output.append(CommandHelper.centerMessage(f"&ePlayers Online: {len(ctx.server.playerManager.players)} | Worlds: {len(ctx.server.worldManager.worlds)}", color="&2"))
            output.append("&7Use /player [name] to see additional details about a player")

            # Keep track of the number of worlds that were hidden
            numHidden = 0

            # Loop through all worlds and print their players
            for world in ctx.server.worldManager.getWorlds():
                # Get the worlds player list
                playersList = world.playerManager.getPlayers()

                # If there are no players, hide this server from the list
                if len(set(playersList)) == 0:
                    numHidden += 1
                    continue

                # Generate Player List Output
                output += CommandHelper.formatList(playersList, processInput=lambda p: str(p.name), initialMessage=f"&d[{world.name}] &e", separator=", ", lineStart="&e")

            # If any words were hidden, print notice
            if numHidden > 0:
                output.append(f"&7{numHidden} worlds were hidden due to having no players online.")
                output.append("&7Use /worlds to see all worlds.")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eServer Name: {ctx.server.name}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListStaff",
        description="Lists all online staff/operators",
        version="v1.0.0"
    )
    class ListStaffCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["staff", "liststaff", "listallstaff", "allstaff", "slist"])

        async def execute(self, ctx: Player):
            staffList = list(ctx.server.playerManager.getPlayers())

            # Generate command output
            output = []

            # Filter List to Staff Only
            playersList = [player for player in staffList if player.opStatus]

            # Add Header
            output.append(CommandHelper.centerMessage(f"&eStaff Online: {len(playersList)}", color="&2"))

            # Generate Player List Output
            output += CommandHelper.formatList(playersList, processInput=lambda p: str(p.name), initialMessage="&4", separator=", ", lineStart="&4")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eServer Name: {ctx.server.name}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "ListAllClients",
        description="Lists all player clients",
        version="v1.0.0"
    )
    class ListAllClientsCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["clients", "clientlist", "pclients"])

        async def execute(self, ctx: Player):
            # Generate command output
            output = []

            # Generate mapping of player -> client
            playerClients: dict[str, set[Player]] = {}
            for player in ctx.server.playerManager.getPlayers():
                client = player.clientSoftware
                if client not in playerClients:
                    playerClients[client] = set()
                playerClients[client].add(player)

            # Add Header
            output.append(CommandHelper.centerMessage(f"&ePlayers Online: {len(ctx.server.playerManager.players)} | Unique Clients: {len(playerClients)}", color="&2"))
            output.append("&7Use /player [name] to see additional details about a player")

            # Generate Player List Output
            for client, playersList in playerClients.items():
                output += CommandHelper.formatList(playersList, processInput=lambda p: str(p.name), initialMessage=f"&d[{client}] &e", separator=", ", lineStart="&e")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eServer Name: {ctx.server.name}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "PlayerInfo",
        description="Detailed information for a specific player",
        version="v1.0.0"
    )
    class PlayerInfoCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["player", "playerinfo", "pinfo"])

        async def execute(self, ctx: Player, player: Optional[Player] = None):
            # If no player is passed, use self
            if player is None:
                player = ctx

            # Generate plugin output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&ePlayer Information: {player.name}", color="&2"))

            # Add Player Information
            output.append(f"&d[Username]&f {player.name} &7({player.username})")
            output.append(f"&d[Joined World]&f {player.worldPlayerManager.world.name if player.worldPlayerManager else 'Unknown'}")
            output.append(f"&d[Coordinates]&f &7x:&f{player.posX//32} &7y:&f{player.posY//32} &7z:&f{player.posZ//32}")
            output.append(f"&d[Client Software]&f {player.clientSoftware}")
            output.append(f"&d[CPE Enabled]&f {player.supportsCPE} ({len(player._extensions)} extensions supported)")

            # Add self-only Player Information
            if player is ctx:
                output.append("&7(Only you can see the information below)")
                output.append(f"&d[Network Information]&f {player.networkHandler.ip}:{player.networkHandler.port}")
                output.append(f"&d[Authentication]&f {player.authenticated}")
                output.append(f"&d[Internal Player Id]&f {player.playerId}")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eServer Name: {ctx.server.name}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "PrivateMessage",
        description="Sends a private message to another user",
        version="v1.0.0"
    )
    class PrivateMessageCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["msg", "message", "tell", "whisper", "pm", "dm", "w"])

        async def execute(self, ctx: Player, recipient: Player, *, message: str):
            # Send Message
            await recipient.sendMessage(f"&7[{ctx.name} -> You]: {message}")
            await ctx.sendMessage(f"&7[You -> {recipient.name}]: {message}")

    @Command(
        "Teleport",
        description="Teleports player to coordinates",
        version="v1.0.0"
    )
    class TeleportCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["tp", "teleport"])

        async def execute(self, ctx: Player, posX: int, posY: int, posZ: int, yaw: int = 0, pitch: int = 0):
            # Check if player is in a world
            if ctx.worldPlayerManager is None:
                raise CommandError("You are not in a world!")

            # Check if location is within world
            try:
                ctx.worldPlayerManager.world.getBlock(posX, posY, posZ)
            except BlockError:
                raise CommandError("Coordinates are outside of the world!")

            # Set players location to world spawnpoint
            await ctx.setLocation(
                posX * 32 + 16,
                posY * 32 + 51,
                posZ * 32 + 16,
                yaw,
                pitch
            )

            await ctx.sendMessage("&aTeleported!")

    @Command(
        "TeleportPlayer",
        description="Teleports player to another player",
        version="v1.0.0"
    )
    class TeleportPlayerCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["tpplayer", "tpp", "teleportplayer"])

        async def execute(self, ctx: Player, player1: Player, player2: Optional[Player] = None):
            # Check who to teleport to who!
            if player2 is None:
                teleportWho = ctx
                teleportTo = player1
            else:
                teleportWho = player1
                teleportTo = player2

            # Check if both players are in the same world!
            if ctx.worldPlayerManager is None:
                raise CommandError("You are not in a world!")
            if teleportWho.worldPlayerManager is None:
                raise CommandError(f"{teleportWho.name} is not in a world!")
            if teleportTo.worldPlayerManager is None:
                raise CommandError(f"{teleportTo.name} is not in a world!")
            if teleportWho.worldPlayerManager.world != teleportTo.worldPlayerManager.world:
                raise CommandError(f"{teleportWho.name} and {teleportTo.name} are not in the same world!")

            # Check if the player teleporting to is within the world boundaries
            try:
                ctx.worldPlayerManager.world.getBlock(
                    teleportTo.posX // 32,
                    teleportTo.posY // 32,
                    teleportTo.posZ // 32
                )
            except BlockError:
                raise CommandError(f"{teleportTo.name} coordinates are outside the world!")

            # Teleport User
            await teleportWho.setLocation(
                teleportTo.posX,
                teleportTo.posY,
                teleportTo.posZ,
                teleportTo.posYaw,
                teleportTo.posPitch
            )

            await ctx.sendMessage("&aTeleported!")

    @Command(
        "Respawn",
        description="Respawns Self to Spawnpoint",
        version="v1.0.0"
    )
    class RespawnCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["respawn", "r"])

        async def execute(self, ctx: Player):
            # Check if player is in a world
            if ctx.worldPlayerManager is None:
                raise CommandError("You are not in a world!")

            # Set players location to world spawnpoint
            await ctx.setLocation(
                ctx.worldPlayerManager.world.spawnX,
                ctx.worldPlayerManager.world.spawnY,
                ctx.worldPlayerManager.world.spawnZ,
                ctx.worldPlayerManager.world.spawnYaw,
                ctx.worldPlayerManager.world.spawnPitch
            )

            await ctx.sendMessage("&aRespawned!")

    @Command(
        "ReloadWorld",
        description="Re-sends map data.",
        version="v1.0.0"
    )
    class ReloadWorldCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reload", "reloadworld", "wreload", "rw", "wr"])

        async def execute(self, ctx: Player):
            # Check if player is in a world
            if ctx.worldPlayerManager is None:
                raise CommandError("You are not in a world!")

            # Send world data again
            await ctx.reloadWorld()

    @Command(
        "JoinWorld",
        description="Joins another world",
        version="v1.0.0"
    )
    class JoinWorldCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["join", "joinworld", "wjoin", "jw", "wj"])

        async def execute(self, ctx: Player, world: World):
            await ctx.changeWorld(world)

    @Command(
        "ListWorlds",
        description="Lists All Loaded Worlds",
        version="v1.0.0"
    )
    class ListWorldsCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["worlds", "listworlds", "wlist", "lw", "wl"])

        async def execute(self, ctx: Player):
            # Get list of worlds
            worldList = list(ctx.server.worldManager.getWorlds())

            # Generate command output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&eWorlds Loaded: {len(worldList)}", color="&2"))
            output.append("&7Use /world [world] to see additional details about a world")

            # Generate Player List Output
            output += CommandHelper.formatList(worldList, processInput=lambda p: str(p.name), initialMessage="&e", separator=", ", lineStart="&e")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eServer Name: {ctx.server.name}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "WorldInfo",
        description="Detailed information for a specific world",
        version="v1.0.0"
    )
    class WorldInfoCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["world", "worldinfo", "winfo"])

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Generate plugin output
            output = []

            # Add Header
            output.append(CommandHelper.centerMessage(f"&eWorld Information: {world.name}", color="&2"))

            # Add World Information
            output.append(f"&d[Seed]&f {world.seed}")
            output.append(f"&d[World Size]&f &7x:&f{world.sizeX} &7y:&f{world.sizeY} &7z:&f{world.sizeZ}")
            output.append(f"&d[World Spawn]&f &7x:&f{world.spawnX//32} &7y:&f{world.spawnY//32} &7z:&f{world.spawnZ//32}")
            output.append(f"&d[World Generator]&f {world.generator.NAME if world.generator else 'N/A'}")
            output.append(f"&d[World Format]&f {world.worldFormat.NAME if world.worldFormat else 'N/A'}")
            output.append(f"&d[Read Only]&f {not world.canEdit}")
            output.append(f"&d[UUID]&f {world.worldUUID}")
            output.append(f"&d[Created By]&f {world.worldCreationPlayer} (Account: {world.worldCreationService})")
            output.append(f"&d[Map Generator]&f {world.mapGeneratorName} (Using {world.mapGeneratorSoftware})")
            output.append(f"&d[Time Created]&f {world.timeCreated}")

            # Add Footer
            output.append(CommandHelper.centerMessage(f"&eServer Name: {ctx.server.name}", color="&2"))

            # Send Message
            await ctx.sendMessage(output)

    @Command(
        "Seed",
        description="Get the world seed",
        version="v1.0.0"
    )
    class SeedCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["seed", "worldseed", "wseed"])

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Send Formatted World Seed
            await ctx.sendMessage(f"Seed for &e{world.name}&f: [&a{world.seed}&f]")

    @Command(
        "MOTD",
        description="Prints Message of the Day",
        version="v1.0.0"
    )
    class MOTDCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["motd"])

        async def execute(self, ctx: Player):
            await ctx.sendMOTD()

    @Command(
        "Ping",
        description="Pong!",
        version="v1.0.0"
    )
    class PingCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["ping"])

        async def execute(self, ctx: Player):
            # Send the ping packet, even though it doesn't really do anything
            await ctx.networkHandler.dispatcher.sendPacket(
                Packets.Response.Ping
            )
            await ctx.sendMessage("&aPong!")

    @Command(
        "Quit",
        description="Quits server with a message",
        version="v1.0.0"
    )
    class QuitCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["quit"])

        async def execute(self, ctx: Player, *, message: Optional[str] = None):
            await ctx.networkHandler.closeConnection("Quitting the Server...", notifyPlayer=True, chatMessage=message)

    #
    # COMMANDS (OPERATORS ONLY)
    #

    @Command(
        "Operator",
        description="Sets A Player As An Operator",
        version="v1.0.0"
    )
    class OPCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["op", "operator"], OP=True)

        async def execute(self, ctx: Player, name: str):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if user is already operator
            serverConfig = ctx.playerManager.server.config
            if username in serverConfig.operatorsList:
                raise CommandError(f"Player {username} is already an operator!")

            # Add Player To Operators List
            serverConfig.operatorsList.append(username)
            serverConfig.save()

            # Update User On Its OP Status
            if (player := ctx.playerManager.players.get(username, None)):
                await player.updateOperatorStatus()

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Added To Operators List")

    @Command(
        "DeOperator",
        description="Removes A Player As An Operator",
        version="v1.0.0"
    )
    class DEOPCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["deop", "deoperator"], OP=True)

        async def execute(self, ctx: Player, name: str):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if player is operator
            serverConfig = ctx.playerManager.server.config
            if username not in serverConfig.operatorsList:
                raise CommandError(f"Player {username} is not an operator!")

            # Remove Player From Operators List
            serverConfig.operatorsList.remove(username)
            serverConfig.save()

            # Update User On Its OP Status
            if (player := ctx.playerManager.players.get(username, None)):
                await player.updateOperatorStatus()

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Removed From Operators List")

    @Command(
        "ListOperators",
        description="List all operators",
        version="v1.0.0"
    )
    class ListOPCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["listop", "oplist"], OP=True)

        async def execute(self, ctx: Player):
            # Send formatted operators list
            await ctx.sendMessage(
                CommandHelper.formatList(
                    ctx.server.config.operatorsList,
                    initialMessage="&4[Operators] &e",
                    lineStart="&e", separator=", "
                )
            )

    @Command(
        "Kick",
        description="Kicks a user by name",
        version="v1.0.0"
    )
    class KickCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["kick", "kickuser"], OP=True)

        async def execute(self, ctx: Player, name: str, reason: str = "You Have Been Kicked By An Operator"):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if user is in list of players
            if not ctx.playerManager.players.get(username, None):
                raise CommandError(f"Player {username} is not online!")

            # Kick Player
            await ctx.playerManager.kickPlayer(username, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Kicked!")

    @Command(
        "KickIp",
        description="Kicks a user by ip",
        version="v1.0.0"
    )
    class KickIpCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["kickip"], OP=True)

        async def execute(self, ctx: Player, ip: str, reason: str = "You Have Been Kicked By An Operator"):
            # Check if IP is valid
            try:
                ip = _formatIp(ip)
            except TypeError:
                raise CommandError(f"Ip {ip} is not a valid Ip!")

            # Check if user with ip is connected
            if not ctx.playerManager.getPlayersByIp(ip):
                raise CommandError(f"No Players With Ip {ip} is online!")

            # Kick Player
            await ctx.playerManager.kickPlayerByIp(ip, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aKick Players With {ip}!")

    @Command(
        "Ban",
        description="Bans a user by name",
        version="v1.0.0"
    )
    class BanCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["ban", "banuser"], OP=True)

        async def execute(self, ctx: Player, name: str, *, reason: str = "You Have Been Banned By An Operator"):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if user is already banned
            serverConfig = ctx.server.config
            if username in serverConfig.bannedPlayers:
                raise CommandError(f"Player {username} is already banned!")

            # Add Player To Banned Users List
            serverConfig.bannedPlayers.append(username)
            serverConfig.save()

            # If Player Is Connected, Kick Player
            if ctx.playerManager.players.get(username, None):
                await ctx.playerManager.kickPlayer(username, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Banned!")

    @Command(
        "Pardon",
        description="Pardons a user by name",
        version="v1.0.0"
    )
    class PardonCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["pardon", "pardonuser"], OP=True)

        async def execute(self, ctx: Player, name: str):
            # Parse Name Into Username
            username = _formatUsername(name)

            # Check if player is banned
            serverConfig = ctx.server.config
            if username not in serverConfig.bannedPlayers:
                raise CommandError(f"Player {username} is not banned!")

            # Remove Player From Banned List
            serverConfig.bannedPlayers.remove(username)
            serverConfig.save()

            # Send Response Back
            await ctx.sendMessage(f"&aPlayer {username} Pardoned!")

    @Command(
        "BanIp",
        description="Bans an ip",
        version="v1.0.0"
    )
    class BanIpCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["banip"], OP=True)

        async def execute(self, ctx: Player, ip: str, *, reason: str = "You Have Been Banned By An Operator"):
            # Check if IP is valid
            try:
                ip = _formatIp(ip)
            except TypeError:
                raise CommandError(f"Ip {ip} is not a valid Ip!")

            # Check if Ip is already banned
            serverConfig = ctx.server.config
            if ip in serverConfig.bannedIps:
                raise CommandError(f"Ip {ip} is already banned!")

            # Add Ip To Banned Ips List
            serverConfig.bannedIps.append(ip)
            serverConfig.save()

            # If Ip Is Connected, Kick Players With That Ip
            if ctx.playerManager.getPlayersByIp(ip):
                await ctx.playerManager.kickPlayerByIp(ip, reason=reason)

            # Send Response Back
            await ctx.sendMessage(f"&aIp {ip} Banned!")

    @Command(
        "PardonIp",
        description="Pardons an Ip",
        version="v1.0.0"
    )
    class PardonIpCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["pardonip"], OP=True)

        async def execute(self, ctx: Player, ip: str):
            # Check if IP is valid
            try:
                ip = _formatIp(ip)
            except TypeError:
                raise CommandError(f"Ip {ip} is not a valid Ip!")

            # Check if Ip is Banned
            serverConfig = ctx.server.config
            if ip not in serverConfig.bannedIps:
                raise CommandError(f"Ip {ip} is not banned!")

            # Remove Ip From Banned Ips List
            serverConfig.bannedIps.remove(ip)
            serverConfig.save()

            # Send Response Back
            await ctx.sendMessage(f"&aIp {ip} Pardoned!")

    @Command(
        "BanList",
        description="List all banned players",
        version="v1.0.0"
    )
    class BanListCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["banlist", "listbans"], OP=True)

        async def execute(self, ctx: Player):
            # Send formatted banned list
            await ctx.sendMessage(
                CommandHelper.formatList(
                    ctx.server.config.bannedPlayers,
                    initialMessage="&4[Banned Players] &e",
                    lineStart="&e", separator=", "
                )
            )
            await ctx.sendMessage(
                CommandHelper.formatList(
                    ctx.server.config.bannedIps,
                    initialMessage="&4[Banned Ips] &e",
                    lineStart="&e", separator=", "
                )
            )

    @Command(
        "Say",
        description="Repeats message to all players in world",
        version="v1.0.0"
    )
    class SayCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["say", "repeat"], OP=True)

        async def execute(self, ctx: Player, *, msg: str):
            # Check if player is in a world
            if ctx.worldPlayerManager is None:
                raise CommandError("You are not in a world!")

            # Send message
            await ctx.worldPlayerManager.sendWorldMessage(msg)

    @Command(
        "SayAll",
        description="Repeats message to all players in all worlds",
        version="v1.0.0"
    )
    class SayAllCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["sayall", "repeatall"], OP=True)

        async def execute(self, ctx: Player, msg: str):
            # Send message
            await ctx.playerManager.sendGlobalMessage(msg)

    @Command(
        "Broadcast",
        description="Broadcasts message to all players in all worlds",
        version="v1.0.0"
    )
    class BroadcastCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["broadcast"], OP=True)

        async def execute(self, ctx: Player, *, msg: str):
            # Send message
            await ctx.playerManager.sendGlobalMessage(f"&4[Broadcast] &f{msg}")

    @Command(
        "DisableCommand",
        description="Disables a command",
        version="v1.0.0"
    )
    class DisableCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["disable", "disablecommand", "disablecmd"], OP=True)

        async def execute(self, ctx: Player, cmd: AbstractCommand):
            # Check if Command is already banned
            serverConfig = ctx.server.config
            if cmd.NAME in serverConfig.disabledCommands:
                raise CommandError(f"Command {cmd.NAME} is already disabled!")

            # Add Ip To Banned Ips List
            serverConfig.disabledCommands.append(cmd.NAME)
            serverConfig.save()

            # Send Response Back
            await ctx.sendMessage(f"&aCommand {cmd.NAME} Disabled!")

    @Command(
        "EnableCommand",
        description="Enables a command",
        version="v1.0.0"
    )
    class EnableCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["enable", "enablecommand", "enablecmd"], OP=True)

        async def execute(self, ctx: Player, cmd: AbstractCommand):
            # Check if command is disabled
            serverConfig = ctx.server.config
            if cmd.NAME not in serverConfig.disabledCommands:
                raise CommandError(f"Command {cmd.NAME} is already enabled!")

            # Remove Command from Disabled Commands List
            serverConfig.disabledCommands.remove(cmd.NAME)
            serverConfig.save()

            # Send Response Back
            await ctx.sendMessage(f"&aCommand {cmd.NAME} Enabled!")

    @Command(
        "DisabledCommandsList",
        description="List all disabled commands",
        version="v1.0.0"
    )
    class DisabledCommandsListCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["disabled", "disabledcommands", "listdisabled"], OP=True)

        async def execute(self, ctx: Player):
            # Send formatted disabled list
            await ctx.sendMessage(
                CommandHelper.formatList(
                    ctx.server.config.disabledCommands,
                    initialMessage="&4[Disabled Commands] &e",
                    lineStart="&e", separator=", "
                )
            )

    @Command(
        "ReloadConfig",
        description="Forces a reload of the config",
        version="v1.0.0"
    )
    class ReloadConfigCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reloadconfig"], OP=True)

        async def execute(self, ctx: Player):
            # Reload Config
            serverConfig = ctx.server.config
            serverConfig.reload()

            # Send Response Back
            await ctx.sendMessage("&aConfig Reloaded!")

    @Command(
        "SetWorldSpawn",
        description="Sets global default world spawn to current location.",
        version="v1.0.0"
    )
    class SetWorldSpawnCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["setworldspawn"], OP=True)

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Set the world spawn X, Y, Z, Yaw, and Pitch to current player
            world.spawnX = ctx.posX
            world.spawnY = ctx.posY
            world.spawnZ = ctx.posZ
            world.spawnYaw = ctx.posYaw
            world.spawnPitch = ctx.posPitch

            # Send Response Back
            await ctx.sendMessage("&aWorld Spawn Set To:")
            await ctx.sendMessage(f"&7x: &e{world.spawnX//32} &7y: &e{world.spawnY//32} &7z: &e{world.spawnZ//32} &7yaw: &e{world.spawnYaw} &7pitch: &e{world.spawnPitch}!")

    @Command(
        "SetWorldName",
        description="Sets the world name to a new value.",
        version="v1.0.0"
    )
    class SetWorldNameCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["worldname", "setworldname", "renameworld"], OP=True)

        async def execute(self, ctx: Player, newName: str):
            # Get player world
            if ctx.worldPlayerManager is not None:
                world = ctx.worldPlayerManager.world
            else:
                raise CommandError("You are not in a world!")

            # Set world name
            world.name = newName

            # Send Response Back
            await ctx.sendMessage(f"&aWorld Name Set To: {newName}! (Will be saved on next world save)")

    @Command(
        "ResetWorldSpawn",
        description="Sets global default world spawn to defaults.",
        version="v1.0.0"
    )
    class ResetWorldSpawnCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["resetspawn", "resetworldspawn"], OP=True)

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Set the world spawn X, Y, Z, Yaw, and Pitch to current player
            world.generateSpawnCoords(resetCoords=True)

            # Send Response Back
            await ctx.sendMessage("&aWorld Spawn Set To:")
            await ctx.sendMessage(f"&7x: &e{world.spawnX//32} &7y: &e{world.spawnY//32} &7z: &e{world.spawnZ//32} &7yaw: &e{world.spawnYaw} &7pitch: &e{world.spawnPitch}!")

    @Command(
        "ToggleWorldEdit",
        description="Toggles world editing.",
        version="v1.0.0"
    )
    class ToggleWorldEditCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["toggleedit", "togglemodify", "readonly"], OP=True)

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Toggle world edit status
            if world.canEdit:
                world.canEdit = False
                await ctx.sendMessage("&aWorld Editing Disabled!")
            else:
                world.canEdit = True
                await ctx.sendMessage("&aWorld Editing Enabled!")

    @Command(
        "ClearWorldMetadata",
        description="Clears all additional metadata in world",
        version="v1.0.0"
    )
    class ClearWorldMetadataCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["clearmetadata", "metadataclear"], OP=True)

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Confirm with user before clearing
            await ctx.sendMessage("&cAre you sure you want to clear all additional world metadata? (y/n)")
            resp = await ctx.getNextMessage()
            if resp.lower() != "y":
                await ctx.sendMessage("&cClearing metadata cancelled!")
                return

            # Empty the dictionary for metadata
            world.additionalMetadata = {}

            # Send Response Back
            await ctx.sendMessage("&aMetadata Cleared!")

    @Command(
        "ReloadWorlds",
        description="Scans world folder and reloads all worlds",
        version="v1.0.0"
    )
    class ReloadWorldsCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reloadworlds"], OP=True)

        async def execute(self, ctx: Player):
            # Reload Worlds
            if ctx.worldPlayerManager is not None:
                ctx.worldPlayerManager.world.worldManager.loadWorlds(reload=True)
            else:
                raise CommandError("You are not in a world!")

            # Send Response Back
            await ctx.sendMessage("&aWorlds Reloaded!")

    @Command(
        "SaveWorlds",
        description="Saves all worlds to disk",
        version="v1.0.0"
    )
    class SaveWorldsCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["save", "s", "saveall"], OP=True)

        async def execute(self, ctx: Player):
            # Save Worlds
            if ctx.worldPlayerManager is not None:
                # Get list of worlds (should only be used to notify player)
                worldList = list(ctx.server.worldManager.getWorlds())

                # Send world save message to entire server
                await ctx.playerManager.sendGlobalMessage("&aStarting Manual World Save!")
                await ctx.playerManager.sendGlobalMessage("&eWarning: The server may lag while saving!")
                await ctx.sendMessage(
                    CommandHelper.formatList(
                        worldList,
                        processInput=lambda p: str(p.name),
                        initialMessage="&eSaving These Worlds: ",
                        separator=", ", lineStart="&e"
                    )
                )

                ctx.worldPlayerManager.world.worldManager.saveWorlds()

                # Update server members on save
                await ctx.playerManager.sendGlobalMessage(f"&a{len(worldList)} Worlds Saved!")
            else:
                raise CommandError("You are not in a world!")

    @Command(
        "SaveWorld",
        description="Saves the current world to disk",
        version="v1.0.0"
    )
    class SaveWorldCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["saveworld", "savemap", "sw", "sm"], OP=True)

        async def execute(self, ctx: Player):
            # Save World
            if ctx.worldPlayerManager is not None:
                # Send world save message to entire world
                await ctx.worldPlayerManager.sendWorldMessage("&aStarting Manual World Save!")

                world = ctx.worldPlayerManager.world
                if world.persistent:
                    world.saveMap()
                else:
                    raise CommandError("World is not persistent. Cannot save!")

                # Send Update to entire world
                await ctx.worldPlayerManager.sendWorldMessage("&aWorld Saved!")
            else:
                raise CommandError("You are not in a world!")

    @Command(
        "StopServer",
        description="Stops the server",
        version="v1.0.0"
    )
    class StopCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["stop", "shutdown"], OP=True)

        async def execute(self, ctx: Player):
            await ctx.sendMessage("&4Stopping Server")
            # await ctx.playerManager.server.stop()

            # Server doesn't like it when it sys.exit()s mid await
            # So as a workaround, we disconnect the calling user first then stop the server using asyncstop
            # Which should launch the stop script on another event loop.
            # TODO: This works fine for now, but might cause issues later...
            await ctx.networkHandler.closeConnection("Server Shutting Down", notifyPlayer=True)

            ctx.server.asyncStop()

    @Command(
        "ForceStopServer",
        description="Force stops the server, without saving",
        version="v1.0.0"
    )
    class ForceStopCommand(AbstractCommand["EssentialsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["forcestop", "stopnosave"], OP=True)

        async def execute(self, ctx: Player):
            await ctx.sendMessage("&4Force Stopping Server")
            # await ctx.playerManager.server.stop(saveWorlds=False)

            # Server doesn't like it when it sys.exit()s mid await
            # So as a workaround, we disconnect the calling user first then stop the server using asyncstop
            # Which should launch the stop script on another event loop.
            # TODO: This works fine for now, but might cause issues later...
            await ctx.networkHandler.closeConnection("Server Shutting Down", notifyPlayer=True)

            ctx.server.asyncStop(saveWorlds=False)
