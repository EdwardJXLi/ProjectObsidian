from obsidian.module import Module, AbstractModule, Dependency
from obsidian.mixins import Override
from obsidian.world import World
from obsidian.player import Player, WorldPlayerManager
from obsidian.config import AbstractConfig

from dataclasses import dataclass
from typing import cast
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

        # Sanity check maximum line length
        if self.textWrapConfig.maximumLineLength > 64:
            raise ValueError("Maximum line length cannot be greater than 64!")

    def postInit(self):
        # Check if text wrapping is enabled
        if self.config.enableTextWrap:
            # Create reference to textWrapConfig
            textWrapConfig = self.textWrapConfig

            # Override the original bulkBlockUpdate method to use the new BulkBlockUpdate packet
            @Override(target=WorldPlayerManager.processPlayerMessage)
            async def processPlayerMessage(
                self,
                player: Player,
                message: str,
                world: None | str | World = None,
                globalMessage: bool = False
            ):
                # Since we are injecting, set type of self to World
                self = cast(WorldPlayerManager, self)

                # Figure out which message handler to use
                if globalMessage:
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
                        if textWrapConfig.warnOnMessageOverflow:
                            await sendMessage("&e[NOTICE] One of your words were truncated for length.")

                    # Check if we need to flush the message
                    if len(words) == 0 or (len(messageBuffer) + len(words[0]) + 1 > textWrapConfig.maximumLineLength):
                        # Constantly remove the last character if it is a '&'
                        # This crashes older clients, so we need to remove it
                        while messageBuffer.endswith("&"):
                            messageBuffer = messageBuffer[:-1]

                        # Flush message
                        await sendMessage(messageBuffer)
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
                if textWrapConfig.warnOnWordOverflow and linesSent > 1:
                    await sendMessage("&e[NOTICE] Your messages were truncated for length.")

    # Config for BetterChat
    @dataclass
    class BetterChatConfig(AbstractConfig):
        enableTextWrap: bool = True

    # Config for TextWrap
    @dataclass
    class TextWrapConfig(AbstractConfig):
        maximumLineLength: int = 64
        preserveColours: bool = True
        multilinePrefix: str = "&7 | "
        warnOnMessageOverflow: bool = False
        warnOnWordOverflow: bool = False
