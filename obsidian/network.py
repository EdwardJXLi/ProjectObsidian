from __future__ import annotations

import asyncio
import hashlib
from typing import Type, Optional, Callable, TYPE_CHECKING

from obsidian.log import Logger
from obsidian.world import World
from obsidian.player import Player
from obsidian.cpe import CPEExtension
from obsidian.packet import (
    PacketManager, Packets,
    AbstractRequestPacket,
    AbstractResponsePacket
)
from obsidian.constants import (
    __version__,
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

if TYPE_CHECKING:
    from obsidian.server import Server


class NetworkHandler:
    def __init__(self, server: Server, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.server: Server = server
        self.reader: asyncio.StreamReader = reader
        self.writer: asyncio.StreamWriter = writer
        self.connectionInfo: tuple[str, int] = self.writer.get_extra_info('peername')
        self.ip: IpType = IpType(self.connectionInfo[0])
        self.port: int = self.connectionInfo[1]
        self.dispatcher: NetworkDispatcher = NetworkDispatcher(self)
        self.isConnected: bool = True  # Connected Flag So Outbound Queue Buffer Can Stop
        self.inLoop: bool = False  # In Loop Flag so that functions know when to use a different implementation
        self.player: Optional[Player] = None

    async def initConnection(self, *args, **kwargs):
        try:
            return await self._initConnection(*args, **kwargs)
        except ClientError as e:
            Logger.warn(f"Client Error, Disconnecting Ip {self.connectionInfo} - {type(e).__name__}: {e}", module="network")
            await self.closeConnection(str(e), notifyPlayer=True, chatMessage="Client Error")
        except BrokenPipeError:
            Logger.warn(f"Ip {self.connectionInfo} Broken Pipe. Closing Connection.", module="network")
            await self.closeConnection("Broken Pipe", chatMessage="Disconnected")
        except ConnectionResetError:
            Logger.warn(f"Ip {self.connectionInfo} Connection Reset. Closing Connection.", module="network")
            await self.closeConnection("Connection Reset", chatMessage="Disconnected")
        except asyncio.IncompleteReadError:
            Logger.warn(f"Ip {self.connectionInfo} Incomplete Read Error. Closing Connection.", module="network")
            await self.closeConnection("Incomplete Read Error", chatMessage="Disconnected")
        except asyncio.TimeoutError:
            Logger.warn(f"Ip {self.connectionInfo} Timeout Error. Closing Connection.", module="network")
            await self.closeConnection("Timeout Error", chatMessage="Disconnected")
        except Exception as e:
            Logger.error(f"Error While Handling Connection {self.connectionInfo} - {type(e).__name__}: {e}", module="network")
            try:
                await self.closeConnection("Internal Server Error", notifyPlayer=True)
            except Exception as ex:
                Logger.error(f"Close Connected Failed To Complete Successfully - {type(ex).__name__}: {ex}", module="network")

    async def _initConnection(self):
        # Log Connection
        Logger.info(f"New Connection From {self.connectionInfo}", module="network")

        # Check if user is IP banned
        if self.ip in self.server.config.bannedIps:
            Logger.info(f"IP {self.connectionInfo} Is Banned. Kicking!", module="network")
            raise ClientError("Your IP Has Been Banned From The Server!")

        # Start the server <-> client login protocol
        Logger.debug(f"{self.connectionInfo} | Starting Client <-> Server Handshake", module="network")
        await self._handleInitialHandshake()

    async def _handleInitialHandshake(self):
        # Double Check Server is Initialized
        if not self.server.initialized or not self.server.worldManager or not self.server.playerManager:
            raise ServerError("Cannot Initialize Handshake Protocol When Server is not Initialized!")

        # Wait For Player Identification Packet
        Logger.debug(f"{self.connectionInfo} | Waiting For Initial Player Information Packet", module="network")
        protocolVersion, username, verificationKey, supportsCPE = await self.dispatcher.readPacket(Packets.Request.PlayerIdentification)

        # Checking Client Protocol Version
        if protocolVersion > self.server.protocolVersion:
            raise ClientError(f"Server Outdated (Client: {protocolVersion}, Server: {self.server.protocolVersion})")
        if protocolVersion < self.server.protocolVersion:
            raise ClientError(f"Client Outdated (Client: {protocolVersion}, Server: {self.server.protocolVersion})")

        # Verify login - Calculates if md5(salt + name) is equal to verificationKey
        if verificationKey != hashlib.md5(self.server.salt.encode() + username.encode()).hexdigest():
            authenticated = False
            Logger.warn(f"User {username} tried logging in with invalid verification key {verificationKey}!", module="network")
            Logger.debug(f"{self.connectionInfo} | Login verification FAILED for Player {username}", module="network")
            if self.server.config.verifyLogin:
                raise ClientError("Username Verification Failed!")
        else:
            authenticated = True
            Logger.debug(f"{self.connectionInfo} | Login verified for Player {username}", module="network")

        # Create Player
        Logger.debug(f"{self.connectionInfo} | Creating Player {username}", module="network")
        self.player = await self.server.playerManager.createPlayer(self, username, verificationKey, authenticated)

        # If client supports CPE and if server enables CPE, start CPE negotiation
        # CPE stands for Classic Protocol Extension, and is defined here: https://wiki.vg/Classic_Protocol_Extension
        if supportsCPE and self.server.config.enableCPE:
            Logger.info("Client Supports CPE, Starting CPE Negotiation", module="network")
            await self._handleCPENegotiation()

        # Send Server Information Packet
        Logger.debug(f"{self.connectionInfo} | Sending Initial Server Information Packet", module="network")
        await self.dispatcher.sendPacket(Packets.Response.ServerIdentification, self.server.protocolVersion, self.server.name, self.server.motd, 0x00)

        # Sending World Data Of Default World
        defaultWorld = self.server.worldManager.worlds[self.server.config.defaultWorld]
        Logger.debug(f"{self.connectionInfo} | Preparing To Send World {defaultWorld.name}", module="network")
        await self.sendWorldData(defaultWorld)

        # Send global message that player has connected to the server
        Logger.debug(f"{self.connectionInfo} | Sending Global Player Join Message", module="network")
        await self.player.playerManager.sendGlobalMessage(f"&2{self.player.name} connected to the server!")

        # Join Default World
        Logger.debug(f"{self.connectionInfo} | Joining Default World {defaultWorld.name}", module="network")
        await self.player.joinWorld(defaultWorld)

        # Player Spawn Packet
        Logger.debug(f"{self.connectionInfo} | Preparing To Send Spawn Player Information", module="network")
        await self.dispatcher.sendPacket(
            Packets.Response.SpawnPlayer,
            255,
            username,
            self.player.posX,
            self.player.posY,
            self.player.posZ,
            self.player.posYaw,
            self.player.posPitch
        )

        # Perform any post login actions
        Logger.debug(f"{self.connectionInfo} | Performing Post Login Actions", module="network")
        await self._processPostLogin()

        # Setup And Begin Player Loop
        Logger.debug(f"{self.connectionInfo} | Starting Player Loop", module="network")
        await self._beginPlayerLoop()

    async def _handleCPENegotiation(self):
        # Check that CPE is enabled and server.cpe is not None
        if not self.server.supportsCPE:
            raise ServerError("Server Does Not Support CPE!")

        # Sanity check that this should be called after player initialization
        if not self.player:
            raise ServerError("CPE Negotiation Called Before Player Initialization!")

        # Enable CPE support on the player
        self.player.supportsCPE = True

        # Send Server ExtInfo Packet
        Logger.debug(f"{self.connectionInfo} | Sending Server CPE ExtInfo (Extension Info) Packet", module="network")
        await self.dispatcher.sendPacket(Packets.Response.ServerExtInfo, f"ProjectObsidian - {__version__}", len(self.server.getSupportedCPE()))

        # Send ExtEntry Packet For Each Extension that server supports
        Logger.debug(f"{self.connectionInfo} | Sending Server CPE ExtEntry (Extension Entry) Packets", module="network")
        Logger.debug(f"{self.connectionInfo} | Server supports {len(self.server.getSupportedCPE())} extensions", module="network")
        for extension in self.server.getSupportedCPE():
            Logger.debug(f"{self.connectionInfo} | Sending Server CPE ExtEntry for {extension.name} version {extension.version}", module="network")
            await self.dispatcher.sendPacket(Packets.Response.ServerExtEntry, extension.name, extension.version)

        # Receive Client ExtInfo Packet
        Logger.debug(f"{self.connectionInfo} | Waiting For Player CPE ExtInfo (Extension Info) Packet", module="network")
        clientSoftware, extensionCount = await self.dispatcher.readPacket(Packets.Request.PlayerExtInfo)
        Logger.debug(f"{self.connectionInfo} | ExtInfo Received! Client supports {extensionCount} extensions", module="network")
        Logger.debug(f"{self.connectionInfo} | Client is also running on software: {clientSoftware}", module="network")
        self.player.clientSoftware = clientSoftware

        # Receive Client ExtEntry Packets
        for extNum in range(extensionCount):
            Logger.debug(f"{self.connectionInfo} | Waiting Client CPE ExtEntry #{extNum}", module="network")
            extName, extVersion = await self.dispatcher.readPacket(Packets.Request.PlayerExtEntry)
            Logger.debug(f"{self.connectionInfo} | ExtEntry Received! Client supports {extName} version {extVersion}", module="network")
            self.player._extensions.add(CPEExtension(extName, extVersion))

        # Finish CPE Negotiation
        Logger.info(f"{self.connectionInfo} | Finished CPE Negotiation", module="network")

    async def _processPostLogin(self):
        # Check if player is not None
        if self.player is None:
            raise ServerError("Trying To Process Post Login Actions Before Player Is Initialized!")

        # Send MOTD to user
        Logger.debug(f"{self.connectionInfo} | Sending MOTD", module="network")
        await self.player.sendMOTD()

    async def _beginPlayerLoop(self):
        # Set the inLoop flag
        self.inLoop = True
        # Called to handle Player Loop Packets
        # (Packets Sent During Normal Player Gameplay)
        while self.isConnected:
            # Listen and Handle Incoming Packets
            await self.dispatcher.listenForPackets(packetDict=PacketManager.Request.loopPackets)

    async def _processWorldChange(self, world: World, previousWorld: World):
        # Check if player is joined in a world in the first place
        if self.player is None:
            raise ServerError("Trying To Change World When NetworkHandler Has No Player...")
        if self.player.worldPlayerManager is None:
            raise ServerError(f"Player {self.player.name} Not In World")

        # Change Server Information To Include "Switching Server..."
        Logger.debug(f"{self.connectionInfo} | Changing Server Information Packet", module="change-world")
        await self.dispatcher.sendPacket(Packets.Response.ServerIdentification, self.server.protocolVersion, self.server.name, f"Joining {world.name}...", 0x00)

        # Disconnect Player from Current World Manager and Remove worldPlayerManager from user
        Logger.debug(f"{self.connectionInfo} | Removing Player From Current World {previousWorld.name}", module="change-world")
        await self.player.worldPlayerManager.removePlayer(self.player, reason=f"Switching World To {world.name}")
        self.player.worldPlayerManager = None

        # Sending World Data Of Default World
        Logger.debug(f"{self.connectionInfo} | Preparing To Send World {world.name}", module="change-world")
        await self.sendWorldData(world)

        # Join Default World
        Logger.debug(f"{self.connectionInfo} | Joining New World {world.name}", module="change-world")
        await self.player.joinWorld(world)

        # Player Spawn Packet
        Logger.debug(f"{self.connectionInfo} | Preparing To Send Spawn Player Information", module="change-world")
        await self.dispatcher.sendPacket(
            Packets.Response.SpawnPlayer,
            255,
            self.player.username,
            self.player.posX,
            self.player.posY,
            self.player.posZ,
            self.player.posYaw,
            self.player.posPitch
        )

    async def sendWorldData(self, world: World):
        # Send Level Initialize Packet
        Logger.debug(f"{self.connectionInfo} | Sending Level Initialize Packet", module="network")
        await self.dispatcher.sendPacket(Packets.Response.LevelInitialize)

        # Preparing To Send Map
        Logger.debug(f"{self.connectionInfo} | Preparing To Send Map", module="network")
        worldGzip = world.gzipMap(includeSizeHeader=True)  # Generate GZIP
        # World Data Needs To Be Sent In Chunks Of 1024 Characters
        chunks = [worldGzip[i: i + 1024] for i in range(0, len(worldGzip), 1024)]

        # Looping Through All Chunks And Sending Data
        Logger.debug(f"{self.connectionInfo} | Sending Chunk Data", module="network")
        for chunkCount, chunk in enumerate(chunks):
            # Sending Chunk Data
            Logger.verbose(f"{self.connectionInfo} | Sending Chunk Data {chunkCount + 1} of {len(chunks)}", module="network")
            await self.dispatcher.sendPacket(Packets.Response.LevelDataChunk, chunk, percentComplete=int((100 / len(chunks)) * chunkCount))

        # Send Level Finalize Packet
        Logger.debug(f"{self.connectionInfo} | Sending Level Finalize Packet", module="network")
        await self.dispatcher.sendPacket(
            Packets.Response.LevelFinalize,
            world.sizeX,
            world.sizeY,
            world.sizeZ
        )

    async def closeConnection(self, reason: str, notifyPlayer: bool = False, chatMessage: Optional[str] = None):
        # Check if user has already been disconnected
        if not self.isConnected:
            Logger.debug("User Already Disconnected.", module="network")
            return

        # Removing and Cleaning Up Player If Necessary
        if self.player is not None:
            # Remove player from the current world
            Logger.debug("Closing and Cleaning Up User", module="network")
            await self.player.playerManager.deletePlayer(self.player, reason=chatMessage)

            # Send global message that player has disconnected from the server
            Logger.debug(f"{self.connectionInfo} | Sending Global Player Leave Message", module="network")
            await self.player.playerManager.sendGlobalMessage(f"&2{self.player.name} disconnected from the server!")

        Logger.debug(f"Closing Connection {self.connectionInfo} For Reason {reason}", module="network")
        # Send Disconnect Message
        if notifyPlayer:
            try:
                await self.dispatcher.sendPacket(Packets.Response.DisconnectPlayer, f"Disconnected: {reason}")
            except Exception as e:
                if e not in CRITICAL_RESPONSE_ERRORS:
                    # Something Broke!
                    Logger.error(f"An Error Occurred While Disconnect Packet - {type(e).__name__}: {e}", module="network")
                else:
                    # Bad Timing with Connection Closure. Ignoring
                    Logger.debug("Ignoring Error While Sending Disconnect Packet", module="network")

        # Set Disconnect Flags
        self.isConnected = False
        self.writer.close()


class NetworkDispatcher:
    def __init__(self, handler: NetworkHandler):
        self.handler: NetworkHandler = handler
        # Dictionary: {(Key)<Type of AbstractRequestPacket> : (Values)list[tuple[<Future Event>, <Check Function>, <Should Continue Handling>]]}
        self._listeners: dict[Type[AbstractRequestPacket], list[tuple[asyncio.Future, Callable[..., bool], bool]]] = {}

    # NOTE: or call receivePacket
    # Used when exact packet is expected
    async def readPacket(
        self,
        packet: AbstractRequestPacket,
        timeout: float = NET_TIMEOUT,
        critical: bool = False,  # Hacky critical flag to please type checker
        checkId=True
    ):
        try:
            # Get Packet Data
            Logger.verbose(f"Expected Packet {packet.ID} Size {packet.SIZE} from {self.handler.connectionInfo}", module="network")
            rawData = await asyncio.wait_for(
                self.handler.reader.readexactly(
                    packet.SIZE
                ), timeout
            )
            Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.connectionInfo} | DATA: {rawData}", module="network")

            # Check If Packet ID is Valid
            header = rawData[0]
            if checkId and header != packet.ID:
                Logger.verbose(f"{self.handler.connectionInfo} | Packet Invalid!", module="network")
                raise ClientError(f"Invalid Packet {header}")

            # Deserialize Packet
            serializedData = await packet.deserialize(self.handler.player, rawData)
            return serializedData
        except asyncio.TimeoutError:
            raise ClientError(f"Did Not Receive Packet {packet.ID} In Time!")
        except Exception as e:
            if packet.CRITICAL or type(e) in CRITICAL_REQUEST_ERRORS or critical:
                raise e  # Pass Down Exception To Lower Layer
            packet.onError(e)
            raise e

    # Used in main listen loop; expect multiple types of packets!
    async def listenForPackets(
        self,
        packetDict: dict = {},
        headerSize: int = 1,
        ignoreUnknownPackets: bool = False,
        timeout: float = NET_TIMEOUT
    ):
        try:
            # Reading First Byte For Packet Header
            rawData = await asyncio.wait_for(
                self.handler.reader.readexactly(
                    headerSize  # Size of packet header
                ), timeout
            )
            Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.connectionInfo} | Incoming Player Loop Packet Id {rawData}", module="network")

            # Convert Packet Header to Int
            packetHeader = int.from_bytes(rawData, byteorder="big")

            # Check if packet is to be expected
            if packetHeader not in packetDict.keys():
                # Ignore if ignoreUnknownPackets flag is set
                if not ignoreUnknownPackets:
                    Logger.debug(f"Player Sent Unknown Packet Header {rawData} ({packetHeader})", module="network")
                    raise ClientError(f"Unknown Client Packet {packetHeader}")

            # Get packet using packetId
            packet = PacketManager.Request.getPacketById(packetHeader)

            # Reading and Appending Rest Of Packet Data (Packet Body)
            rawData += await asyncio.wait_for(
                self.handler.reader.readexactly(
                    packet.SIZE - headerSize  # Size of packet body (packet minus header size)
                ), timeout
            )
            Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.connectionInfo} | DATA: {rawData}", module="network")

            # Check if packet is being listened to
            if type(packet) in self._listeners:
                Logger.verbose(f"Checking Listeners For Packet {packet.NAME}", module="network")
                # Keep track on whether packet should continue to be processed after being handled
                continueProcessing = True
                # Get all the listeners
                listeners = self._listeners.get(type(packet), [])
                # Check if there are listeners in the queue
                if len(listeners) > 0:
                    # Create a hacky "check failed" list to store unmatched listeners to be put back into the dict
                    checkFailed = []
                    for future, check, shouldContinue in listeners:
                        Logger.verbose(f"({packet.NAME}) Checking Listener {check}", module="network")
                        # If future is cancelled, remove listener
                        if future.cancelled():
                            Logger.verbose(f"({check}) Listener Cancelled", module="network")
                            continue

                        # Check if check function returns true
                        try:
                            checkResult = check(self.handler.player, rawData)
                        except Exception as e:
                            Logger.verbose(f"({check}) Listener Error", module="network")
                            Logger.error("Error occurred while processing listener check function", module="network", printTb=False)
                            future.set_exception(e)
                            continue
                        else:
                            if checkResult:
                                future.set_result(rawData)
                                # As soon as one check sets continueProcessing to false, we should stop processing the packet
                                if continueProcessing and not shouldContinue:
                                    continueProcessing = False
                                continue

                        # This check did not pass. Add to checkFailed list
                        if not future.done():
                            Logger.verbose(f"({check}) Listener Condition Failed", module="network")
                            checkFailed.append((future, check, shouldContinue))

                    # Set the listeners list to the new list of failed listeners
                    self._listeners[type(packet)] = checkFailed

                    # If packet should not continue to be processed, return
                    if not continueProcessing:
                        Logger.verbose("Packet Processing Skipped", module="network")
                        return packetHeader, None

            # Attempting to Deserialize Packets
            try:
                # Deserialize Packet
                serializedData = await packet.deserialize(self.handler.player, rawData)
                return packetHeader, serializedData

            except Exception as e:
                if packet.CRITICAL or type(e) in CRITICAL_REQUEST_ERRORS:
                    raise e  # Pass Down Exception To Lower Layer
                return packetHeader, packet.onError(e)

        except asyncio.TimeoutError:
            # Some clients don't send info when not moving
            # Send Ping Packet (Make sure client is still connected)
            Logger.debug(f"{self.handler.connectionInfo} | Sending Connection Ping", module="network")
            await self.handler.dispatcher.sendPacket(Packets.Response.Ping)
            # raise ClientError("Did Not Receive Packet In Time!")
        except Exception as e:
            raise e  # Pass Down Exception To Lower Layer

    async def sendPacket(
        self,
        packet: Type[AbstractResponsePacket],
        *args,
        timeout: float = NET_TIMEOUT,
        **kwargs
    ):
        try:
            # Generate Packet
            rawData = await packet.serialize(*args, **kwargs)

            # Send Packet
            Logger.verbose(f"SERVER -> CLIENT | CLIENT: {self.handler.connectionInfo} | ID: {packet.ID} {packet.NAME} | SIZE: {packet.SIZE} | DATA: {rawData}", module="network")
            if self.handler.isConnected:
                self.handler.writer.write(bytes(rawData))
                await self.handler.writer.drain()
            else:
                Logger.debug(f"Packet {packet.NAME} Skipped Due To Closed Connection!", module="network")
        except Exception as e:
            # Making Sure These Errors Always Gets Raised (Ignore onError)
            if packet.CRITICAL or type(e) in CRITICAL_RESPONSE_ERRORS:
                raise e  # Pass Down Exception To Lower Layer
            return packet.onError(e)

    # Create Dispatch Listener to capture incoming packets
    def waitFor(
        self,
        packet: AbstractRequestPacket,
        *,
        check: Callable[..., bool] = lambda *args, **kwargs: True,
        timeout: Optional[float] = 600.0,  # Default 10 minute timeout
        shouldContinue: bool = False
    ):
        Logger.debug(f"Creating New Listener For Packet {type(packet)}", module="network")
        # Create Future Event
        future = asyncio.get_event_loop().create_future()

        # Add Future Event to Listeners
        self._listeners.setdefault(type(packet), []).append((future, check, shouldContinue))

        # Return Future
        return asyncio.wait_for(future, timeout)
