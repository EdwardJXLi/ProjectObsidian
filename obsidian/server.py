from __future__ import annotations

import asyncio
from typing import Optional, Any
from pathlib import Path
import traceback
import sys
import os
import threading
import time

from obsidian.config import ServerConfig
from obsidian.packet import PacketManager, Packets
from obsidian.errors import InitError, ServerError, FatalError
from obsidian.log import Logger
from obsidian.network import NetworkHandler
from obsidian.module import ModuleManager
from obsidian.world import WorldManager
from obsidian.worldformat import WorldFormatManager
from obsidian.mapgen import MapGeneratorManager
from obsidian.commands import CommandManager
from obsidian.blocks import BlockManager
from obsidian.player import PlayerManager
from obsidian.constants import (
    managers_list,
    Colour,
    MODULESFOLDER,
    SERVERPATH
)


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
        self.protocolVersion: int = 0x07  # Minecraft Protocol Version
        self.initialized: bool = False  # Flag Set When Everything Is Fully Loaded
        self.stopping: bool = False  # Flag To Prevent Crl-C Spamming
        # These Values Have Getters
        self._server: Optional[asyncio.AbstractServer] = None  # Asyncio Server Object (initialized later)
        self._worldManager: Optional[WorldManager] = None  # World Manager Class (initialized later)
        self._playerManager: Optional[PlayerManager] = None  # Player Manager Class (initialized later)

        # Init Colour
        if colour:
            Colour.init()

        # Initialize Config, Depending On What Type It Is
        if config is None:
            self.config: ServerConfig = ServerConfig("server.json", hideWarning=True)
        elif isinstance(config, str):
            self.config: ServerConfig = ServerConfig(config)
        elif isinstance(config, ServerConfig):
            self.config: ServerConfig = config
        else:
            raise InitError(f"Unknown Config Type {type(config)}")

    async def init(self, *args, **kwargs):
        try:
            return await self._init(*args, **kwargs)
        except FatalError as e:
            # NOTE: e is already formatted with the type and stuff
            Logger.fatal("Fatal Error Detected. Stopping Server.", module="obsidian", printTb=False)
            Logger.fatal(f"{type(e).__name__}: {e}", module="main")
        except Exception as e:
            Logger.fatal("==================== FATAL ERROR! ====================", module="obsidian", printTb=False)
            Logger.fatal(f"Fatal Error While Initializing Server - {type(e).__name__}: {e}", module="obsidian", printTb=False)
            Logger.fatal("===================== Traceback ======================", module="obsidian", printTb=False)
            Logger._log(f"{traceback.format_exc()}")
            Logger.fatal("==================== FATAL ERROR! ====================", module="obsidian", printTb=False)

    async def _init(self):
        Logger.info(f"=== Initializing Server '{self.name}' ===", module="init")

        # Testing If Debug Is Enabled
        Logger.debug("Debug Is Enabled", module="init")
        Logger.verbose("Verbose Is Enabled", module="init")
        Logger.info("Use '-d' and/or '-v' To Enable Debug Mode Or Verbose Mode", module="init")

        # Initializing Config
        Logger.info("Initializing Server Config", module="init")
        # Ensuring Config Path
        Path(SERVERPATH, self.config.configPath).parent.mkdir(parents=True, exist_ok=True)
        # Initing Config
        self.config.init()

        # Set up logging with data from config
        if self.config.logBuffer < 0:
            raise FatalError("Log Buffer Size Cannot Be Negative")
        Logger.setBufferSize(self.config.logBuffer)

        # Setting Up File Structure
        Logger.info("Setting Up File Structure", module="init")
        Path(SERVERPATH, MODULESFOLDER).mkdir(parents=True, exist_ok=True)
        if self.config.worldSaveLocation is not None:
            Path(SERVERPATH, self.config.worldSaveLocation).mkdir(parents=True, exist_ok=True)

        # Print out SubModule Managers
        Logger.info("SubModule Managers Initiated!", module="init")
        Logger.info(f"Submodules Intitiated: [{', '.join([m.NAME for m in managers_list])}]", module="init")

        # Load and Log Modules
        Logger.info("Starting Module Initialization", module="init")
        ModuleManager.initModules(ignorelist=self.config.moduleIgnoreList, ensureCore=True)
        Logger.info("All Modules Initialized!!!", module="init")

        Logger.info(f"{ModuleManager.numModules} Modules Initialized", module="init")
        Logger.info(f"{PacketManager.numPackets} Packets Initialized", module="init")
        Logger.info(f"{BlockManager.numBlocks} Blocks Initialized", module="init")
        Logger.info(f"{CommandManager.numCommands} Commands Initialized", module="init")
        Logger.info(f"{MapGeneratorManager.numMapGenerators} Map Generators Initialized", module="init")

        # Print Pretty List of All Modules
        Logger.info(f"Module List:\n{ModuleManager.generateTable()}", module="init")
        # Only Print Packet And World Generators List If Debug Enabled
        if Logger.DEBUG:
            Logger.debug(f"Packets List:\n{PacketManager.generateTable()}", module="init")
            Logger.debug(f"World Formats List:\n{WorldFormatManager.generateTable()}", module="init")
            Logger.debug(f"Map Generators List:\n{MapGeneratorManager.generateTable()}", module="init")
            Logger.debug(f"Commands List:\n{CommandManager.generateTable()}", module="init")

        # Only Print Block List If Verbose Enabled (Very Big)
        if Logger.VERBOSE:
            Logger.verbose(f"Blocks List:\n{BlockManager.generateTable()}", module="init")

        # Printing Error If Error Occurs During Init
        if len(ModuleManager._error_list) != 0:
            Logger.warn("Some Modules Files Failed To Load!\n", module="init")
            Logger.warn("!!! Failed Modules May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="init-module")
            Logger.warn(f"Failed: {ModuleManager._error_list}\n", module="init")
            Logger.askConfirmation()

        # Initialize WorldManager
        Logger.info("Initializing World Manager", module="init")
        self._worldManager = WorldManager(self, ignorelist=self.config.worldIgnoreList)
        Logger.info("Loading Worlds", module="init")
        self.worldManager.loadWorlds()

        # Initialize PlayerManager
        Logger.info("Initializing Player Manager", module="init")
        self._playerManager = PlayerManager(self, maxSize=self.config.serverMaxPlayers)

        # Create Asyncio Socket Server
        # When new connection occurs, run callback _getConnHandler
        Logger.info(f"Setting Up Server {self.name}", module="init")
        self._server = await asyncio.start_server(self._getConnHandler(), self.address, self.port)

        self.initialized = True

    async def run(self):
        try:
            # Check if server is initialized and async server has started
            if self.initialized and self.server:
                # Start Server
                Logger.info(f"Starting Server {self.name} On {self.address} Port {self.port}", module="obsidian")
                await self.server.serve_forever()
            else:
                raise ServerError("Server Did Not Initialize. This May Be Because server.init() Was Never Called Or An Error Occurred While Initializing")
        except ServerError as e:
            Logger.fatal(f"Error While Starting Server - {type(e).__name__}: {e}", module="server", printTb=False)
        except Exception as e:
            Logger.fatal(f"Error While Starting Server - {type(e).__name__}: {e}", module="server")

    def _getConnHandler(self):  # -> Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]
        # Callback function on new connection
        async def handler(reader, writer):
            # Check if server is still initialized (Might be in shutdown procedure)
            if self.initialized:
                c = NetworkHandler(self, reader, writer)
                await c.initConnection()
            else:
                Logger.warn("Player tried to connect when server is not initialized. Dropping connection.", module="connection-handler")
                writer.close()

        return handler

    # Getters for server, worldManager, and playerManager
    @property
    def server(self) -> asyncio.AbstractServer:
        if self._server is None:
            raise ServerError("Server is not initialized! This May Be Because server.init() Was Never Called Or An Error Occurred While Initializing")
        return self._server

    @property
    def worldManager(self) -> WorldManager:
        if self._worldManager is None:
            raise ServerError("worldManager is not initialized! This May Be Because server.init() Was Never Called Or An Error Occurred While Initializing")
        return self._worldManager

    @property
    def playerManager(self) -> PlayerManager:
        if self._playerManager is None:
            raise ServerError("playerManager is not initialized! This May Be Because server.init() Was Never Called Or An Error Occurred While Initializing")
        return self._playerManager

    # Quick hack to run function in async mode no matter what
    def asyncstop(self, *args, **kwargs):
        Logger.debug("Trying to launch stop procedure in async", "server-stop")
        try:
            # Inject the stop event into the existing event loop
            eventLoop = asyncio.get_running_loop()
            Logger.debug("Existing Event Loop detected. Sending Stop Command!", "server-stop")
            asyncio.run_coroutine_threadsafe(
                self.stop(),
                eventLoop
            )
        except RuntimeError:
            Logger.debug("No Running Event Loops Were Detected. Creating Stop Event Loop", "server-stop")
            eventLoop = asyncio.new_event_loop()
            eventLoop.run_until_complete(self.stop())
            eventLoop.stop()

        # Start a new thread with a dead mans switch to kill the server if it takes too long to stop
        def deadMansProcess():
            time.sleep(30)
            Logger.warn("Stop procedure is taking a long time. For stopping in 30 seconds", "server-stop")
            Logger.warn("DATA MAY BE LOST!", "server-stop")
            time.sleep(30)
            Logger.fatal("FORCE STOPPING SERVER!", "server-stop", printTb=False)
            os._exit(-1)
        Logger.debug("Starting Dead Mans Thread", "server-stop")
        threading.Thread(target=deadMansProcess, daemon=True).start()

    async def stop(self):
        try:
            # Setting initialized to false to prevent multiple ctl-c
            if self.stopping:
                # Ignoring Repetitive Ctl-Cs
                return None

            if not self.initialized:
                Logger.info("Trying to shut down server that is not initialized!", module="server-stop")
                Logger.info("Skipping Shutdown and Cleanup Procedure", module="server-stop")
                sys.exit(0)

            # Preparing to stop server!
            Logger.info("Stopping Server...", module="server-stop")
            self.initialized = False
            self.stopping = True

            if self.playerManager:
                # Send message to all players
                Logger.info("Sending Disconnect Message To All Players", module="server-stop")
                await self.playerManager.sendGlobalMessage("&cServer Shutting Down")

                # Kick All Logged On Players
                Logger.info("Kicking All Logged On Players", module="server-stop")
                for player in list(self.playerManager.players.values()):
                    await player.networkHandler.closeConnection("Server Shutting Down", notifyPlayer=True)

                # Sending Disconnect Packet To Remaining Server Members
                Logger.info("Sending Disconnect Packet To Remaining Members", module="server-stop")
                await self.playerManager.sendGlobalPacket(
                    Packets.Response.DisconnectPlayer,
                    "Disconnected: Server Shutting Down"
                )
            else:
                Logger.warn("Player Manager was not initialized properly. Skipping disconnect packet.")

            # Stopping Connection Handler
            Logger.info("Stopping Connection Handler Loop", module="server-stop")
            if self.server is not None:
                self.server.close()

            # Managing worlds
            if self.worldManager:
                # Saving Worlds
                Logger.info("Saving All Worlds", module="server-stop")
                self.worldManager.saveWorlds()

                # Closing Worlds
                Logger.info("Closing All Worlds", module="server-stop")
                self.worldManager.closeWorlds()
            else:
                Logger.warn("Server Manager was not initialized properly. Skipping world save.")

            # Flushing Log Buffer
            if Logger.LOGFILE is not None:
                Logger.LOGFILE.flush()

            # Closing Server
            Logger.info("Terminating Process", module="server-stop")
            Logger._log("Goodbye!")
            sys.exit(0)

            # If server fails to stop, force terminate
            Logger.fatal("Server Failed To Terminate! Force Terminating Server", module="server-stop", printTb=False)
            os._exit(-1)
        except Exception as e:
            # Server Stop Failed! Last Ditch Attempt To Clean Up
            # Not Using Logger Incase Thats What Breaks It
            print(f"Error occurred while stopping server - {type(e).__name__}: {e}")
            print("Force Terminating Server")
            sys.exit(0)
