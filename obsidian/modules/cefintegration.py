from obsidian.module import Module, AbstractModule, Dependency
from obsidian.modules.core import CommandHelper
from obsidian.player import Player
from obsidian.network import NetworkHandler
from obsidian.config import AbstractConfig
from obsidian.mixins import Inject, InjectionPoint, addAttribute
from obsidian.commands import AbstractCommand, Command, Commands
from obsidian.errors import ServerError
from obsidian.log import Logger

from dataclasses import dataclass
from typing import cast
import asyncio


@Module(
    "CEFIntegration",
    description="Provides integration with the CEF (Chrome Embedded Framework) plugin",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class CEFIntegrationModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.CEFIntegrationConfig)
        addAttribute(Player, "cefSupport", False)

    def postInit(self):
        super().postInit()

        # Helper function to process the /clients command
        async def processCEFClientsCommand(player: Player):
            message = await player.getNextMessage()

            # Override /clients command to return an mcgalaxy-style player list
            if message == "/clients":
                await Commands.CEFClients.execute(player)
            else:
                Logger.warn("CEF Plugin Did Not Send /clients Command!", module="cef-integration")

        # Check if user has CEF installed. If so, send CEF player list
        @Inject(target=NetworkHandler._processPostLogin, at=InjectionPoint.AFTER, additionalContext={"cefconfig": self.config})
        async def initCEFSupport(self, cefconfig: CEFIntegrationModule.CEFIntegrationConfig):
            # Since we are injecting, set type of self to Player
            self = cast(NetworkHandler, self)

            # Check if player is not None
            if self.player is None:
                raise ServerError("Trying To Process Post Login Actions Before Player Is Initialized!")

            # Check if player supports the TextHotKey Extension
            Logger.info(f"{self.connectionInfo} | Checking CEF Support", module="cef-integration")
            if " + cef" in self.player.clientSoftware:
                Logger.info(f"{self.connectionInfo} | Client Supports CEF! Waiting for /clients command", module="cef-integration")
                setattr(self.player, "cefSupport", True)

                # Asynchronously wait for the /clients command
                asyncio.create_task(processCEFClientsCommand(self.player))

                # Send warning about CEF Support
                # TODO: Finish CEF Support
                if cefconfig.sendWarning:
                    await self.player.sendMessage("&eWarning: CEF is only partially supported on ProjectObsidian!")
            else:
                Logger.info(f"{self.connectionInfo} | No CEF Support", module="cef-integration")

    @Command(
        "CEFClients",
        description="Lists CEF Clients",
        version="v1.0.0"
    )
    class CEFClientsCommand(AbstractCommand["CEFIntegrationModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["cefclients"])

        async def execute(self, ctx: Player):
            # Generate command output
            output = []

            # Generate mapping of player -> client
            playerClients: dict[str, set[Player]] = dict()
            for player in ctx.server.playerManager.getPlayers():
                client = player.clientSoftware
                if client not in playerClients:
                    playerClients[client] = set()
                playerClients[client].add(player)

            # Add Header
            output.append("&7Players using:")

            # Generate Player List Output
            for client, playersList in playerClients.items():
                output += CommandHelper.formatList(playersList, processInput=lambda p: str(p.name), initialMessage=f"&7  {client}: &f", separator=", ", lineStart="> ")

            # Send Message
            await ctx.sendMessage(output)

    # Config for CEF Integration hotkeys
    @dataclass
    class CEFIntegrationConfig(AbstractConfig):
        sendWarning: bool = True
