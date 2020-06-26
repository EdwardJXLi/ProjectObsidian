import asyncio
from typing import Optional, List

from obsidian.packet import PacketManager
from obsidian.constants import Colour, ServerError, FatalError
from obsidian.log import Logger
from obsidian.network import NetworkHandler
from obsidian.module import ModuleManager


class Server:
    def __init__(
        self,
        address: str,
        port: int,
        name: str,
        motd: str,
        colour: bool = True,
        moduleBlacklist: List[str] = []
    ):
        self.address: str = address
        self.port: int = port
        self.name: str = name
        self.motd: str = motd
        self.server: Optional[asyncio.AbstractServer] = None
        self.moduleBlacklist: List[str] = moduleBlacklist
        self.protocolVersion: int = 0x07
        self.initialized = False

        # Init Colour
        if colour:
            Colour.init()

    async def init(self, *args, **kwargs):
        try:
            return await self._init(*args, **kwargs)
        except FatalError:
            # NOTE: e is already formatted with the type and stuff
            Logger.fatal(f"Fatal Error Detected. Stopping Server.", "main", printTb=False)
        except Exception as e:
            Logger.fatal(f"Error While Initializing Server - {type(e).__name__}: {e}", "server")

    async def _init(self):
        # Testing If Debug Is Enabled
        Logger.debug("Debug Is Enabled", module="init")
        Logger.verbose("Verbose Is Enabled", module="init")

        Logger.info(f"Initializing Server {self.name}", module="init")

        ModuleManager.initModules(blacklist=self.moduleBlacklist)

        Logger.info(f"{ModuleManager.numModules} Modules, {PacketManager.numPackets} Packets Initialized!", module="init")
        # Print Pretty List of All Modules
        Logger.info("Module List:", module="init")
        print(ModuleManager.generateTable())
        # Only print Packet List If Debug Enabled
        if Logger.DEBUG:
            Logger.debug("Packets List:", module="init")
            print(PacketManager.generateTable())

        # Printing Error If Error Occurs During Init
        if len(ModuleManager._errorList) != 0:
            Logger.warn("Some Module Files Failed To Load!", module="init")
            Logger.warn(f"Failed: {ModuleManager._errorList}", module="init")

        # Create Asyncio Socket Server
        # When new connection occurs, run callback _getConnHandler
        Logger.info(f"Setting Up Server {self.name}", module="init")
        self.server = await asyncio.start_server(self._getConnHandler(), self.address, self.port)

        self.initialized = True

    async def run(self):
        try:
            if self.initialized:
                # Start Server
                Logger.info(f"Starting Server {self.name} On {self.address} Port {self.port}")
                async with self.server as s:
                    await s.serve_forever()
            else:
                raise ServerError("Server Did Not Initialize. This May Be Because server.init() Was Never Called Or An Error Occurred While Initializing")
        except ServerError as e:
            Logger.fatal(f"Error While Starting Server - {type(e).__name__}: {e}", "server", printTb=False)
        except Exception as e:
            Logger.fatal(f"Error While Starting Server - {type(e).__name__}: {e}", "server")

    def _getConnHandler(self):  # -> Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]
        # Callback function on new connection
        async def handler(reader, writer):
            c = NetworkHandler(self, reader, writer)
            await c.initConnection()

        return handler
