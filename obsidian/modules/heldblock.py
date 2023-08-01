from obsidian.module import Module, AbstractModule, Dependency
from obsidian.modules.core import CoreModule
from obsidian.cpe import CPE, CPEExtension
from obsidian.commands import Command, AbstractCommand
from obsidian.blocks import AbstractBlock, BlockManager
from obsidian.player import Player
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets
from obsidian.mixins import Inject, InjectionPoint, addAttribute
from obsidian.errors import ServerError, CPEError, CommandError
from obsidian.log import Logger

from typing import Optional
import struct


@Module(
    "HeldBlock",
    description="Provides a way for the client to notify the server about the blocktype that it is currently holding, and for the server to change the currently-held block type.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="HeldBlock",
    extVersion=1,
    cpeOnly=True
)
class HeldBlockModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        addAttribute(Player, "heldBlock", None)

    def postInit(self):
        super().postInit()

        # Change handler for MovementUpdate deserialization to use the (unused) PlayerID field to store the held block
        @Inject(target=CoreModule.MovementUpdatePacket.deserialize, at=InjectionPoint.AFTER)
        async def deserializeHeldBlock(self, ctx: Optional[Player], rawData: bytearray, handleUpdate: bool = True):
            # <Held Block Packet Addition>
            # (Byte) Packet ID
            # (Byte) HeldBlock
            # (Short) Ignore
            # (Short) Ignore
            # (Short) Ignore
            # (Byte) Ignore
            # (Byte) Ignore
            _, heldBlock, _, _, _, _, _ = struct.unpack(self.FORMAT, bytearray(rawData))

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

            # Check if player supports the HeldBlock Extension
            if ctx.supports(CPEExtension("HeldBlock", 1)) and handleUpdate:
                # Set held block of player
                setattr(ctx, "heldBlock", BlockManager.getBlockById(heldBlock))

    # Create helper function to set held block of a player
    @staticmethod
    async def holdThis(player: Player, block: AbstractBlock, preventChange: bool = False):
        # Check if player supports the HeldBlock Extension
        if not player.supports(CPEExtension("HeldBlock", 1)):
            raise CPEError(f"Player {player.name} Does Not Support HeldBlock Extension!")

        # Set held block of player
        setattr(player, "heldBlock", block)

        # Send HoldThis Packet
        Logger.info(f"Setting held block for {player.username} to {block.NAME} ({block.ID}).", module="heldblock")
        if preventChange:
            Logger.info(f"Preventing {player.username} from changing their held block.", module="heldblock")
        await player.networkHandler.dispatcher.sendPacket(Packets.Response.HoldThis, block, preventChange=preventChange)

    # Create helper function to get held block of a player
    @staticmethod
    def getHeldBlock(player: Player) -> AbstractBlock:
        # Check if player supports the HeldBlock Extension
        if not player.supports(CPEExtension("HeldBlock", 1)):
            raise CPEError(f"Player {player.name} Does Not Support HeldBlock Extension!")

        # Get held block of player
        # Using cast to ignore type of player, as heldBlock is injected
        return getattr(player, "heldBlock")

    # Packet to send to clients to force them to change their held block
    @ResponsePacket(
        "HoldThis",
        description="Force the client to hold the desired block type",
    )
    class HoldThisPacket(AbstractResponsePacket["HeldBlockModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x14,
                FORMAT="!BBB",
                CRITICAL=False
            )

        async def serialize(self, blockToHold: AbstractBlock, preventChange: bool = False):
            # <Hold This Packet>
            # (Byte) Packet ID
            # (Byte) Block To Hold
            # (Byte) Prevent Change
            msg = struct.pack(self.FORMAT, self.ID, blockToHold.ID, preventChange)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # Command to set an individual player's held block.
    @Command(
        "HoldThis",
        description="Forces a player to hold a block.",
        version="v1.0.0"
    )
    class HoldThisCommand(AbstractCommand["HeldBlockModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["holdthis", "setheldblock", "setheld"],
                OP=True
            )

        async def execute(
            self, ctx: Player,
            block: AbstractBlock,
            player: Optional[Player] = None,
            preventChange: bool = False
        ):
            # Use sender if no player was passed
            if player is None:
                player = ctx

            # Check if player supports the HeldBlock Extension
            if not player.supports(CPEExtension("HeldBlock", 1)):
                raise CommandError(f"Player {player.name} Does Not Support HeldBlock Extension!")

            # Force player to hold a specific block
            await HeldBlockModule.holdThis(player, block, preventChange)

            # Notify Sender
            await ctx.sendMessage(f"&aSet {player.username}'s held block to {block.NAME}")

    # Command to get an individual player's held block.
    @Command(
        "GetHeldBlock",
        description="Gets the block that a player is holding.",
        version="v1.0.0"
    )
    class GetHeldBlockCommand(AbstractCommand["HeldBlockModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["holding", "getheldblock", "getheld"],
                OP=True
            )

        async def execute(self, ctx: Player, player: Optional[Player] = None):
            # Use sender if no player was passed
            if player is None:
                player = ctx

            # Check if player supports the HeldBlock Extension
            if not player.supports(CPEExtension("HeldBlock", 1)):
                raise CommandError(f"Player {player.name} Does Not Support HeldBlock Extension!")

            # Get held block of player
            # Using cast to ignore type of player, as heldBlock is injected
            heldBlock = HeldBlockModule.getHeldBlock(player)

            # Notify Sender
            await ctx.sendMessage(f"&a{player.username} is holding {heldBlock.NAME} (&9{heldBlock.ID}&a)")
