from dataclasses import dataclass
from typing import Callable, Awaitable, cast
import zlib
import struct

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.log import Logger
from obsidian.packet import Packets
from obsidian.config import AbstractConfig
from obsidian.world import World
from obsidian.network import NetworkHandler
from obsidian.errors import ServerError
from obsidian.cpe import CPE, CPEExtension
from obsidian.mixins import Override
from obsidian.packet import (
    AbstractResponsePacket,
    ResponsePacket
)


@Module(
    "FastMap",
    description="Reduces load on clients and servers by reducing the complexity of sending the map.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="FastMap",
    extVersion=1,
    cpeOnly=True
)
class FastMapModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.FastMapConfig)

    def postInit(self, *args, **kwargs):
        # Override the original sendWorldData method to use the new FastMap protocol
        @Override(target=NetworkHandler.sendWorldData, passSuper=True, additionalContext={"fastMapConfig": self.config})
        async def sendWorldData(
            self,
            world: World,
            *,
            _super: Callable[[NetworkHandler, World], Awaitable],
            fastMapConfig: "FastMapModule.FastMapConfig"
        ):
            # Since we are injecting, set type of self to NetworkHandler
            self = cast(NetworkHandler, self)

            # Sanity check that this should be called after player initialization
            if not self.player:
                raise ServerError("CPE Negotiation Called Before Player Initialization!")

            # Check if player supports the FastMap extension
            if not self.player.supports(CPEExtension("FastMap", 1)):
                Logger.debug(f"{self.connectionInfo} | Player does not support FastMap. Falling back to original method.", module="fastmap")
                # If not, fallback to original method
                return await _super(self, world)

            Logger.debug(f"{self.connectionInfo} | Player supports FastMap. Upgrading to the FastMap protocol.", module="fastmap")

            # Send Level Initialize Packet
            Logger.debug(f"{self.connectionInfo} | Sending Level Initialize Packet [Fast Map]", module="fastmap")
            await self.dispatcher.sendPacket(Packets.Response.FastMapLevelInitialize, len(world.mapArray))

            # Preparing To Send Map
            Logger.debug(f"{self.connectionInfo} | Preparing To Send Map [Fast Map] ", module="fastmap")
            deflatedWorld = FastMapModule.deflateMap(self, world, compressionLevel=fastMapConfig.deflateCompressionLevel)  # Generate Deflated Map
            # World Data Needs To Be Sent In Chunks Of 1024 Characters
            chunks = [deflatedWorld[i: i + 1024] for i in range(0, len(deflatedWorld), 1024)]

            # Looping Through All Chunks And Sending Data
            Logger.debug(f"{self.connectionInfo} | Sending Chunk Data [Fast Map]", module="fastmap")
            for chunkCount, chunk in enumerate(chunks):
                # Sending Chunk Data
                Logger.verbose(f"{self.connectionInfo} | Sending Chunk Data {chunkCount + 1} of {len(chunks)} [Fast Map]", module="fastmap")
                await self.dispatcher.sendPacket(Packets.Response.LevelDataChunk, chunk, percentComplete=int((100 / len(chunks)) * chunkCount))

            # Send Level Finalize Packet
            Logger.debug(f"{self.connectionInfo} | Sending Level Finalize Packet [Fast Map]", module="fastmap")
            await self.dispatcher.sendPacket(
                Packets.Response.LevelFinalize,
                world.sizeX,
                world.sizeY,
                world.sizeZ
            )

    @staticmethod
    def deflateMap(networkHandler: NetworkHandler, world: World, compressionLevel: int = 9) -> bytes:
        # Invalid Compression Level!
        if not 0 <= compressionLevel <= 9:
            raise ServerError(f"Invalid Deflate Compression Level Of {compressionLevel}!!!")

        Logger.debug(f"Compressing Map {world.name} With Compression Level {compressionLevel}", module="deflate")
        # Create compressor object
        compressor = zlib.compressobj(
            level=compressionLevel,
            method=zlib.DEFLATED,
            wbits=-zlib.MAX_WBITS,
            memLevel=zlib.DEF_MEM_LEVEL,
            strategy=zlib.Z_DEFAULT_STRATEGY
        )

        # Deflate Data
        deflatedData = compressor.compress(world.mapArray)
        deflatedData += compressor.flush()

        Logger.debug(f"Deflated Map! DEFLATE SIZE: {len(deflatedData)}", module="deflate")
        return deflatedData

    @ResponsePacket(
        "FastMapLevelInitialize",
        description="Packet To Begin World Data Transfer with the FastMap extension",
        override=True
    )
    class FastMapLevelInitializePacket(AbstractResponsePacket["FastMapModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x02,
                FORMAT="!BI",
                CRITICAL=True
            )

        async def serialize(self, size: int):
            # <(FastMap) Level Initialize Packet>
            # (Byte) Packet ID
            # (Integer) Size Of Map
            msg = struct.pack(self.FORMAT, self.ID, size)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # Config for default click distance
    @dataclass
    class FastMapConfig(AbstractConfig):
        deflateCompressionLevel: int = 6
