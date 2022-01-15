from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server

import asyncio
from typing import Type, Optional

from obsidian.log import Logger
from obsidian.world import World
from obsidian.player import Player
from obsidian.packet import (
    PacketManager, Packets,
    AbstractRequestPacket,
    AbstractResponsePacket
)
from obsidian.constants import (
    NET_TIMEOUT,
    CRITICAL_REQUEST_ERRORS,
    CRITICAL_RESPONSE_ERRORS
)
from obsidian.errors import (
    ServerError,
    ClientError
)
from obsidian.types import (
    IpType
)


class NetworkHandler:
    def __init__(self, server: Server, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.server: Server = server
        self.reader: asyncio.StreamReader = reader
        self.writer: asyncio.StreamWriter = writer
        self.conninfo: tuple[str, int] = self.writer.get_extra_info('peername')
        self.ip: IpType = IpType(self.conninfo[0])
        self.port: int = self.conninfo[1]
        self.dispacher: NetworkDispacher = NetworkDispacher(self)
        self.isConnected: bool = True  # Connected Flag So Outbound Queue Buffer Can Stop
        self.player: Optional[Player] = None

    async def initConnection(self, *args, **kwargs):
        try:
            return await self._initConnection(*args, **kwargs)
        except ClientError as e:
            Logger.warn(f"Client Error, Disconnecting Ip {self.conninfo} - {type(e).__name__}: {e}", module="network")
            await self.closeConnection(reason=str(e), notifyPlayer=True)
        except BrokenPipeError:
            Logger.warn(f"Ip {self.conninfo} Broken Pipe. Closing Connection.", module="network")
            await self.closeConnection(reason="Broken Pipe")
        except ConnectionResetError:
            Logger.warn(f"Ip {self.conninfo} Connection Reset. Closing Connection.", module="network")
            await self.closeConnection(reason="Connection Reset")
        except asyncio.IncompleteReadError:
            Logger.warn(f"Ip {self.conninfo} Incomplete Read Error. Closing Connection.", module="network")
            await self.closeConnection(reason="Incomplete Read Error")
        except Exception as e:
            Logger.error(f"Error While Handling Connection {self.conninfo} - {type(e).__name__}: {e}", module="network")
            try:
                await self.closeConnection(reason="Internal Server Error", notifyPlayer=True)
            except Exception as e:
                Logger.error(f"Close Connected Failed To Complete Successfully - {type(e).__name__}: {e}", module="network")

    async def _initConnection(self):
        # Log Connection
        Logger.info(f"New Connection From {self.conninfo}", module="network")

        # Check if user is IP banned
        if self.ip in self.server.config.bannedIps:
            Logger.info(f"IP {self.conninfo} Is Banned. Kicking!", module="network")
            raise ClientError("Your IP Has Been Banned From The Server!")

        # Start the server <-> client login protocol
        Logger.debug(f"{self.conninfo} | Starting Client <-> Server Handshake", module="network")
        await self._handleInitialHandshake()

    async def _handleInitialHandshake(self):
        # Double Check Server is Initialized
        if not self.server.initialized or not self.server.worldManager or not self.server.playerManager:
            raise ServerError("Cannot Initialize Handshake Protocol When Server is not Initialized!")

        # Wait For Player Identification Packet
        Logger.debug(f"{self.conninfo} | Waiting For Initial Player Information Packet", module="network")
        protocolVersion, username, verificationKey = await self.dispacher.readPacket(Packets.Request.PlayerIdentification)

        # Checking Client Protocol Version
        if protocolVersion > self.server.protocolVersion:
            raise ClientError(f"Server Outdated (Client: {protocolVersion}, Server: {self.server.protocolVersion})")
        elif protocolVersion < self.server.protocolVersion:
            raise ClientError(f"Client Outdated (Client: {protocolVersion}, Server: {self.server.protocolVersion})")

        # Create Player
        Logger.debug(f"{self.conninfo} | Creating Player {username}", module="network")
        self.player = await self.server.playerManager.createPlayer(self, username, verificationKey)

        # Send Server Information Packet
        Logger.debug(f"{self.conninfo} | Sending Initial Server Information Packet", module="network")
        await self.dispacher.sendPacket(Packets.Response.ServerIdentification, self.server.protocolVersion, self.server.name, self.server.motd, 0x00)

        # Sending World Data Of Default World
        defaultWorld = self.server.worldManager.worlds[self.server.config.defaultWorld]
        Logger.debug(f"{self.conninfo} | Preparing To Send World {defaultWorld.name}", module="network")
        await self.sendWorldData(defaultWorld)

        # Join Default World
        Logger.debug(f"{self.conninfo} | Joining Default World {defaultWorld.name}", module="network")
        await self.player.joinWorld(defaultWorld)

        # Player Spawn Packet
        Logger.debug(f"{self.conninfo} | Preparing To Send Spawn Player Information", module="network")
        await self.dispacher.sendPacket(
            Packets.Response.SpawnPlayer,
            255,
            username,
            defaultWorld.spawnX,
            defaultWorld.spawnY,
            defaultWorld.spawnZ,
            defaultWorld.spawnYaw,
            defaultWorld.spawnPitch
        )

        # Send MOTD to user
        Logger.debug(f"{self.conninfo} | Sending MOTD", module="network")
        await self.player.sendMOTD()

        # Setup And Begin Player Loop
        Logger.debug(f"{self.conninfo} | Starting Player Loop", module="network")
        await self._beginPlayerLoop()

    async def _beginPlayerLoop(self):
        # Called to handle Player Loop Packets
        # (Packets Sent During Normal Player Gameplay)
        while self.isConnected:
            # Listen and Handle Incoming Packets
            await self.dispacher.listenForPackets(packetDict=PacketManager.Request.loopPackets)

    async def _processWorldChange(self, world: World, previousWorld: World, updateServerInfo: bool = True):
        # TODO: updateServerInfoWhileSwitching is included because IDK if clients would like it.
        # Its an undocumented feature, so look into if its part of the defacto standard
        # This is use changable in config

        # Check if player is joined in a world in the first place
        if self.player is None:
            raise ServerError("Trying To Change World When NetworkHandler Has No Player...")
        if self.player.worldPlayerManager is None:
            raise ServerError(f"Player {self.player.name} Not In World")

        # Change Server Information To Include "Switching Server..."
        if updateServerInfo:
            Logger.debug(f"{self.conninfo} | Changing Server Information Packet", module="change-world")
            await self.dispacher.sendPacket(Packets.Response.ServerIdentification, self.server.protocolVersion, self.server.name, f"Joining {world.name}...", 0x00)

        # Disconnect Player from Current World Manager and Remove worldPlayerManager from user
        Logger.debug(f"{self.conninfo} | Removing Player From Current World {previousWorld.name}", module="change-world")
        await self.player.worldPlayerManager.removePlayer(self.player)
        self.player.worldPlayerManager = None

        # Sending World Data Of Default World
        Logger.debug(f"{self.conninfo} | Preparing To Send World {world.name}", module="change-world")
        await self.sendWorldData(world)

        # Join Default World
        Logger.debug(f"{self.conninfo} | Joining New World {world.name}", module="change-world")
        await self.player.joinWorld(world)

        # Player Spawn Packet
        Logger.debug(f"{self.conninfo} | Preparing To Send Spawn Player Information", module="change-world")
        await self.dispacher.sendPacket(
            Packets.Response.SpawnPlayer,
            255,
            self.player.username,
            world.spawnX,
            world.spawnY,
            world.spawnZ,
            world.spawnYaw,
            world.spawnPitch
        )

        # Change Server Information Back To Original
        if updateServerInfo:
            Logger.debug(f"{self.conninfo} | Changing Server Information Packet Back To Original", module="change-world")
            await self.dispacher.sendPacket(Packets.Response.ServerIdentification, self.server.protocolVersion, self.server.name, self.server.motd, 0x00)

    async def sendWorldData(self, world: World):
        # Send Level Initialize Packet
        Logger.debug(f"{self.conninfo} | Sending Level Initialize Packet", module="network")
        await self.dispacher.sendPacket(Packets.Response.LevelInitialize)

        # Preparing To Send Map
        Logger.debug(f"{self.conninfo} | Preparing To Send Map", module="network")
        worldGzip = world.gzipMap(includeSizeHeader=True)  # Generate GZIP
        # World Data Needs To Be Sent In Chunks Of 1024 Characters
        chunks = [worldGzip[i: i + 1024] for i in range(0, len(worldGzip), 1024)]

        # Looping Through All Chunks And Sending Data
        Logger.debug(f"{self.conninfo} | Sending Chunk Data", module="network")
        for chunkCount, chunk in enumerate(chunks):
            # Sending Chunk Data
            Logger.verbose(f"{self.conninfo} | Sending Chunk Data {chunkCount + 1} of {len(chunks)}", module="network")
            await self.dispacher.sendPacket(Packets.Response.LevelDataChunk, chunk, percentComplete=int((100 / len(chunks)) * chunkCount))

        # Send Level Finalize Packet
        Logger.debug(f"{self.conninfo} | Sending Level Finalize Packet", module="network")
        await self.dispacher.sendPacket(
            Packets.Response.LevelFinalize,
            world.sizeX,
            world.sizeY,
            world.sizeZ
        )

    async def closeConnection(self, reason: Optional[str] = None, notifyPlayer: bool = False):
        # Setting Up Reason If None
        if reason is None:
            reason = "No Reason Provided"

        # Check if user has already been disconnected
        if not self.isConnected:
            Logger.debug("User Already Disconnected.", module="network")
            return

        # Removing and Cleaning Up Player If Necessary
        if self.player is not None:
            Logger.debug("Closing and Cleaning Up User", module="network")
            await self.player.playerManager.deletePlayer(self.player)

        Logger.debug(f"Closing Connection {self.conninfo} For Reason {reason}", module="network")
        # Send Disconnect Message
        if notifyPlayer:
            await self.dispacher.sendPacket(Packets.Response.DisconnectPlayer, f"Disconnected: {reason}")

        # Set Disconnect Flags
        self.isConnected = False
        self.writer.close()


class NetworkDispacher:
    def __init__(self, handler: NetworkHandler):
        self.handler: NetworkHandler = handler

    # NOTE: or call receivePacket
    # Used when exact packet is expected
    async def readPacket(
        self,
        packet: AbstractRequestPacket,
        timeout: int = NET_TIMEOUT,
        critical: bool = False,  # Hacky critical flag to please type checker
        checkId=True
    ):
        try:
            # Get Packet Data
            Logger.verbose(f"Expected Packet {packet.ID} Size {packet.SIZE} from {self.handler.conninfo}", module="network")
            rawData = await asyncio.wait_for(
                self.handler.reader.readexactly(
                    packet.SIZE
                ), timeout
            )
            Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.conninfo} | DATA: {rawData}", module="network")

            # Check If Packet ID is Valid
            header = rawData[0]
            if checkId and header != packet.ID:
                Logger.verbose(f"{self.handler.conninfo} | Packet Invalid!", module="network")
                raise ClientError(f"Invalid Packet {header}")

            # Deserialize Packet
            serializedData = await packet.deserialize(self.handler.player, rawData)
            return serializedData
        except asyncio.TimeoutError:
            raise ClientError(f"Did Not Receive Packet {packet.ID} In Time!")
        except Exception as e:
            if packet.CRITICAL or type(e) in CRITICAL_REQUEST_ERRORS or critical:
                raise e  # Pass Down Exception To Lower Layer
            else:
                packet.onError(e)
                raise e

    async def sendPacket(
        self,
        packet: Type[AbstractResponsePacket],
        *args,
        timeout: int = NET_TIMEOUT,
        **kwargs
    ):
        try:
            # Generate Packet
            rawData = await packet.serialize(*args, **kwargs)

            # Send Packet
            Logger.verbose(f"SERVER -> CLIENT | CLIENT: {self.handler.conninfo} | ID: {packet.ID} {packet.NAME} | SIZE: {packet.SIZE} | DATA: {rawData}", module="network")
            if self.handler.isConnected:
                self.handler.writer.write(bytes(rawData))
                await self.handler.writer.drain()
            else:
                Logger.debug(f"Packet {packet.NAME} Skipped Due To Closed Connection!", module="network")
        except Exception as e:
            # Making Sure These Errors Always Gets Raised (Ignore onError)
            if packet.CRITICAL or type(e) in CRITICAL_RESPONSE_ERRORS:
                raise e  # Pass Down Exception To Lower Layer
            else:
                return packet.onError(e)

    # Used in main listen loop; expect multiple types of packets!
    async def listenForPackets(
        self,
        packetDict: dict = {},
        headerSize: int = 1,
        ignoreUnknownPackets: bool = False,
        timeout: int = NET_TIMEOUT
    ):
        try:
            # Reading First Byte For Packet Header
            rawData = await asyncio.wait_for(
                self.handler.reader.readexactly(
                    headerSize  # Size of packet header
                ), timeout
            )
            Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.conninfo} | Incoming Player Loop Packet Id {rawData}", module="network")

            # Convert Packet Header to Int
            packetHeader = int.from_bytes(rawData, byteorder="big")

            # Check if packet is to be expected
            if packetHeader not in packetDict.keys():
                # Ignore if ignoreUnknownPackets flag is set
                if not ignoreUnknownPackets:
                    Logger.debug(f"Player Sent Unknown Packet Header {rawData} ({packetHeader})", module="network")
                    raise ClientError(f"Unknown Packet {packetHeader}")

            # Get packet using packetId
            packet = PacketManager.Request.getPacketById(packetHeader)

            # Reading and Appending Rest Of Packet Data (Packet Body)
            rawData += await asyncio.wait_for(
                self.handler.reader.readexactly(
                    packet.SIZE - headerSize  # Size of packet body (packet minus header size)
                ), timeout
            )
            Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.conninfo} | DATA: {rawData}", module="network")

            # Attempting to Deserialize Packets
            try:
                # Deserialize Packet
                serializedData = await packet.deserialize(self.handler.player, rawData)
                return packetHeader, serializedData

            except Exception as e:
                if packet.CRITICAL or type(e) in CRITICAL_REQUEST_ERRORS:
                    raise e  # Pass Down Exception To Lower Layer
                else:
                    return packetHeader, packet.onError(e)

        except asyncio.TimeoutError:
            # Some clients don't send info when not moving
            # Send Ping Packet (Make sure client is still connected)
            Logger.debug(f"{self.handler.conninfo} | Sending Connection Ping", module="network")
            await self.handler.dispacher.sendPacket(Packets.Response.Ping)
            # raise ClientError("Did Not Receive Packet In Time!")
        except Exception as e:
            raise e  # Pass Down Exception To Lower Layer
