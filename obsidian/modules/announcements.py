from __future__ import annotations

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player
from obsidian.mixins import Inject, InjectionPoint
from obsidian.config import AbstractConfig
from obsidian.server import Server
from obsidian.log import Logger

from dataclasses import dataclass, field
from threading import Thread
import asyncio
import time
import random


@Module(
    "Announcements",
    description="Sends periodic announcements in chat.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class AnnouncementsModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.AnnouncementsConfig)

    def postInit(self, **kwargs):
        # Check if the module is enabled
        if not self.config.enabled:
            Logger.info("The Announcements Library is disabled! Not starting module.", module="announcements")
            return

        Logger.debug("Injecting announcements thread into ProjectObsidian", module="announcements")

        @Inject(target=Server.run, at=InjectionPoint.BEFORE)
        async def startAnnouncementsThread(server_self, *args, **kwargs):
            server_self.serverAnnouncementsThread = Thread(target=AnnouncementsModule.announcementThread, args=(server_self, self.config))
            server_self.serverAnnouncementsThread.setName("AnnouncementsThread")
            server_self.serverAnnouncementsThread.setDaemon(True)
            Logger.debug(f"Starting announcements thread {server_self.serverAnnouncementsThread}", module="announcements")
            server_self.serverAnnouncementsThread.start()

    @staticmethod
    def announcementThread(server: Server, config: AnnouncementsModule.AnnouncementsConfig):
        # TODO: Change this to use a better async system in the future.

        # Keep track of message index
        messageIndex = 0

        # Start hot-loop for heartbeat
        while True:
            try:
                # Inject the message event into the existing event loop
                eventLoop = asyncio.new_event_loop()
                Logger.verbose(f"Creating new event loop {eventLoop} to send announcement.", module="announcements")
                eventLoop.run_until_complete(AnnouncementsModule.sendAnnouncement(server, config, messageIndex=messageIndex))
                messageIndex += 1

                # Sleep
                time.sleep(config.interval)
            except Exception as e:
                Logger.error(f"Unhandled exception in heartbeat thread - {type(e).__name__}: {e}", module="announcements", printTb=True)
                time.sleep(60)

    @staticmethod
    async def sendAnnouncement(server: Server, config: AnnouncementsModule.AnnouncementsConfig, messageIndex: int = 0):
        # Sanity Check messages
        if len(config.messages) <= 0:
            Logger.warn("No messages to send!", module="announcements")
            return

        # Get announcement message
        if config.random:
            message = random.choice(config.messages)
        else:
            message = config.messages[messageIndex % len(config.messages)]

        # Add prefix
        if isinstance(message, str):
            message = config.announcementPrefix + message
        else:
            for i in range(len(message)):
                message[i] = config.announcementPrefix + message[i]
        Logger.verbose(f"Sending announcement '{message}'", module="announcements")

        # Check if we should send the message
        if server.initialized and not server.stopping:
            if not (config.skipSendIfNoPlayers and len(server.playerManager.players) == 0):
                if config.globalMessage:
                    Logger.debug(f"Sending announcement '{message}' to all worlds", module="announcements")
                    await server.playerManager.sendGlobalMessage(message)
                else:
                    for worldName in config.worlds:
                        try:
                            world = server.worldManager.getWorld(worldName)
                        except NameError:
                            Logger.warn(f"World {worldName} does not exist!", module="announcements")
                            continue
                        Logger.debug(f"Sending announcement '{message}' to world {worldName}", module="announcements")
                        await world.playerManager.sendWorldMessage(message)
            else:
                Logger.verbose("Skipping announcement send due to no players online", module="announcements")
        else:
            Logger.verbose("Skipping announcement send due to server not being initialized or stopping", module="announcements")

    @Command(
        "ReloadAnnouncements",
        description="Reloads the Announcements Config",
        version="v1.0.0"
    )
    class ReloadAnnouncementsCommand(AbstractCommand["AnnouncementsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reloadannouncements"], OP=True)

        async def execute(self, ctx: Player):
            # Reload Config
            self.module.config.reload()

            # Send Response Back
            await ctx.sendMessage("&aAnnouncements API Config Reloaded!")

    @dataclass
    class AnnouncementsConfig(AbstractConfig):
        # Determine whether or not time announcements are enabled
        enabled: bool = True
        # Determine time between messages
        interval: int = 30
        # Determine where to send messages
        globalMessage: bool = True
        worlds: list[str] = field(default_factory=list)
        # Messages to send
        announcementPrefix: str = "&a[Announcement] "
        messages: list[str | list[str]] = field(default_factory=lambda: ["&aThis is a test message!", "&aThis is another test message!"])
        random: bool = False
        # Misc settings
        skipSendIfNoPlayers: bool = True
