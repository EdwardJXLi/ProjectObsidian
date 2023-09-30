from obsidian.module import Module, AbstractModule, Dependency
from obsidian.player import Player
from obsidian.errors import ServerError
from obsidian.cpe import CPE, CPEExtension
from obsidian.commands import Command, AbstractCommand
from obsidian.packet import (
    Packets,
    RequestPacket,
    AbstractRequestPacket,
    ResponsePacket,
    AbstractResponsePacket
)

from typing import Optional
from enum import Enum
import struct
import time


class PingDirection(Enum):
    CLIENT_TO_SERVER = 0
    SERVER_TO_CLIENT = 1


@Module(
    "TwoWayPing",
    description="Allows servers and clients to send identifiable ping packets.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="TwoWayPing",
    extVersion=1,
    cpeOnly=True
)
class TwoWayPingModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @RequestPacket(
        "PlayerPing",
        description="Client to Server Ping Packet"
    )
    class PlayerPingPacket(AbstractRequestPacket["TwoWayPingModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x2b,
                FORMAT="!BBh",
                CRITICAL=False,
                PLAYERLOOP=True
            )

        async def deserialize(self, ctx: Optional[Player], rawData: bytearray, handleUpdate: bool = True):
            # <Player Ping Packet>
            # (Byte) Packet ID
            # (Byte) Direction ID
            # (Short) Unique Data
            _, directionId, uniqueData = struct.unpack(self.FORMAT, bytearray(rawData))

            # Convert direction ID to enum
            if directionId == 0:
                direction = PingDirection.CLIENT_TO_SERVER
            else:
                direction = PingDirection.SERVER_TO_CLIENT

            # Check if player was passed / initialized
            if ctx is None:
                raise ServerError("Player Context Was Not Passed And/Or Was Not Initialized!")

            # Check if packet should be processed
            if handleUpdate:
                # Check if direction is from client to server, and if so, send a response packet if client supports it
                if direction == PingDirection.CLIENT_TO_SERVER and ctx.supports(CPEExtension("TwoWayPing", 1)):
                    # Send packet right back
                    await ctx.networkHandler.dispatcher.sendPacket(
                        Packets.Response.ServerPing,
                        direction=direction,
                        uniqueData=uniqueData
                    )

            # Return packet information
            return direction, uniqueData

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @ResponsePacket(
        "ServerPing",
        description="Server to Client Ping Packet",
    )
    class ServerPingPacket(AbstractResponsePacket["TwoWayPingModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x2b,
                FORMAT="!BBh",
                CRITICAL=False
            )

        async def serialize(self, direction: PingDirection, uniqueData: int):
            # <Server Ping Packet>
            # (Byte) Packet ID
            # (Byte) Direction ID
            # (Short) Unique Data
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                direction.value,
                uniqueData
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @Command(
        "Ping",
        description="Returns network ping from the server side.",
        version="v1.0.0",
        override=True
    )
    class PingCommand(AbstractCommand["TwoWayPingModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["ping"])

        async def execute(self, ctx: Player):
            # Check if player supports the TwoWayPing Extension
            if ctx.supports(CPEExtension("TwoWayPing", 1)):
                # Log start time
                start = time.time()

                # Send ping packet to client
                await ctx.networkHandler.dispatcher.sendPacket(
                    Packets.Response.ServerPing,
                    direction=PingDirection.SERVER_TO_CLIENT,
                    uniqueData=0
                )

                # Wait for ping response
                await ctx.networkHandler.dispatcher.waitFor(Packets.Request.PlayerPing)

                # Log end time
                end = time.time()
                ms_delta = int((end - start) * 1000)

                # Notify the user
                await ctx.sendMessage(f"&aPong! Roundtrip took {ms_delta}ms.")
            else:
                # Send a simple "Pong!" message with a warning
                await ctx.sendMessage("&aPong!")
                await ctx.sendMessage("&eWarning: TwoWayPing support is needed for network latency!")
