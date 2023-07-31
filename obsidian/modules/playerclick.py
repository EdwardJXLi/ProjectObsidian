from obsidian.module import Module, AbstractModule, Dependency
from obsidian.packet import RequestPacket, AbstractRequestPacket
from obsidian.player import Player
from obsidian.errors import ServerError
from obsidian.cpe import CPE

from typing import Optional
import struct


@Module(
    "PlayerClick",
    description="Lets the server receive details of every mouse click a player makes, including targeting information.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="PlayerClick",
    extVersion=1,
    cpeOnly=True
)
class PlayerClickModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @RequestPacket(
        "PlayerClicked",
        description="Received When Player Clicks on Something"
    )
    class PlayerClickedPacket(AbstractRequestPacket["PlayerClickModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x22,
                FORMAT="!BBBhhBhhhB",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray, handleUpdate: bool = True):
            # <Player Click Packet>
            # (Byte) Packet ID
            # (Byte) Button
            # (Byte) Action
            # (Short) Yaw
            # (Short) Pitch
            # (Byte) Target Entity ID
            # (Short) Target Block X
            # (Short) Target Block Y
            # (Short) Target Block Z
            # (Byte) Target Block Face
            (
                _,
                buttonId,
                actionId,
                yaw,
                pitch,
                targetEntityId,
                targetBlockX,
                targetBlockY,
                targetBlockZ,
                targetBlockFace
            ) = struct.unpack(self.FORMAT, bytearray(rawData))

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

            # By default, nothing should be done with the data. This is meant to be overridden

            # Return new positions
            return (
                buttonId,
                actionId,
                yaw,
                pitch,
                targetEntityId,
                targetBlockX,
                targetBlockY,
                targetBlockZ,
                targetBlockFace
            )

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)
