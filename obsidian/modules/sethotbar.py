from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE
from obsidian.blocks import AbstractBlock
from obsidian.errors import ServerError
from obsidian.packet import (
    AbstractResponsePacket,
    ResponsePacket
)

import struct


@Module(
    "SetHotbar",
    description="Allows servers to set the contents of a player's hotbar.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="SetHotbar",
    extVersion=1,
    cpeOnly=True
)
class SetHotbarModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @ResponsePacket(
        "SetHotbar",
        description="Packet To Change The Contents Of A Player's Hotbar."
    )
    class SetHotbarPacket(AbstractResponsePacket["SetHotbarModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x2D,
                FORMAT="!BBB",
                CRITICAL=False
            )

        async def serialize(self, block: AbstractBlock, hotbarIndex: int):
            # <Set Hotbar Packet>
            # (Byte) Packet ID
            # (Byte) Block ID
            # (Byte) Hotbar Index

            # Sanity check hotbar index
            if hotbarIndex < 0 or hotbarIndex > 8:
                raise ServerError(f"Invalid hotbar index {hotbarIndex}!")

            msg = struct.pack(self.FORMAT, self.ID, block.ID, hotbarIndex)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)
