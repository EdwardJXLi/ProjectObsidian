import struct

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE, CPEExtension
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player
from obsidian.errors import ModuleError
from obsidian.packet import (
    AbstractResponsePacket,
    ResponsePacket,
    Packets
)


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

    @staticmethod
    async def setSpawnpoint(player: Player, x: int, y: int, z: int, yaw: int, pitch: int):
        # Verify that the player supports the SetSpawnpoint extension
        if not player.supports(CPEExtension("SetSpawnpoint", 1)):
            raise ModuleError(f"Player {player} does not support the SetSpawnpoint extension!")

        # Send SetSpawnpoint packet to player
        await player.networkHandler.dispatcher.sendPacket(
            Packets.Response.SetSpawnpoint,
            x, y, z, yaw, pitch
        )

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

    @Command(
        "SetSpawn",
        description="Set the your personal spawnpoint",
        version="v1.0.0"
    )
    class SetSpawnCommand(AbstractCommand["SetSpawnpointModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["setspawn", "setspawnpoint", "setsp"])

        async def execute(self, ctx: Player):
            # Check if user supports the SetSpawnpoint extension
            if not ctx.supports(CPEExtension("SetSpawnpoint", 1)):
                raise ModuleError(f"Player {ctx} does not support the SetSpawnpoint extension!")

            # Set the spawnpoint to the current user position
            await SetSpawnpointModule.setSpawnpoint(
                ctx, ctx.posX, ctx.posY, ctx.posZ, ctx.posYaw, ctx.posPitch
            )

            # Send Formatted World Seed
            await ctx.sendMessage("&aSpawnpoint Set!")
