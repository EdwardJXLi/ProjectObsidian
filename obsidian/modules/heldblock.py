from obsidian.module import Module, AbstractModule, Dependency
from obsidian.modules.core import CoreModule
from obsidian.cpe import CPE, CPEExtension
from obsidian.commands import Command, AbstractCommand
from obsidian.blocks import AbstractBlock, BlockManager
from obsidian.player import Player
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets
from obsidian.mixins import Inject, InjectionPoint, InjectMethod, addAttribute
from obsidian.errors import ServerError, CPEError, CommandError
from obsidian.log import Logger

from typing import Optional, Any, cast
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
            # <Player Movement Packet>
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
            if CPEExtension("HeldBlock", 1) in ctx.getSupportedCPE() and handleUpdate:
                # Set held block of player
                # Using cast to ignore type of player, as heldBlock is injected
                cast(Any, ctx).heldBlock = BlockManager.getBlockById(heldBlock)

        # Create helper function to set held block of a player
        @InjectMethod(target=Player)
        async def holdThis(self, block: AbstractBlock, preventChange: bool = False):
            # Since we are injecting, set type of self to Player
            self = cast(Player, self)

            # Check if player supports the HeldBlock Extension
            if CPEExtension("HeldBlock", 1) not in self.getSupportedCPE():
                raise CPEError(f"Player {self.name} Does Not Support HeldBlock Extension!")

            # Set held block of player
            # Using cast to ignore type of player, as heldBlock is injected
            cast(Any, self).heldBlock = block

            # Send HoldThis Packet
            Logger.info(f"Setting held block for {self.username} to {block.NAME} ({block.ID}).", module="clickdistance")
            if preventChange:
                Logger.info(f"Preventing {self.username} from changing their held block.", module="clickdistance")
            await self.networkHandler.dispatcher.sendPacket(Packets.Response.HoldThis, block, preventChange=preventChange)

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
    )
    class HoldThisCommand(AbstractCommand["HeldBlockModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["holdthis", "setheldblock", "setheld"],
                OP=True
            )

        async def execute(self, ctx: Player, player: Player, block: AbstractBlock, preventChange: bool = False):
            # Check if player supports the HeldBlock Extension
            if CPEExtension("HeldBlock", 1) not in player.getSupportedCPE():
                raise CommandError(f"Player {player.name} Does Not Support HeldBlock Extension!")

            # Force player to hold a specific block
            # Using cast to ignore type of player, as holdThis is injected
            await cast(Any, player).holdThis(block, preventChange)

            # Notify Sender
            await ctx.sendMessage(f"&aSet {player.username}'s held block to {block.NAME}")

    # Command to get an individual player's held block.
    @Command(
        "GetHeldBlock",
        description="Gets the block that a player is holding.",
    )
    class GetHeldBlockCommand(AbstractCommand["HeldBlockModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["holding", "getheldblock", "getheld"],
                OP=True
            )

        async def execute(self, ctx: Player, player: Player):
            # Check if player supports the HeldBlock Extension
            if CPEExtension("HeldBlock", 1) not in player.getSupportedCPE():
                raise CommandError(f"Player {player.name} Does Not Support HeldBlock Extension!")

            # Get held block of player
            # Using cast to ignore type of player, as heldBlock is injected
            heldBlock = cast(Any, player).heldBlock

            # Notify Sender
            await ctx.sendMessage(f"&a{player.username} is holding {heldBlock.NAME} (&9{heldBlock.ID}&a)")
