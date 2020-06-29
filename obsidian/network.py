from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server

import asyncio
from typing import Type

from obsidian.log import Logger
from obsidian.world import World
from obsidian.packet import (
    Packets,
    AbstractRequestPacket,
    AbstractResponsePacket
)
from obsidian.constants import (
    NET_TIMEOUT,
    CRITICAL_REQUEST_ERRORS,
    CRITICAL_RESPONSE_ERRORS,
    ClientError
)


class NetworkHandler:
    def __init__(self, server: Server, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.ip: tuple = self.reader._transport.get_extra_info("peername")  # type: ignore
        self.dispacher = NetworkDispacher(self)
        self.isConnected = True  # Connected Flag So Outbound Queue Buffer Can Stop
        # self.player = None

    async def initConnection(self, *args, **kwargs):
        try:
            return await self._initConnection(*args, **kwargs)
        except ClientError as e:
            Logger.warn(f"Client Error, Disconnecting Ip {self.ip} - {type(e).__name__}: {e}", module="network")
            await self.dispacher.sendPacket(Packets.Response.DisconnectPlayer, "Disconnected: " + str(e))
            self.writer.close()
        except BrokenPipeError:
            Logger.warn(f"Ip {self.ip} Broken Pipe. Closing Connection.", module="network")
            self.isConnected = False
            self.writer.close()
        except ConnectionResetError:
            Logger.warn(f"Ip {self.ip} Connection Reset. Closing Connection.", module="network")
            self.isConnected = False
            self.writer.close()
        except asyncio.IncompleteReadError:
            Logger.warn(f"Ip {self.ip} Incomplete Read Error. Closing Connection.", module="network")
            self.isConnected = False
            self.writer.close()
        except Exception as e:
            Logger.error(f"Error While Handling Connection {self.ip} - {type(e).__name__}: {e}", "network")
            self.isConnected = False
            try:
                await self.dispacher.sendPacket(Packets.Response.DisconnectPlayer, "Disconnected: Internal Server Error")
                self.writer.close()
            except Exception:
                Logger.warn("Internal Server Error Disconnect Packet Failed To Send!!!!!")

    async def _initConnection(self):
        # Log Connection
        Logger.info(f"New Connection From {self.ip}", module="network")

        # Start the server <-> client login protocol
        Logger.debug(f"{self.ip} | Starting Client <-> Server Handshake", module="network")
        await self._handleInitialHandshake()

    async def _handleInitialHandshake(self):
        # Wait For Player Identification Packet
        Logger.debug(f"{self.ip} | Waiting For Initial Player Information Packet", module="network")
        protocolVersion, username, verificationKey = await self.dispacher.readPacket(Packets.Request.PlayerIdentification)

        # Checking Client Protocol Version
        if protocolVersion > self.server.protocolVersion:
            raise ClientError(f"Server Outdated (Client: {protocolVersion}, Server: {self.server.protocolVersion:})")
        elif protocolVersion < self.server.protocolVersion:
            raise ClientError(f"Client Outdated (Client: {protocolVersion}, Server: {self.server.protocolVersion:})")

        # Send Server Information Packet
        Logger.debug(f"{self.ip} | Sending Initial Server Information Packet", module="network")
        await self.dispacher.sendPacket(Packets.Response.ServerIdentification, self.server.protocolVersion, self.server.name, self.server.motd, 0x00)

        # Sending World Data Of Default World
        Logger.debug(f"{self.ip} | Preparing To Send World {self.server.defaultWorld}", module="network")
        await self.sendWorldData(self.server.worldManager.worlds[self.server.defaultWorld])

        # Setting Up Ping Loop To Check Connection
        while True:
            await self.dispacher.sendPacket(Packets.Response.Ping)
            await asyncio.sleep(1)

    async def sendWorldData(self, world: World):
        # Send Level Initialize Packet
        Logger.debug(f"{self.ip} | Sending Level Initialize Packet", module="network")
        await self.dispacher.sendPacket(Packets.Response.LevelInitialize)

        # Preparing To Send Map
        Logger.debug(f"{self.ip} | Preparing To Send Map", module="network")
        worldGzip = world.gzipMap(includeSizeHeader=True)  # Generate GZIP
        # World Data Needs To Be Sent In Chunks Of 1024 Characters
        chunks = [worldGzip[i: i + 1024] for i in range(0, len(worldGzip), 1024)]

        # Looping Through All Chunks And Sending Data
        for chunkCount, chunk in enumerate(chunks):
            # Sending Chunk Data
            Logger.debug(f"{self.ip} | Sending Chunk Data {chunkCount + 1} of {len(chunks)}", module="network")
            await self.dispacher.sendPacket(Packets.Response.LevelDataChunk, chunk, percentComplete=int((100 / len(chunks)) * chunkCount))

        # Send Level Finalize Packet
        Logger.debug(f"{self.ip} | Sending Level Finalize Packet", module="network")
        await self.dispacher.sendPacket(
            Packets.Response.LevelFinalize,
            world.sizeX,
            world.sizeY,
            world.sizeZ
        )


class NetworkDispacher:
    def __init__(self, handler: NetworkHandler):
        self.player = None
        self.handler = handler

    # Used in main listen loop; expect multiple types of packets!
    async def listenForPacket(self, timeout=NET_TIMEOUT):
        pass

    # NOTE: or call receivePacket
    # Used when exact packet is expected
    async def readPacket(
        self,
        packet: Type[AbstractRequestPacket],
        timeout=NET_TIMEOUT,
        checkId=True,
    ):
        try:
            # Get Packet Data
            Logger.verbose(f"Expected Packet {packet.ID} Size {packet.SIZE} from {self.handler.ip}", module="network")
            rawData = await asyncio.wait_for(
                self.handler.reader.readexactly(
                    packet.SIZE
                ), timeout)
            Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.ip} | DATA: {rawData}", module="network")

            # Check If Packet ID is Valid
            if checkId and rawData[0] != packet.ID:
                Logger.verbose(f"{self.handler.ip} | Packet Invalid!", module="network")
                raise ClientError(f"Invalid Packet {rawData[0]}")

            # Deserialize Packet
            # TODO: Fix type complaint!
            serializedData = packet.deserialize(rawData)  # type: ignore
            return serializedData
        except asyncio.TimeoutError:
            raise ClientError(f"Did Not Receive Packet {packet.ID} In Time!")
        except Exception as e:
            if packet.CRITICAL or type(e) in CRITICAL_REQUEST_ERRORS:
                raise e  # Pass Down Exception To Lower Layer
            else:
                # TODO: Remove Hacky Type Ignore
                return packet.onError(e)  # type: ignore

    async def sendPacket(
        self,
        packet: Type[AbstractResponsePacket],
        *args,
        timeout=NET_TIMEOUT,
        **kwargs
    ):
        try:
            # Generate Packet
            rawData = packet.serialize(*args, **kwargs)

            # Send Packet
            Logger.verbose(f"SERVER -> CLIENT | CLIENT: {self.handler.ip} | ID: {packet.ID} | SIZE: {packet.SIZE} | DATA: {rawData}", module="network")
            if self.handler.isConnected:
                self.handler.writer.write(rawData)
                await self.handler.writer.drain()
            else:
                Logger.debug(f"Packet {packet.NAME} Skipped Due To Closed Connection!")
        except Exception as e:
            # Making Sure These Errors Always Gets Raised (Ignore onError)
            if packet.CRITICAL or type(e) in CRITICAL_RESPONSE_ERRORS:
                raise e  # Pass Down Exception To Lower Layer
            else:
                # TODO: Remove Hacky Type Ignore
                return packet.onError(e)  # type: ignore

    # Initialize Regerster Packer Handler
    def registerInit(self, module: str):
        pass  # Unused for now
