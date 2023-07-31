from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE
from obsidian.blocks import AbstractBlock
from obsidian.packet import (
    AbstractResponsePacket,
    ResponsePacket
)

import struct


@Module(
    "InventoryOrder",
    description="Allows servers to explicitly control the inventory's layout.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="InventoryOrder",
    extVersion=1,
    cpeOnly=True
)
class InventoryOrderModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @ResponsePacket(
        "SetInventoryOrder",
        description="Packet To Change The Contents Of A Player's Inventory Order."
    )
    class SetInventoryOrderPacket(AbstractResponsePacket["InventoryOrderModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x2C,
                FORMAT="!BBB",
                CRITICAL=False
            )

        async def serialize(self, order: int, block: AbstractBlock):
            # <Inventory Order Packet>
            # (Byte) Packet ID
            # (Byte) Block Order
            # (Byte) Block ID

            msg = struct.pack(self.FORMAT, self.ID, order, block.ID)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)
