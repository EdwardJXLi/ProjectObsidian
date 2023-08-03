from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE, CPEExtension
from obsidian.player import Player, PlayerManager, WorldPlayerManager
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets, packageString
from obsidian.commands import Command, AbstractCommand
from obsidian.errors import ConverterError, CPEError
from obsidian.log import Logger, Color

from enum import Enum
import struct


class MessageType(Enum):
    CHAT = 0
    STATUS_1 = 1
    STATUS_2 = 2
    STATUS_3 = 3
    BOTTOM_RIGHT_1 = 11
    BOTTOM_RIGHT_2 = 12
    BOTTOM_RIGHT_3 = 13
    ANNOUNCEMENT = 100
    BIG_ANNOUNCEMENT = 101
    SMALL_ANNOUNCEMENT = 102

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

    # Create helper method to send enhanced messages to players
    @staticmethod
    async def sendMessage(
        player: Player,
        message: str | list,
        messageType: MessageType = MessageType.CHAT,
        fallbackToChat: bool = False
    ):
        Logger.debug(f"Sending Player {player.name} Message {message} of type {messageType}", module="player-enhanced-message")
        # If Message Is A List, Recursively Send All Messages Within
        if isinstance(message, list):
            Logger.debug("Sending List Of Messages To Player!", module="player-enhanced-message")
            for msg in message:
                await MessageTypesModule.sendMessage(player, msg, messageType=messageType, fallbackToChat=fallbackToChat)
            return None  # Break Out of Function

        # Check if user supports the MessageTypes extension
        if player.supports(CPEExtension("MessageTypes", 1)):
            # Send message packet to user
            await player.networkHandler.dispatcher.sendPacket(
                Packets.Response.SendEnhancedMessage,
                str(message),
                messageType
            )
        # If not, check if we should fallback to chat
        elif fallbackToChat:
            Logger.debug(f"Player {player.name} Does Not Support MessageTypes Extension! Falling Back To Chat!", module="player-enhanced-message")
            await player.sendMessage(message)
        else:
            raise CPEError(f"Player {player.name} Does Not Support MessageTypes Extension!")

    # Create helper method to send enhanced messages to a world
    @staticmethod
    async def sendWorldMessage(
        worldPlayerManager: WorldPlayerManager,
        message: str | list,
        messageType: MessageType = MessageType.CHAT,
        fallbackToChat: bool = False,
        ignoreList: set[Player] = set()  # List of players to not send the message
    ):
        # If Message Is A List, Recursively Send All Messages Within
        if isinstance(message, list):
            Logger.debug("Sending List Of Messages!", module="world-enhanced-message")
            for msg in message:
                await MessageTypesModule.sendWorldMessage(
                    worldPlayerManager,
                    msg,
                    messageType=messageType,
                    fallbackToChat=fallbackToChat,
                    ignoreList=ignoreList
                )
            return True  # Break Out of Function

        # Finally, send formatted message
        Logger._log(
            str(message),
            tags=(Logger._getTimestamp(), messageType.name, "world", worldPlayerManager.world.name),
            color=Color.GREEN,
            textColor=Color.WHITE
        )

        # Generate list of players who do not support the MessageTypes extension
        noSupport = {player for player in worldPlayerManager.getPlayers() if not player.supports(CPEExtension("MessageTypes", 1))}
        hasSupport = (set(worldPlayerManager.getPlayers()) - noSupport)

        # Send message packet to all players who support the MessageTypes extension
        if fallbackToChat:
            Logger.debug(f"Sending Enhanced Message To {len(ignoreList | noSupport) - len(noSupport)} Players!", module="world-enhanced-message")
            await worldPlayerManager.sendWorldPacket(
                Packets.Response.SendEnhancedMessage,
                message,
                messageType,
                ignoreList=ignoreList | noSupport
            )

        # Send message to all players who do not support the MessageTypes extension
        Logger.debug(f"Sending Fallback Message To {len(ignoreList | hasSupport)} Players!", module="world-enhanced-message")
        await worldPlayerManager.sendWorldPacket(
            Packets.Response.SendMessage,
            message,
            ignoreList=ignoreList | hasSupport
        )

    # Create helper method to send enhanced messages to all players in all worlds
    @staticmethod
    async def sendGlobalMessage(
        playerManager: PlayerManager,
        message: str | list,
        messageType: MessageType = MessageType.CHAT,
        fallbackToChat: bool = False,
        ignoreList: set[Player] = set()  # List of players to not send the message not
    ):
        # If Message Is A List, Recursively Send All Messages Within
        if isinstance(message, list):
            Logger.debug("Sending List Of Messages!", module="global-enhanced-message")
            for msg in message:
                await MessageTypesModule.sendGlobalMessage(
                    playerManager,
                    msg,
                    messageType=messageType,
                    fallbackToChat=fallbackToChat,
                    ignoreList=ignoreList
                )
            return True  # Break Out of Function

        # Finally, send formatted message
        Logger._log(
            str(message),
            tags=(Logger._getTimestamp(), messageType.name, "global"),
            color=Color.GREEN,
            textColor=Color.WHITE
        )

        # Generate list of players who do not support the MessageTypes extension
        noSupport = {player for player in playerManager.players.values() if not player.supports(CPEExtension("MessageTypes", 1))}
        hasSupport = (set(playerManager.players.values()) - noSupport)

        # Send message packet to all players who support the MessageTypes extension
        Logger.debug(f"Sending Enhanced Message To {len(ignoreList | noSupport)} Players!", module="global-enhanced-message")
        await playerManager.sendGlobalPacket(
            Packets.Response.SendEnhancedMessage,
            message,
            messageType,
            ignoreList=ignoreList | noSupport
        )

        # Send message to all players who do not support the MessageTypes extension
        if fallbackToChat:
            Logger.debug(f"Sending Fallback Message To {len(ignoreList | hasSupport)} Players!", module="global-enhanced-message")
            await playerManager.sendGlobalPacket(
                Packets.Response.SendMessage,
                message,
                ignoreList=ignoreList | hasSupport
            )

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
            # <(Enhanced) Server Message Packet>
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

    @Command(
        "TestEnhancedMessage",
        description="Sends a test message to the player, with customizable types.",
        version="v1.0.0"
    )
    class TestEnhancedMessageCommand(AbstractCommand["MessageTypesModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["enhancedmsg", "emsg"])

        async def execute(self, ctx: Player, messageType: MessageType, *, message: str):
            # Send message to player
            await MessageTypesModule.sendMessage(ctx, message, messageType=messageType)
