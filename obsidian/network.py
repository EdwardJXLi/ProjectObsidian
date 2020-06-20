import asyncio
from typing import Type

from obsidian.log import Logger
from obsidian.packet import (
    Packets,
    AbstractRequestPacket,
    AbstractResponsePacket
)
from obsidian.constants import (
    NET_TIMEOUT,
    ClientError,
    InvalidPacketError
)


class NetworkHandler:
    def __init__(self, server, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.ip: tuple = self.reader._transport.get_extra_info("peername")  # type: ignore
        self.dispacher = NetworkDispacher(self)
        # self.player = None

    async def initConnection(self):
        # Log Connection
        Logger.info(f"New Connection From {self.ip}", module="network")

        # Start the server <-> client login protocol
        Logger.debug(f"{self.ip} | Starting Client <-> Server Handshake")
        await self._handleInitialHandshake()

        '''
        except asyncio.TimeoutError as te:
            pass
        except asyncio.IncompleteReadError as ire:
            pass
        except InvalidPacketError as ipe:
            pass
        except Exception as e:
            pass
        '''

        # finally:
        #     pass

        '''
        data = await reader.readuntil(b'\n')
        message = data.decode()
        addr = writer.get_extra_info('peername')
        print(f"Received {message!r} from {addr!r}")
        print(f"Send: {message!r}")
        writer.write(data)
        await writer.drain()
        '''

    async def _handleInitialHandshake(self):
        # Wait For Player Identification Packet
        Logger.debug(f"{self.ip} | Waiting For Initial Player Information Packet")
        protocolVersion, username, verificationKey = await self.dispacher.readPacket(Packets.Request.PlayerIdentification)

        # Checking Client Protocol Version
        if protocolVersion > self.server.protocolVersion:
            raise ClientError("Server Outdated")
        elif protocolVersion < self.server.protocolVersion:
            raise ClientError("Client Outdated")

        # Send Server Information Packet
        Logger.debug(f"{self.ip} | Sending Initial Server Information Packet")
        await self.dispacher.sendPacket(Packets.Response.ServerIdentification, self.server.protocolVersion, self.server.name, self.server.motd, 0x00)

        # Send Level Initialize Packet
        Logger.debug(f"{self.ip} | Sending Level Initialize Packet")
        await self.dispacher.sendPacket(Packets.Response.LevelInitialize)

    '''
    async def handleConnection(self):
        while True:
            data = await reader.readuntil(b'\n')
            message = data.decode()
            addr = writer.get_extra_info('peername')

            print(f"Received {message!r} from {addr!r}")

            print(f"Send: {message!r}")
            writer.write(data)
            await writer.drain()
    '''


class NetworkDispacher:
    def __init__(self, handler: NetworkHandler):
        self.player = None
        self.handler = handler
        self.request = []  # Array of Request Packets
        self.response = []  # Array of Request Packets

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
        # Get Packet Data
        Logger.verbose(f"Expected Packet {packet.ID} Size {packet.SIZE} from {self.handler.ip}")
        rawData = await asyncio.wait_for(
            self.handler.reader.readexactly(
                packet.SIZE
            ), timeout)
        Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.ip} | DATA: {rawData}")

        # Check If Packet ID is Valid
        if checkId and rawData[0] != packet.ID:
            Logger.verbose(f"{self.handler.ip} | Packet Invalid!")
            raise InvalidPacketError("Packet Invalid")

        # Deserialize Packet
        # TODO: Fix type complaint!
        serializedData = packet.deserialize(rawData)  # type: ignore
        return serializedData

    async def sendPacket(
        self,
        packet: Type[AbstractResponsePacket],
        *args,
        timeout=NET_TIMEOUT,
        **kwargs
    ):
        # Generate Packet
        rawData = packet.serialize(*args, **kwargs)

        # Send Packet
        Logger.verbose(f"SERVER -> CLIENT | CLIENT: {self.handler.ip} | ID: {packet.ID} | SIZE: {packet.SIZE} | DATA: {rawData}")
        self.handler.writer.write(rawData)
        await self.handler.writer.drain()

    # Initialize Regerster Packer Handler
    def registerInit(self, module: str):
        pass  # Unused for now
