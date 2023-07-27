from obsidian.module import Module, AbstractModule, Dependency
from obsidian.mixins import Override
from obsidian.world import World
from obsidian.player import Player, WorldPlayerManager
from obsidian.commands import Command, AbstractCommand
from obsidian.errors import ServerError
from obsidian.config import AbstractConfig

from typing import cast, Optional, Callable, Awaitable
from dataclasses import dataclass
import re


@Module(
    "BetterChat",
    description="Adds Quality-of-life Chat Features",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class BetterChatModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.BetterChatConfig)
        self.textWrapConfig = self.initConfig(self.TextWrapConfig, name="textwrap.json")
        self.playerPingConfig = self.initConfig(self.PlayerPingConfig, name="playerping.json")

        # Sanity check maximum line length
        if self.textWrapConfig.maximumLineLength > 64:
            raise ValueError("Maximum line length cannot be greater than 64!")

    def initTextWrap(self):
        # Create reference to textWrapConfig
        textWrapConfig = self.textWrapConfig

        # Override the original processPlayerMessage method
        @Override(target=WorldPlayerManager.processPlayerMessage)
        async def processLinedWrappedMessage(
            self,
            player: Optional[Player],
            message: str,
            world: None | str | World = None,
            globalMessage: bool = False,
            ignoreList: set[Player] = set(),
            messageHandlerOverride: Optional[Callable[..., Awaitable]] = None
        ):
            # Since we are injecting, set type of self to World
            self = cast(WorldPlayerManager, self)

            # Figure out which message handler to use
            if messageHandlerOverride:
                sendMessage = messageHandlerOverride
            elif globalMessage:
                sendMessage = self.playerManager.sendGlobalMessage
            else:
                sendMessage = self.sendWorldMessage

            # Intelligently split message into multiple lines
            words = message.split(" ")

            # Generate Message Header
            messageBuffer = self.playerManager.generateMessage("", author=player, world=world)

            # Keep track of previous colors
            previousColor = "&f"

            # Keep track of lines sent
            linesSent = 0

            # Loop through all words to generate message
            while words:
                # Add word to buffer
                messageBuffer += words.pop(0) + " "

                # Check if the message buffer is too long. If so, truncate it.
                if len(messageBuffer) > textWrapConfig.maximumLineLength:
                    # Strip the extra space at the end of the message
                    messageBuffer = messageBuffer[:-1]
                    # Inject the overflow message back into the queue
                    words.insert(0, messageBuffer[textWrapConfig.maximumLineLength:])
                    messageBuffer = messageBuffer[:textWrapConfig.maximumLineLength]
                    # If we want to warn the player about the overflow, do so
                    if textWrapConfig.warnOnMessageOverflow and player:
                        await player.sendMessage("&e[NOTICE] One of your words were truncated for length.")

                # Check if we need to flush the message
                if len(words) == 0 or (len(messageBuffer) + len(words[0]) + 1 > textWrapConfig.maximumLineLength):
                    # Constantly remove the last character if it is a '&'
                    # This crashes older clients, so we need to remove it
                    while messageBuffer.endswith("&"):
                        messageBuffer = messageBuffer[:-1]

                    # Flush message
                    await sendMessage(messageBuffer, ignoreList=ignoreList)
                    linesSent += 1

                    # Get last color of message
                    if textWrapConfig.preserveColours:
                        matches = re.findall(r'&[a-zA-Z0-9]', messageBuffer)
                        if matches:
                            # Set previousColor to the last match
                            previousColor = matches[-1]

                    # Reset message buffer
                    messageBuffer = textWrapConfig.multilinePrefix + previousColor

            # If we want to warn the player about the overflow, do so
            if textWrapConfig.warnOnWordOverflow and linesSent > 1 and player:
                await player.sendMessage("&e[NOTICE] Your messages were truncated for length.")

    def initPlayerPing(self):
        # Create reference to playerPingConfig
        playerPingConfig = self.playerPingConfig

        # Save reference back to original processPlayerMessage
        processPlayerMessage = WorldPlayerManager.processPlayerMessage

        # Override the original processPlayerMessage method
        @Override(target=WorldPlayerManager.processPlayerMessage)
        async def processPlayerPingMessage(
            self,
            player: Player,
            message: str,
            world: None | str | World = None,
            globalMessage: bool = False,
            ignoreList: set[Player] = set(),
            messageHandlerOverride: Optional[Callable[..., Awaitable]] = None
        ):
            # Since we are injecting, set type of self to World
            self = cast(WorldPlayerManager, self)

            # Search for pinged players from the message
            pingedPlayers: set[Player] = set()
            pingMatches: set[str] = set(re.findall(playerPingConfig.pingRegex, message))
            for match in pingMatches:
                playerName = match[1:]
                try:
                    p = Player._convertArgument(player.server, playerName)
                except Exception:
                    continue  # Ignore invalid players.
                pingedPlayers.add(p)

            # If there are actually pinged players, run the process. Else, continue as normal.
            if len(pingedPlayers) > 0:
                # Create a helper function to only send the message to the pinged players
                async def sendMessageToPingedPlayers(
                    message: str | list,
                    ignoreList: set[Player] = set()  # List of players to not send the message not
                ):
                    # Sanity check that ignoreList is empty
                    if len(ignoreList) > 0:
                        raise ServerError("Cannot ignore players when sending a message to pinged players! - ignoreList has to be empty when calling sendMessageToPingedPlayers!")

                    # Loop through all players and send the message to them
                    for player in pingedPlayers:
                        await player.sendMessage(message)

                # Send the message header to the pinged players
                if playerPingConfig.sendHeadersAndFooters:
                    await processPlayerMessage(
                        self,
                        None,
                        playerPingConfig.headerColor + playerPingConfig.headerCharacter * playerPingConfig.headerLength,
                        messageHandlerOverride=sendMessageToPingedPlayers
                    )

                # Check if player wants to highlight the ping
                if playerPingConfig.highlightPing:
                    # Generate highlighted message
                    highlightedMessage = message
                    for match in pingMatches:
                        highlightedMessage = highlightedMessage.replace(match, playerPingConfig.pingHighlightFormat.format(ping=match))

                    # Send highlighted message to pinged players
                    await processPlayerMessage(
                        self,
                        player,
                        highlightedMessage,
                        world=world,
                        messageHandlerOverride=sendMessageToPingedPlayers
                    )
                else:
                    # Send regular message to pinged players
                    await processPlayerMessage(
                        self,
                        player,
                        message,
                        world=world,
                        messageHandlerOverride=sendMessageToPingedPlayers
                    )

                # Send the message footer to the pinged players
                if playerPingConfig.sendHeadersAndFooters:
                    await processPlayerMessage(
                        self,
                        None,
                        playerPingConfig.footerColor + playerPingConfig.footerCharacter * playerPingConfig.footerLength,
                        messageHandlerOverride=sendMessageToPingedPlayers
                    )

                # Send message to rest of players as usual
                await processPlayerMessage(
                    self,
                    player,
                    message,
                    world=world,
                    globalMessage=globalMessage,
                    ignoreList=ignoreList | pingedPlayers,
                    messageHandlerOverride=messageHandlerOverride
                )

                # Dont continue to base case
                return

            # Send message to all users as usual
            await processPlayerMessage(
                self,
                player,
                message,
                world=world,
                globalMessage=globalMessage,
                ignoreList=ignoreList,
                messageHandlerOverride=messageHandlerOverride
            )

    def postInit(self):
        # Check if text wrapping is enabled
        if self.config.enableTextWrap:
            self.initTextWrap()

        # Check if text wrapping is enabled
        if self.config.enablePlayerPing:
            self.initPlayerPing()

    @Command(
        "ReloadChatConfig",
        description="Reloads the BetterChat Config",
        version="v1.0.0"
    )
    class ReloadChatConfigCommand(AbstractCommand["BetterChatModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reloadchat"], OP=True)

        async def execute(self, ctx: Player):
            # Reload Config
            self.module.config.reload()
            self.module.textWrapConfig.reload()
            self.module.playerPingConfig.reload()

            # Send Response Back
            await ctx.sendMessage("&aBetterChat Config Reloaded!")

    # Config for BetterChat
    @dataclass
    class BetterChatConfig(AbstractConfig):
        enableTextWrap: bool = True
        enablePlayerPing: bool = True

    # Config for TextWrap
    @dataclass
    class TextWrapConfig(AbstractConfig):
        maximumLineLength: int = 64
        preserveColours: bool = True
        multilinePrefix: str = "&7 | "
        warnOnMessageOverflow: bool = False
        warnOnWordOverflow: bool = False

    # Config for PlayerPing
    @dataclass
    class PlayerPingConfig(AbstractConfig):
        pingRegex: str = "(?<!\\w)@\\w+"
        highlightPing: bool = False
        pingHighlightFormat: str = "&e[{ping}]&f"
        sendHeadersAndFooters: bool = True
        headerColor: str = "&e"
        headerCharacter: str = ">"
        headerLength: int = 48
        footerColor: str = "&e"
        footerCharacter: str = "<"
        footerLength: int = 48
