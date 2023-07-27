from __future__ import annotations

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player
from obsidian.mixins import Inject, InjectionPoint
from obsidian.constants import __version__
from obsidian.config import AbstractConfig
from obsidian.errors import ModuleError
from obsidian.server import Server
from obsidian.log import Logger

from dataclasses import dataclass
from threading import Thread
from typing import Optional
import time


@Module(
    "ClassiCubeAPI",
    description="Interacts with the ClassiCube API. Processes server heartbeat.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class ClassiCubeApiModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.ClassiCubeApiConfig)

    def postInit(self, **kwargs):
        # Check if the module is enabled
        if not self.config.enabled:
            Logger.info("The ClassiCube API support is disabled! Not starting module.", module="classiccubeapi")
            return

        # Check if the requests library is installed
        # TODO: Fix this code
        try:
            import requests
            Logger.verbose(f"Using requests version {requests.__version__}", module="classiccubeapi")
        except ImportError:
            raise ModuleError("The requests library is not installed! Please install it to use the ClassiCube API Module!")

        # Create heartbeat injector
        if self.config.heartbeat:
            Logger.debug("Injecting server heartbeat thread into ProjectObsidian", module="classiccubeapi")

            @Inject(target=Server.run, at=InjectionPoint.BEFORE)
            async def startHeartbeatThread(server_self, *args, **kwargs):
                server_self.serverHeartbeatThread = Thread(target=ClassiCubeApiModule.serverHeartbeat, args=(server_self, self.config))
                server_self.serverHeartbeatThread.setName("HeartbeatThread")
                server_self.serverHeartbeatThread.setDaemon(True)
                Logger.debug(f"Starting heartbeat thread {server_self.serverHeartbeatThread}", module="classiccubeapi")
                server_self.serverHeartbeatThread.start()

    @staticmethod
    def serverHeartbeat(server: Server, config: ClassiCubeApiModule.ClassiCubeApiConfig):
        import requests
        Logger.info("Starting server heartbeat", module="classiccubeapi")

        # Save server url information
        serverUrl = None

        # Start hot-loop for heartbeat
        while True:
            try:
                Logger.verbose("Sending heartbeat...", module="classiccubeapi")

                # Get url of classicube api heartbeat server
                url = f"{config.url}/{config.heartbeatUri}"

                # Generate Server Name
                if config.nameOverride:
                    serverName = config.nameOverride
                elif config.addSoftwareHeader:
                    serverName = f"[ProjectObsidian] {server.name}"
                else:
                    serverName = server.name

                # Generate Software Name
                if config.softwareOverride:
                    softwareName = config.softwareOverride
                elif not config.addSoftwareColour:
                    if config.includeSoftwareVersion:
                        softwareName = f"ProjectObsidian v. {__version__}"
                    else:
                        softwareName = "ProjectObsidian"
                else:
                    if config.includeSoftwareVersion:
                        softwareName = f"&dProject&5Obsidian &fv. &a{__version__}&f"
                    else:
                        softwareName = "&dProject&5Obsidian&f"

                # Calculate number of users
                if config.countByIp:
                    uniqueIps = set()
                    for player in server.playerManager.players.values():
                        uniqueIps.add(player.networkHandler.ip)
                    playerCount = len(uniqueIps)
                else:
                    playerCount = len(server.playerManager.players)

                # Generate parameters
                params = {
                    "name": serverName,
                    "port": server.port if config.portOverride is None else config.portOverride,
                    "users": playerCount,
                    "max": server.playerManager.maxSize or config.defaultMaxSize,
                    "public": config.public,
                    "salt": server.salt,
                    "software": softwareName,
                    "web": config.web,
                }

                # Send HTTP Request
                Logger.verbose(f"Sending heartbeat to {url} with params {params}", module="classiccubeapi")
                resp = requests.get(url, params=params)

                # Check if response is valid json
                Logger.verbose(f"Received response from server: {resp.text}", module="classiccubeapi")

                # Checking is response was successful
                if config.playUri in resp.text:
                    if serverUrl is None:
                        serverUrl = resp.text
                        Logger.info(f"Server is now online on ClassiCube! Play at {serverUrl}", module="classiccubeapi")
                    elif serverUrl != resp.text:
                        serverUrl = resp.text
                        Logger.warn(f"Server URL has changed! Play at {serverUrl}", module="classiccubeapi")
                else:
                    Logger.error(f"Server heartbeat failed! Response: {resp.text}", module="classiccubeapi")

                # Sleep
                time.sleep(config.heartbeatInterval)
            except Exception as e:
                Logger.error(f"Unhandled exception in heartbeat thread - {type(e).__name__}: {e}", module="classiccubeapi", printTb=True)
                time.sleep(60)

    @Command(
        "ReloadCCApi",
        description="Reloads the Classicube API Config",
        version="v1.0.0"
    )
    class ReloadCCApiCommand(AbstractCommand["ClassiCubeApiModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reloadccapi"], OP=True)

        async def execute(self, ctx: Player):
            # Reload Config
            self.module.config.reload()

            # Send Response Back
            await ctx.sendMessage("&aClassiCube API Config Reloaded!")

    @dataclass
    class ClassiCubeApiConfig(AbstractConfig):
        # Determine whether or not the ClassiCube API is enabled
        enabled: bool = True
        # Base settings
        url: str = "https://www.classicube.net"
        heartbeatUri: str = "server/heartbeat"
        playUri: str = "server/play"
        # Heartbeat Settings
        heartbeat: bool = True
        heartbeatInterval: int = 30
        # Server info settings
        public: bool = True
        web: bool = False
        # Player Count Settings
        defaultMaxSize: int = 1024
        countByIp: bool = False
        # Hostname and Port settings
        portOverride: Optional[int] = None
        # Server Name Settings
        addSoftwareHeader: bool = True
        nameOverride: Optional[str] = None
        # Server Software Settings
        includeSoftwareVersion: bool = True
        addSoftwareColour: bool = True
        softwareOverride: Optional[str] = None
