from enum import Enum
import struct

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE, CPEExtension
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player
from obsidian.errors import CPEError, CommandError
from obsidian.log import Logger
from obsidian.packet import (
    AbstractResponsePacket,
    ResponsePacket,
    Packets
)


class VelocityControlMode(Enum):
    ADD = 0
    SET = 1


@Module(
    "VelocityControl",
    description="Allows servers to affect the velocity of players.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="VelocityControl",
    extVersion=1,
    cpeOnly=True
)
class VelocityControlModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    # Create helper method to set a player's velocity
    @staticmethod
    async def setPlayerVelocity(player: Player, xVelocity: int, yVelocity: int, zVelocity: int):
        Logger.debug(f"Changing Player {player.name}'s Velocity to {xVelocity}, {yVelocity}, {zVelocity}", module="velocity-control")
        # Check if player supports the VelocityControl Extension
        if not player.supports(CPEExtension("VelocityControl", 1)):
            raise CPEError(f"Player {player.name} Does Not Support VelocityControl Extension!")

        # Send Velocity Control Packet
        await player.networkHandler.dispatcher.sendPacket(
            Packets.Response.VelocityControl,
            xVelocity, yVelocity, zVelocity,
            VelocityControlMode.SET, VelocityControlMode.SET, VelocityControlMode.SET
        )

    # Create helper method to add to a a player's velocity
    @staticmethod
    async def addPlayerVelocity(player: Player, xVelocity: int, yVelocity: int, zVelocity: int):
        Logger.debug(f"Adding {xVelocity}, {yVelocity}, {zVelocity} to Player {player.name}'s Velocity", module="velocity-control")

        # Check if player supports the VelocityControl Extension
        if not player.supports(CPEExtension("VelocityControl", 1)):
            raise CPEError(f"Player {player.name} Does Not Support VelocityControl Extension!")

        # Send Velocity Control Packet
        await player.networkHandler.dispatcher.sendPacket(
            Packets.Response.VelocityControl,
            xVelocity, yVelocity, zVelocity,
            VelocityControlMode.ADD, VelocityControlMode.ADD, VelocityControlMode.ADD
        )

    @ResponsePacket(
        "VelocityControl",
        description="Packet To Change/Set/Modify the Velocity of a Player."
    )
    class VelocityControlPacket(AbstractResponsePacket["VelocityControlModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x2F,
                FORMAT="!BiiiBBB",
                CRITICAL=False
            )

        async def serialize(
            self,
            xVelocity: int,
            yVelocity: int,
            zVelocity: int,
            xMode: VelocityControlMode = VelocityControlMode.SET,
            yMode: VelocityControlMode = VelocityControlMode.SET,
            zMode: VelocityControlMode = VelocityControlMode.SET
        ):
            # <Velocity Control Packet>
            # (Byte) Packet ID
            # (Integer) X Velocity
            # (Integer) Y Velocity
            # (Integer) Z Velocity
            # (Byte) X Mode (0 = Add, 1 = Set)
            # (Byte) Y Mode (0 = Add, 1 = Set)
            # (Byte) Z Mode (0 = Add, 1 = Set)

            msg = struct.pack(
                self.FORMAT,
                self.ID,
                xVelocity,
                yVelocity,
                zVelocity,
                xMode.value,
                yMode.value,
                zMode.value
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @Command(
        "Push",
        description="Pushes a player in a direction.",
        version="v1.0.0"
    )
    class PushCommand(AbstractCommand["VelocityControlModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["push", "setvelocity"]
            )

        async def execute(self, ctx: Player, target: Player, xVelocity: int, yVelocity: int, zVelocity: int):
            # Check if player supports the VelocityControl Extension
            if not target.supports(CPEExtension("VelocityControl", 1)):
                raise CommandError(f"Player {target.name} Does Not Support VelocityControl Extension!")

            # Send Velocity Control Packet
            await VelocityControlModule.addPlayerVelocity(target, xVelocity, yVelocity, zVelocity)

            # Send message to player
            await ctx.sendMessage("&aYoink!")
