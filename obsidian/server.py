from __future__ import annotations

import asyncio
from typing import Optional, Any, List, Union
import traceback
import os
import sys

from obsidian.config import ServerConfig
from obsidian.packet import PacketManager, Packets
from obsidian.constants import Colour, InitError, MODULESFOLDER, SERVERPATH, ServerError, FatalError
from obsidian.log import Logger
from obsidian.network import NetworkHandler
from obsidian.module import ModuleManager
from obsidian.world import WorldManager
from obsidian.worldformat import WorldFormatManager
from obsidian.mapgen import MapGeneratorManager
from obsidian.commands import CommandManager
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
        self.ensureFiles: List[str] = []  # List of folders to ensure they exist
        self.protocolVersion: int = 0x07  # Minecraft Protocol Version
        self.initialized = False  # Flag Set When Everything Is Fully Loaded
        self.stopping = False  # Flag To Prevent Crl-C Spamming

        # Initialize Config, Depending On What Type It Is
        if config is None:
            self.config = ServerConfig()
        elif type(config) == str:
            self.config = ServerConfig(configPath=config)
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
            Logger.fatal(f"Fatal Error While Initializing Server - {type(e).__name__}: {e}", module="obsidian", printTb=False)
            Logger.fatal("===================== Traceback ======================", module="obsidian", printTb=False)
            Logger.log(f"{traceback.format_exc()}")
            Logger.fatal("==================== FATAL ERROR! ====================", module="obsidian", printTb=False)

    async def _init(self):
        # Testing If Debug Is Enabled
        Logger.debug("Debug Is Enabled", module="init")
        Logger.verbose("Verbose Is Enabled", module="init")
        Logger.info("Use '-d' and/or '-v' To Enable Debug Mode Or Verbose Mode", module="init")

        # Initializing Config
        Logger.info("Initializing Server Config", module="init")
        # Ensuring Config Path
        self._ensureFileStructure(os.path.dirname(self.config.configPath))
        # Initing Config
        self.config.init()

        # Setting Up File Structure
        Logger.info("Setting Up File Structure", module="init")
        if self.config.worldSaveLocation is not None:
            self.ensureFiles.append(MODULESFOLDER)
            self.ensureFiles.append(self.config.worldSaveLocation)
        self._ensureFileStructure(self.ensureFiles)

        Logger.info(f"Initializing Server {self.name}", module="init")
        # Load and Log Modules
        ModuleManager.initModules(blacklist=self.config.moduleBlacklist)

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
            Logger.debug(f"Blocks List:\n{BlockManager.generateTable()}", module="init")

        # Printing Error If Error Occurs During Init
        if len(ModuleManager._errorList) != 0:
            Logger.warn("Some Modules Files Failed To Load!\n", module="init")
            Logger.warn("!!! Failed Modules May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="init-module")
            Logger.warn(f"Failed: {ModuleManager._errorList}\n", module="init")
            Logger.askConfirmation()

        # Initialize WorldManager
        Logger.info("Initializing World Manager", module="init")
        self.worldManager = WorldManager(self, blacklist=self.config.worldBlacklist)
        Logger.info("Loading Worlds", module="init")
        self.worldManager.loadWorlds()

        # Initialize PlayerManager
        Logger.info("Initializing Player Manager", module="init")
        self.playerManager = PlayerManager(self, maxSize=self.config.serverMaxPlayers)

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
                pass

        return handler

    def _ensureFileStructure(self, folders: Union[str, List[str]]):
        Logger.debug(f"Ensuring Folders {folders}", module="init")
        # Check Type, If Str Put In List
        if type(folders) is not list:
            folders = [folders]
        # Ensure All Folders
        for folder in folders:
            folder = os.path.join(SERVERPATH, folder)
            if not os.path.exists(folder):
                Logger.debug(f"Creating Folder Structure {folder}", module="init")
                os.makedirs(folder)

    # Quick hack to run function in async mode no matter what
    def asyncstop(self, *args, **kwargs):
        Logger.debug("Trying to launch stop procedure in async", "stop-helper")
        try:
            eventLoop = asyncio.get_running_loop()
            Logger.debug("Existing Event Loop detected. Sending Stop Command!", "stop-helper")
            asyncio.run_coroutine_threadsafe(
                self.stop(),
                eventLoop
            )
        except RuntimeError:
            Logger.debug("No Running Event Loops Were Detected. Creating Stop Event Loop", "stop-helper")
            eventLoop = asyncio.new_event_loop()
            eventLoop.run_until_complete(self.stop())
            eventLoop.stop()

    async def stop(self):
        try:
            # Setting initialized to false to prevent multiple ctl-c
            if self.stopping:
                # Ignoring Repetitive Ctl-Cs
                return None

            if not self.initialized:
                Logger.info("Trying to shut down server that is not initialized!", module="server-stop")
                Logger.info("Skipping Shutdown Procedure", module="server-stop")
                sys.exit(0)
                return None

            # Preparing to stop server!
            Logger.info("Stopping Server...", module="server-stop")
            self.initialized = False
            self.stopping = True

            # Sending Disconnect Packet To All Server Members
            Logger.info("Sending Disconnect Packet To All Members", module="server-stop")
            await self.playerManager.sendGlobalPacket(
                Packets.Response.DisconnectPlayer,
                "(test) Disconnected: Server Shutting Down"
            )

            # Stopping Connection Handler
            Logger.info("Stopping Connection Handler Loop", module="server-stop")
            if self.server is not None:
                self.server.close()

            # Saving Worlds
            Logger.info("Saving All Worlds", module="server-stop")
            self.worldManager.saveWorlds()

            # Closing Worlds
            Logger.info("Closing All Worlds", module="server-stop")
            self.worldManager.closeWorlds()

            # Closing Server
            Logger.info("Terminating Process", module="server-stop")
            Logger.log("Goodbye!")
            sys.exit(0)
        except Exception as e:
            # Server Stop Failed! Last Ditch Attempt To Clean Up
            # Not Using Logger Incase Thats What Breaks It
            print(f"Error occurred while stopping server - {type(e).__name__}: {e}")
            print("Force Terminating Server")
            sys.exit(0)
