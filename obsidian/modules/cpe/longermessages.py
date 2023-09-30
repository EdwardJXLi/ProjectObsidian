from obsidian.module import Module, AbstractModule, Dependency
from obsidian.errors import ServerError
from obsidian.player import Player
from obsidian.mixins import addAttribute
from obsidian.cpe import CPE, CPEExtension
from obsidian.log import Logger
from obsidian.packet import (
    AbstractRequestPacket,
    RequestPacket,
    unpackString,
)

from typing import Optional
import struct


@Module(
    "LongerMessages",
    description="Allows clients to accept messages longer than 64 characters, and send them to the server in parts.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="LongerMessages",
    extVersion=1,
    cpeOnly=True
)
class LongerMessagesModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        # Add "partialMessageBuffer" to player
        addAttribute(Player, "partialMessageBuffer", bytearray())

    @RequestPacket(
        "PlayerMessage",
        description="Received When Player Sends A Message. Supports LongerMessages CPE.",
        override=True
    )
    class LongerPlayerMessagePacket(AbstractRequestPacket["LongerMessagesModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0d,
                FORMAT="!BB64s",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray, handleUpdate: bool = True):
            # <Longer Player Message Packet>
            # (Byte) Packet ID
            # (Byte) Partial Message Flag
            # (64String) Message
            _, partialMessageFlag, message = struct.unpack(self.FORMAT, bytearray(rawData))

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

            # Add message to buffer
            setattr(ctx, "partialMessageBuffer", getattr(ctx, "partialMessageBuffer") + message)

            # Check if partial message
            if partialMessageFlag and ctx.supports(CPEExtension("LongerMessages", 1)):
                Logger.debug(f"Handing Partial Message from {ctx.username}", module="longer-messages")
                return unpackString(message)

            # Get message from buffer
            message = getattr(ctx, "partialMessageBuffer")

            # Clear the buffer
            setattr(ctx, "partialMessageBuffer", bytearray())

            # Unpack String
            message = unpackString(message)

            # Check if string is valid
            if not message.isprintable():
                await ctx.sendMessage("&4ERROR: Message Failed To Send - Invalid Character In Message&f")
                return None  # Don't Complete Message Sending
            # Check if string is empty
            if len(message) == 0:
                await ctx.sendMessage("&4ERROR: Message Failed To Send - Empty Message&f")
                return None  # Don't Complete Message Sending

            # Handle Player Message
            if handleUpdate:
                await ctx.handlePlayerMessage(message)

            # Return Parsed Message
            return message

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)
