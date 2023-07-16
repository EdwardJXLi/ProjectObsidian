from __future__ import annotations

from obsidian.module import Module, AbstractModule, Dependency
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
    description="Interacts with the ClassiCube API. Processes server heartbeat and classicube authentication.",
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

        Logger.warn("The ClassiCube API Module is still WIP! Things may break!", module="classiccubeapi")

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

        # Start hot-loop for heartbeat
        while True:
            try:
                Logger.verbose("Sending heartbeat...", module="classiccubeapi")

                # Get url of classicube api heartbeat server
                url = f"{config.url}/{config.heartbeatUri}"

                # Generate parameters
                params = {
                    "name": server.name if config.nameOverride is None else config.nameOverride,
                    "port": server.port if config.portOverride is None else config.portOverride,
                    "users": len(server.playerManager.players),
                    "max": server.playerManager.maxSize or config.defaultMaxSize,
                    "public": config.public,
                    "salt": server.salt,
                    "software": f"&dProject&5Obsidian &av.{__version__}&f" if config.softwareOverride is None else config.softwareOverride,
                    "web": config.web,
                }

                # Send HTTP Request
                Logger.verbose(f"Sending heartbeat to {url} with params {params}", module="classiccubeapi")
                resp = requests.get(url, params=params)

                # Check if response is valid json
                Logger.verbose(f"Received response from server: {resp.text}", module="classiccubeapi")

                # Sleep
                time.sleep(config.heartbeatInterval)
            except Exception as e:
                Logger.error(f"Unhandled exception in heartbeat thread - {type(e).__name__}: {e}", module="classiccubeapi", printTb=True)
                time.sleep(10)

    @dataclass
    class ClassiCubeApiConfig(AbstractConfig):
        # Determine whether or not the ClassiCube API is enabled
        enabled: bool = True
        # Base settings
        url: str = "https://www.classicube.net"
        heartbeatUri: str = "server/heartbeat"
        # Heartbeat Settings
        heartbeat: bool = True
        heartbeatInterval: int = 60
        # Server info settings
        public: bool = True
        web: bool = False
        defaultMaxSize: int = 1024
        # Server info overrides
        nameOverride: Optional[str] = None
        portOverride: Optional[int] = None
        softwareOverride: Optional[str] = None
