from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets, packageString
from obsidian.errors import ConverterError
from obsidian.log import Logger

from enum import Enum
import struct


class MessageType(Enum):
    CHAT = 0
    STATUS1 = 1
    STATUS2 = 2
    STATUS3 = 3
    BOTTOMRIGHT1 = 11
    BOTTOMRIGHT2 = 12
    BOTTOMRIGHT3 = 13
    ANNOUNCEMENT = 100

    @staticmethod
    def _convertArgument(_, argument: str):
        try:
            # Try to get the message type as an int
            return MessageType(int(argument))
        except (KeyError, ValueError):
            # If fail, try to get message type as a string
            try:
                return MessageType[argument.upper()]
            except ValueError:
                # Raise error if block not found
                raise ConverterError(f"MessageType {argument} Not Found!")


@Module(
    "MessageTypes",
    description="This extension adds new ways of presenting messages in the client.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="MessageTypes",
    extVersion=1,
    cpeOnly=True
)
class MessageTypesModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @ResponsePacket(
        "SendEnhancedMessage",
        description="Broadcasts Enhanced Message To Player",
        override=True
    )
    class SendEnhancedMessagePacket(AbstractResponsePacket["MessageTypesModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x0d,
                FORMAT="!BB64s",
                CRITICAL=False
            )

        async def serialize(self, message: str, messageType: MessageType):
            # <Player Message Packet>
            # (Byte) Packet ID
            # (Byte) MessageType
            # (64String) Message
            if len(message) > 64:
                Logger.warn(f"Trying to send message '{message}' over the 64 character limit!", module="packet-serializer")

            # Format Message Packet
            packedMessage = packageString(message)
            if len(packedMessage) > 0 and packedMessage[-1] == ord("&"):  # Using the ascii value as it is packed into a bytearray already
                Logger.warn(f"Trying to send message '{message}' with '&' as the last character!", module="packet-serializer")
                packedMessage = packedMessage[:-1]  # This isnt supposed to prevent any exploits, just to prevent accidents if the message gets cut off short

            # Send Message Packet
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                messageType.value,
                bytes(packedMessage)
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # Command to send an enhanced message
    @Command(
        "EnhancedMessage",
        description="Sends an enhanced message to a player.",
        version="v1.0.0"
    )
    class EnhancedMessageCommand(AbstractCommand["MessageTypesModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["sendmessage", "sendannouncement", "sendstatus"],
                OP=True
            )

        async def execute(self, ctx: Player, recipient: Player, messageType: MessageType, *, message: str):
            # Send Message
            # await recipient.sendEnhancedMessage(message, messageType)

            # Send Message Packet
            await recipient.networkHandler.dispatcher.sendPacket(
                Packets.Response.SendEnhancedMessage,
                message, messageType
            )
