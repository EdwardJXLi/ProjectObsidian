import asyncio

import obsidian.packet as corepacket
from obsidian.packet import PacketDirections
from obsidian.log import Logger
from obsidian.constants import NET_TIMEOUT, InvalidPacketError, InitError


class NetworkHandler:
    def __init__(self, server, reader, writer):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.ip = self.reader._transport.get_extra_info("peername")
        self.dispacher = NetworkDispacher(self)
        self.player = None

        # Adding Core Packets To Network Dispacher
        Logger.info("Adding Core Packets", module="network")
        corepacket.registerCoreModules(self.dispacher)

    async def initConnection(self):
        # Log Connection
        Logger.info(f"New Connection From {self.ip}", module="network")

        # Start the server <-> client login protocol
        Logger.debug(f"{self.ip} | Starting Client <-> Server Handshake")
        await self.handleInitialHandshake()

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

    async def handleInitialHandshake(self):
        # Wait For Player Identification Packet
        Logger.debug(f"{self.ip} | Waiting For Initial Player Information Packet")
        await self.dispacher.readPacket(corepacket.TestPacket)

        # Send Server Information Packet
        Logger.debug(f"{self.ip} | Sending Initial Server Information Packet")
        await self.dispacher.sendPacket(corepacket.TestReturnPacket)

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
    def __init__(self, handler):
        self.player = None
        self.handler = handler
        self.request = []  # Array of Request Packets
        self.response = []  # Array of Request Packets

    # Used in main listen loop; expect multiple types of packets!
    async def listenForPacket(self, timeout=NET_TIMEOUT):
        pass

    # NOTE: or call receivePacket
    # Used when exact packet is expected
    async def readPacket(self, packet: corepacket.Packet, timeout=NET_TIMEOUT, checkId=True):
        # Get Packet Data
        Logger.verbose(f"Expected Packet {packet.ID} Size {packet.SIZE} from {self.handler.ip}")
        rawData = await asyncio.wait_for(
            self.handler.reader.readexactly(
                packet.SIZE
            ), timeout)
        Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.ip} | DATA: {rawData}")

        # Check If Packet ID is Valid
        if checkId and rawData[0] != packet.ID:
            Logger.verbose(f"{self.ip} | Packet Invalid!")
            raise InvalidPacketError("Packet Invalid")

        # Deserialize Packet
        serializedData = packet.deserialize(rawData)
        packet.postDeserialization()
        return serializedData

    async def sendPacket(self, packet, *args, timeout=NET_TIMEOUT, **kwargs):
        # Generate Packet
        rawData = packet.serialize(*args, **kwargs)
        packet.postSterilization()

        # Send Packet
        Logger.verbose(f"SERVER -> CLIENT | CLIENT: {self.handler.ip} | ID: {packet.ID} | SIZE: {packet.SIZE} | DATA: {rawData}")
        self.handler.writer.write(rawData)
        await self.handler.writer.drain()

    # Initialize Regerster Packer Handler
    def registerInit(self, module):
        pass  # Unused for now

    # Regerster Packer Handler; Adds Network Protocols To Dispacher
    def registerPacket(self, packet):
        # Check Packet Type
        if packet.DIRECTION == PacketDirections.REQUEST:
            # Append Packet To Request Packets
            self.request.append(packet)
            Logger.debug(f"Registered Request Packet {packet.__name__} (ID: {packet.ID}) From Module {packet.MODULE}", module=packet.MODULE + "-network")

        elif packet.DIRECTION == PacketDirections.RESPONSE:
            # Append Packet To Request Packets
            self.response.append(packet)
            Logger.debug(f"Registered Response Packet {packet.__name__} (ID: {packet.ID}) From Module {packet.MODULE}", module=packet.MODULE + "-network")

        else:
            # Packet Direction Is Unknown
            raise InitError(f"Unknown Packet Direction {packet.DIRECTION} for Packet {packet.__name__} (ID: {packet.ID}) From Module {packet.MODULE}!")
