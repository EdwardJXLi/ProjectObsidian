from typing import Callable, Awaitable, cast
import asyncio
import datetime
import struct

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.log import Logger
from obsidian.packet import Packets
from obsidian.blocks import AbstractBlock
from obsidian.world import World
from obsidian.player import Player
from obsidian.errors import PacketError, BlockError
from obsidian.cpe import CPE, CPEExtension
from obsidian.mixins import Override
from obsidian.packet import (
    AbstractResponsePacket,
    ResponsePacket
)


@Module(
    "BulkBlockUpdate",
    description="Allows servers to send a single optimized packet that contains 256 block updates.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="BulkBlockUpdate",
    extVersion=1,
    cpeOnly=True
)
class BulkBlockUpdateModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    def postInit(self, *args, **kwargs):
        # Override the original bulkBlockUpdate method to use the new BulkBlockUpdate packet
        @Override(target=World.bulkBlockUpdate, passSuper=True)
        async def bulkBlockUpdate(
            self,
            blockUpdates: dict[tuple[int, int, int], AbstractBlock],
            sendPacket: bool = True,
            *,  # Get additional contexts
            _super: Callable[..., Awaitable]
        ):
            # Since we are injecting, set type of self to World
            self = cast(World, self)

            # Check if the number of block updates pass the block update threshold.
            if not len(blockUpdates) > 128:
                Logger.debug("Number of block updates does not exceed the block update threshold. Falling back to original method.", module="bulk-update")
                # If not, fallback to original method
                return await _super(self, blockUpdates, sendPacket)

            # Handles Bulk Block Updates In Server + Checks If Block Placement Is Allowed
            Logger.debug(f"Handling Bulk Block Update for {len(blockUpdates)} blocks", module="bulk-update")

            # Set last modified date
            self.lastModified = datetime.datetime.now()

            # Update maparray with block updates
            Logger.debug("Updating World Map Array", module="bulk-update")
            for (blockX, blockY, blockZ), block in blockUpdates.items():
                # Check If Block Is Out Of Range
                if blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ:
                    raise BlockError(f"Block Placement Is Out Of Range ({blockX}, {blockY}, {blockZ})")

                # Update Map Array
                self.mapArray[blockX + self.sizeX * (blockZ + self.sizeZ * blockY)] = block.ID

            if sendPacket:
                # Check if the number of block updates exceed the map reload threshold. If so, send a map refresh instead
                if self.worldManager.server.config.blockUpdatesBeforeReload > 0 and len(blockUpdates) > self.worldManager.server.config.blockUpdatesBeforeReload:
                    Logger.debug("Number of block updates exceed the map reload threshold. Sending map refresh instead.", module="bulk-update")
                    for player in self.playerManager.getPlayers():
                        await player.reloadWorld()
                    return

                # Make list of players who support BulkBlockUpdate and who dont
                bulkUpdatePlayers: set[Player] = set()
                regularUpdatePlayers: set[Player] = set()

                # Loop through all players and determine who supports BulkBlockUpdate
                for player in self.playerManager.getPlayers():
                    if player.supports(CPEExtension("BulkBlockUpdate", 1)):
                        bulkUpdatePlayers.add(player)
                    else:
                        regularUpdatePlayers.add(player)
                Logger.verbose(f"Players who support BulkBlockUpdate: {bulkUpdatePlayers}", module="bulk-update")
                Logger.verbose(f"Players who dont support BulkBlockUpdate: {regularUpdatePlayers}", module="bulk-update")

                # Chunk up updates and send bulk updates to players who support it
                Logger.debug(f"Sending BulkBlockUpdate Packets to {len(bulkUpdatePlayers)} players", module="bulk-update")
                blockIndices: list[int] = [
                    blockX + self.sizeX * (blockZ + self.sizeZ * blockY)
                    for blockX, blockY, blockZ in blockUpdates.keys()
                ]
                blockIds: list[int] = [block.ID for block in blockUpdates.values()]
                # While theres still block updates to send, send them
                while blockIndices:
                    # Chunk up block updates
                    blockIndicesChunk = blockIndices[:256]
                    blockIdsChunk = blockIds[:256]
                    # Remove chunk from list
                    blockIndices = blockIndices[256:]
                    blockIds = blockIds[256:]

                    # If asynchronousBlockUpdates is enabled, run a 0 second sleep so that other tasks can operate
                    if self.worldManager.server.config.asynchronousBlockUpdates:
                        await asyncio.sleep(0)

                    # Send chunk to players who support BulkBlockUpdates
                    Logger.verbose(f"Sending BulkBlockUpdate Chunk of size {len(blockIndicesChunk)} to {len(bulkUpdatePlayers)} players", module="bulk-update")
                    for player in bulkUpdatePlayers:
                        await player.networkHandler.dispatcher.sendPacket(
                            Packets.Response.BulkBlockUpdate,
                            blockIndicesChunk,
                            blockIdsChunk
                        )

                # Loop through each block and handle update for players who dont support BulkBlockUpdate
                Logger.debug(f"Sending Regular SetBlock Packets to {len(regularUpdatePlayers)} players", module="bulk-update")
                for (blockX, blockY, blockZ), block in blockUpdates.items():
                    Logger.verbose(f"Setting World Block {blockX}, {blockY}, {blockZ} to {block.ID}", module="bulk-update")

                    # If asynchronousBlockUpdates is enabled, run a 0 second sleep so that other tasks can operate
                    if self.worldManager.server.config.asynchronousBlockUpdates:
                        await asyncio.sleep(0)

                    # Loop through players who dont support BulkBlockUpdate and send them the block update
                    for player in regularUpdatePlayers:
                        await player.networkHandler.dispatcher.sendPacket(
                            Packets.Response.SetBlock,
                            blockX, blockY, blockZ, block.ID
                        )

                Logger.debug("Done processing bulkBlockUpdate", module="bulk-update")

    @ResponsePacket(
        "BulkBlockUpdate",
        description="A single optimized packet that contains 256 block updates.",
    )
    class BulkBlockUpdatePacket(AbstractResponsePacket["BulkBlockUpdateModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x26,
                FORMAT="!BB256I256B",
                CRITICAL=False
            )

        async def serialize(self, indices: list[int], blockIds: list[int]):
            # <Bulk Block Update Packet>
            # (Byte) Packet ID
            # (Byte) Number of Block Updates (minus 1)
            # (256 Int) Indices of Block Updates
            # (256 Byte) List of New Blocks

            # Verify that the number of indices and blocks are the same
            if len(indices) != len(blockIds):
                raise PacketError("Number of indices and blocks must be the same!")

            # Pad indices and blockIds to 256
            indices = indices + [0] * (256 - len(indices))
            blockIds = blockIds + [0] * (256 - len(blockIds))

            # Send Packet
            msg = struct.pack(self.FORMAT, self.ID, len(indices) - 1, *indices, *blockIds)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)
