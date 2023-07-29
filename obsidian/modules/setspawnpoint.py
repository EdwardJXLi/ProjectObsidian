from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE
from obsidian.packet import (
    AbstractResponsePacket,
    ResponsePacket
)

import struct


@Module(
    "SetSpawnpoint",
    description="Allows servers to directly set the spawn position and orientation of players.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="SetSpawnpoint",
    extVersion=1,
    cpeOnly=True
)
class SetSpawnpointModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @ResponsePacket(
        "SetSpawnpoint",
        description="Packet To Change The Spawnpoint Of A Player."
    )
    class SetSpawnpointPacket(AbstractResponsePacket["SetSpawnpointModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x2E,
                FORMAT="!BhhhBB",
                CRITICAL=False
            )

        async def serialize(self, x: int, y: int, z: int, yaw: int, pitch: int):
            # <Set Spawnpoint Packet>
            # (Byte) Packet ID
            # (Short) Spawn X Coords
            # (Short) Spawn Y Coords
            # (Short) Spawn Z Coords
            # (Byte) Spawn Yaw
            # (Byte) Spawn Pitch
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                int(x),
                int(y),
                int(z),
                int(yaw),
                int(pitch)
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)
