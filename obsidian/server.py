from __future__ import annotations

import asyncio
from typing import Optional, Any

from obsidian.config import ServerConfig
from obsidian.packet import PacketManager
from obsidian.constants import Colour, InitError, ServerError, FatalError
from obsidian.log import Logger
from obsidian.network import NetworkHandler
from obsidian.module import ModuleManager
from obsidian.world import WorldManager
from obsidian.worldformat import WorldFormatManager
from obsidian.mapgen import MapGeneratorManager
from obsidian.blocks import BlockManager
from obsidian.player import PlayerManager


class Server:
    def __init__(
        self,
        address: str,
        port: int,
        name: str,
        motd: str,
        colour: bool = True,
        # Configuration Information. Could Be Either:
        # None - Use Default Values
        # Str - Pass In Configuration File Location
        # ServerConfig - Pass In Already Parsed Server Configuration Class
        config: Any[None, str, ServerConfig] = None
    ):
        self.address: str = address  # Ip Address Of Server
        self.port: int = port  # Port Number Of Server
        self.name: str = name  # Name Of Server
        self.motd: str = motd  # Message Of The Day
        self.server: Optional[asyncio.AbstractServer] = None  # Asyncio Server Object
        self.worldManager: Optional[WorldManager] = None  # World Manager Class
        self.playerManager: Optional[PlayerManager] = None  # Player Manager CLass
        self.config: Optional[ServerConfig] = None  # Server Config Class; To Be Init Later
        self.protocolVersion: int = 0x07  # Minecraft Protocol Version
        self.initialized = False  # Flag Set When Everything Is Fully Loaded

        # Initialize Config, Depending On What Type It Is
        if config is None:
            self.config = ServerConfig()
        elif type(config) == str:
            self.config = ServerConfig(configPath=config)
            self.config.init()
        elif type(config) == ServerConfig:
            self.config = config
        else:
            raise InitError(f"Unknown Config Type {type(config)}")

        # Init Colour
        if colour:
            Colour.init()

    async def init(self, *args, **kwargs):
        try:
            return await self._init(*args, **kwargs)
        except FatalError as e:
            # NOTE: e is already formatted with the type and stuff
            Logger.fatal("Fatal Error Detected. Stopping Server.", module="obsidian", printTb=False)
            Logger.fatal(f"{type(e).__name__}: {e}", module="main")
        except Exception as e:
            Logger.fatal("==================== FATAL ERROR! ====================", module="obsidian", printTb=False)
            Logger.fatal(f"Fatal Error While Initializing Server - {type(e).__name__}: {e}", module="obsidian")
            Logger.fatal("======================================================", module="obsidian", printTb=False)

    async def _init(self):
        # Testing If Debug Is Enabled
        Logger.debug("Debug Is Enabled", module="init")
        Logger.verbose("Verbose Is Enabled", module="init")
        Logger.info("Use '-d' and/or '-v' To Enable Debug Mode Or Verbose Mode", module="init")

        Logger.info(f"Initializing Server {self.name}", module="init")

        # Load and Log Modules
        ModuleManager.initModules(blacklist=self.config.moduleBlacklist)

        Logger.info(f"{ModuleManager.numModules} Modules Initialized", module="init")
        Logger.info(f"{PacketManager.numPackets} Packets Initialized", module="init")
        Logger.info(f"{BlockManager.numBlocks} Blocks Initialized", module="init")
        Logger.info(f"{MapGeneratorManager.numMapGenerators} Map Generators Initialized", module="init")

        # Print Pretty List of All Modules
        Logger.info("Module List:", module="init")
        print(ModuleManager.generateTable())
        # Only Print Packet And World Generators List If Debug Enabled
        if Logger.DEBUG:
            Logger.debug("Packets List:", module="init")
            print(PacketManager.generateTable())
            Logger.debug("World Formats List:", module="init")
            print(WorldFormatManager.generateTable())
            Logger.debug("Map Generators List:", module="init")
            print(MapGeneratorManager.generateTable())

        # Only Print Block List If Verbose Enabled (Very Big)
        if Logger.VERBOSE:
            Logger.debug("BLocks List:", module="init")
            print(BlockManager.generateTable())

        # Printing Error If Error Occurs During Init
        if len(ModuleManager._errorList) != 0:
            Logger.warn("Some Module Files Failed To Load!", module="init")
            Logger.warn(f"Failed: {ModuleManager._errorList}", module="init")

        # Initialize WorldManager
        Logger.info("Initializing World Manager", module="init")
        self.worldManager = WorldManager(self, blacklist=self.config.worldBlacklist)
        Logger.info("Loading Worlds", module="init")
        self.worldManager.loadWorlds()

        # Initialize PlayerManager
        Logger.info("Initializing Player Manager", module="init")
        self.playerManager = PlayerManager(self)

        # Create Asyncio Socket Server
        # When new connection occurs, run callback _getConnHandler
        Logger.info(f"Setting Up Server {self.name}", module="init")
        self.server = await asyncio.start_server(self._getConnHandler(), self.address, self.port)

        self.initialized = True

    async def run(self):
        try:
            if self.initialized:
                # Start Server
                Logger.info(f"Starting Server {self.name} On {self.address} Port {self.port}", module="obsidian")
                async with self.server as s:
                    await s.serve_forever()
            else:
                raise ServerError("Server Did Not Initialize. This May Be Because server.init() Was Never Called Or An Error Occurred While Initializing")
        except ServerError as e:
            Logger.fatal(f"Error While Starting Server - {type(e).__name__}: {e}", module="server", printTb=False)
        except Exception as e:
            Logger.fatal(f"Error While Starting Server - {type(e).__name__}: {e}", module="server")

    def _getConnHandler(self):  # -> Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]
        # Callback function on new connection
        async def handler(reader, writer):
            c = NetworkHandler(self, reader, writer)
            await c.initConnection()

        return handler
