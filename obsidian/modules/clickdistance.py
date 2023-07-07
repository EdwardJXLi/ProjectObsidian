from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets

from typing import Optional
import struct


@Module(
    "ClickDistance",
    description="Extend or restrict the distance at which client may click blocks",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="ClickDistance",
    extVersion=1,
    cpeOnly=True
)
class ClickDistanceModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @ResponsePacket(
        "SetClickDistance",
        description="Changes player click distance. Set to 0 to disable clicking.",
    )
    class SetClickDistancePacket(AbstractResponsePacket["ClickDistanceModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x12,
                FORMAT="!Bh",
                CRITICAL=False
            )

        async def serialize(self, distance: int):
            # <Set Click Distance Packet>
            # (Byte) Packet ID
            # (Short) Click Distance
            msg = struct.pack(self.FORMAT, self.ID, distance)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @Command(
        "SetClickDistance",
        description="Sets the click distance for a player",
    )
    class SetClickDistanceCommand(AbstractCommand["ClickDistanceModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["setclickdistance"],
                OP=True
            )

        async def execute(self, ctx: Player, distance: int, player: Optional[Player] = None):
            # If no player is specified, set the distance for the sender
            if player is None:
                player = ctx

            # Send click distance to player
            await player.networkHandler.dispatcher.sendPacket(Packets.Response.SetClickDistance, distance)

            # Notify Sender
            await ctx.sendMessage(f"Set click distance for {player.username} to {distance}")
