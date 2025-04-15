from typing import Optional, cast
import struct

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.mixins import Override, Inject, InjectionPoint
from obsidian.errors import ServerError
from obsidian.network import NetworkHandler
from obsidian.player import Player, WorldPlayerManager, PlayerManager
from obsidian.cpe import CPE, CPEExtension
from obsidian.log import Logger
from obsidian.constants import Color
from obsidian.packet import (
    AbstractRequestPacket,
    RequestPacket,
    AbstractResponsePacket,
    ResponsePacket,
    Packets
)
from obsidian.modules.lib.emojilib import replaceNonAsciiCharacters, unpackCP437String, packageCP437String


@Module(
    "FullCP437",
    description="This extension allows players to send and receive chat with all characters in code page 437, rather than just the 0 to 127 characters.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core"), Dependency("emojilib"), Dependency("emotefix")]
)
@CPE(
    extName="FullCP437",
    extVersion=1,
    cpeOnly=True
)
class FullCP437Module(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    def postInit(self):
        super().postInit()

        # Send warning message if player has FullCP437 support without EmoteFix support
        @Inject(target=NetworkHandler._processPostLogin, at=InjectionPoint.AFTER)
        async def sendEmoteFixWarning(self):
            # Since we are injecting, set type of self to Player
            self = cast(NetworkHandler, self)

            # Check if player is not None
            if self.player is None:
                raise ServerError("Trying To Process Post Login Actions Before Player Is Initialized!")

            # Check if player supports the FullCP437 Extension but not the EmoteFix Extension
            if self.player.supports(CPEExtension("FullCP437", 1)) and not self.player.supports(CPEExtension("EmoteFix", 1)):
                Logger.warn(f"Player {self.player.name} supports FullCP437 but not EmoteFix! Sending warning to user!", module="texthotkey")
                # Send warning to user
                await self.player.sendMessage("&eYour client supports FullCP437 but not EmoteFix!")
                await self.player.sendMessage("&eThis means that you will not be able to see emojis in chat!")
                await self.player.sendMessage("&ePlease upgrade to a newer client to be able to see emojis.")

        # Override sendMessage, sendWorldMessage, and sendGlobalMessage to use the FullCP437MessagePacket
        @Override(target=Player.sendMessage)
        async def sendMessage(self, message: str | list):
            # Since we are overriding, set type of self to Player
            self = cast(Player, self)

            Logger.debug(f"Sending Player {self.name} Message {message}", module="player-message")
            # If Message Is A List, Recursively Send All Messages Within
            if isinstance(message, list):
                Logger.debug("Sending List Of Messages To Player!", module="player-message")
                for msg in message:
                    await sendMessage(self, msg)
                return None  # Break Out of Function

            # Check if message contains ascii characters
            if message.isascii():
                # Send message packet to user
                await self.networkHandler.dispatcher.sendPacket(Packets.Response.SendMessage, message)
            elif self.supports(CPEExtension("FullCP437", 1)) and self.supports(CPEExtension("EmoteFix", 1)):
                # Send message packet to user
                await self.networkHandler.dispatcher.sendPacket(Packets.Response.SendCP437Message, message)
            else:
                # Send fallback message to user
                Logger.warn(f"Player {self.name} Does Not Support FullCP437 or EmoteFix Extension! Using Fallback Characters!", module="player-message")
                await self.networkHandler.dispatcher.sendPacket(Packets.Response.SendMessage, replaceNonAsciiCharacters(message))

        @Override(target=WorldPlayerManager.sendWorldMessage)
        async def sendWorldMessage(
            self,
            message: str | list,
            ignoreList: set[Player] = set()  # List of players to not send the message
        ):
            # Since we are overriding, set type of self to WorldPlayerManager
            self = cast(WorldPlayerManager, self)

            # If Message Is A List, Recursively Send All Messages Within
            if isinstance(message, list):
                Logger.debug("Sending List Of Messages!", module="world-message")
                for msg in message:
                    await sendWorldMessage(self, msg, ignoreList=ignoreList)
                return True  # Break Out of Function

            # Finally, send formatted message
            Logger._log(
                str(message),
                tags=(Logger._getTimestamp(), "chat", "world", self.world.name),
                color=Color.GREEN,
                textColor=Color.WHITE
            )

            # If message contains non-ascii characters, send message packet to all players who support the FullCP437 and EmoteFix extension.
            # Else, send message as normal.
            if not message.isascii():
                # Generate list of players who do not support the FullCP437 or EmoteFix extension
                noSupport = {player for player in self.getPlayers() if not (player.supports(CPEExtension("FullCP437", 1)) and player.supports(CPEExtension("EmoteFix", 1)))}
                hasSupport = set(self.getPlayers()) - noSupport

                # Send message packet to all players who support the FullCP437 and EmoteFix extension
                Logger.debug(f"Sending Message To {len(hasSupport)} Players!", module="world-message")
                await self.sendWorldPacket(
                    Packets.Response.SendCP437Message,
                    message,
                    ignoreList=ignoreList | noSupport
                )

                # Send message to all players who do not support the FullCP437 or EmoteFix extension
                Logger.debug(f"Sending Fallback Message To {len(noSupport)} Players! (No FullCP437 or EmoteFix Support)", module="world-message")
                await self.sendWorldPacket(
                    Packets.Response.SendMessage,
                    replaceNonAsciiCharacters(message),
                    ignoreList=ignoreList | hasSupport
                )
            else:
                await self.sendWorldPacket(Packets.Response.SendMessage, message, ignoreList=ignoreList)

        @Override(target=PlayerManager.sendGlobalMessage)
        async def sendGlobalMessage(
            self,
            message: str | list,
            ignoreList: set[Player] = set()  # List of players to not send the message not
        ):
            # Since we are overriding, set type of self to PlayerManager
            self = cast(PlayerManager, self)

            # If Message Is A List, Recursively Send All Messages Within
            if isinstance(message, list):
                Logger.debug("Sending List Of Messages!", module="global-message")
                for msg in message:
                    await sendGlobalMessage(self, msg, ignoreList=ignoreList)
                return True  # Break Out of Function

            # Finally, send formatted message
            Logger._log(
                str(message),
                tags=(Logger._getTimestamp(), "chat", "global"),
                color=Color.GREEN,
                textColor=Color.WHITE
            )

            # If message contains non-ascii characters, send message packet to all players who support the FullCP437 and EmoteFix extension.
            # Else, send message as normal.
            if not message.isascii():
                # Generate list of players who do not support the FullCP437 or EmoteFix extension
                allPlayers = self.getPlayers()
                noSupport = {player for player in allPlayers if not (player.supports(CPEExtension("FullCP437", 1)) and player.supports(CPEExtension("EmoteFix", 1)))}
                hasSupport = set(allPlayers) - noSupport

                # Send message packet to all players who support the FullCP437 and EmoteFix extension
                Logger.debug(f"Sending Message To {len(hasSupport)} Players!", module="global-message")
                await self.sendGlobalPacket(
                    Packets.Response.SendCP437Message,
                    message,
                    ignoreList=ignoreList | noSupport
                )

                # Send message to all players who do not support the FullCP437 or EmoteFix extension
                Logger.debug(f"Sending Fallback Message To {len(noSupport)} Players! (No FullCP437 or EmoteFix Support)", module="global-message")
                await self.sendGlobalPacket(
                    Packets.Response.SendMessage,
                    replaceNonAsciiCharacters(message),
                    ignoreList=ignoreList | hasSupport
                )
            else:
                await self.sendGlobalPacket(Packets.Response.SendMessage, message, ignoreList=ignoreList)

    @RequestPacket(
        "PlayerMessage",
        description="Received When Player Sends A Message. Supports FullCP437 CPE.",
        override=True
    )
    class PlayerCP437MessagePacket(AbstractRequestPacket["FullCP437Module"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0d,
                FORMAT="!BB64s",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray, handleUpdate: bool = True):
            # <Player Message Packet>
            # (Byte) Packet ID
            # (Byte) Unused (Should Always Be 0xFF)
            # (64String) Message
            _, _, message = struct.unpack(self.FORMAT, bytearray(rawData))

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

            # Unpack String
            message = unpackCP437String(message)

            # Handle Player Message
            if handleUpdate:
                await ctx.handlePlayerMessage(message)

            # Return Parsed Message
            return message

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "SendCP437Message",
        description="Broadcasts CP437 Message To Player",
        override=True
    )
    class SendCP437MessagePacket(AbstractResponsePacket["FullCP437Module"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0d,
                FORMAT="!BB64s",
                CRITICAL=False
            )

        async def serialize(self, message: str, playerId: int = 0):
            # <Player Message Packet>
            # (Byte) Packet ID
            # (Byte) Player ID (Seems to be unused?)
            # (64String) Message
            if len(message) > 64:
                Logger.warn(f"Trying to send message '{message}' over the 64 character limit!", module="packet-serializer")

            # Format Message Packet
            packedMessage = packageCP437String(message)
            if len(packedMessage) > 0 and packedMessage[-1] == ord("&"):  # Using the ascii value as it is packed into a bytearray already
                Logger.warn(f"Trying to send message '{message}' with '&' as the last character!", module="packet-serializer")
                packedMessage = packedMessage[:-1]  # This isnt supposed to prevent any exploits, just to prevent accidents if the message gets cut off short

            # Send Message Packet
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(playerId),
                bytes(packedMessage)
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)
