import asyncio

from obsidian.packet import *
from obsidian.log import *

class NetworkHandler:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.ip = self.reader._transport.get_extra_info("peername")
        self.dispacher = NetworkDispacher(self)
        self.player = None

    async def initConnection(self):
        #Log Connection
        Logger.info(f"New Connection From {self.ip}", module="Network")
        #Start the server <-> client login protocol
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

        #finally:
        #    pass

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
        #Wait For Player Identification Packet
        Logger.debug(f"{self.ip} | Waiting For Initial Player Information Packet")
        temp = await self.dispacher.getPacket(TestPacket)
        #Send Server Information Packet
        Logger.debug(f"{self.ip} | Sending Initial Server Information Packet")
        await self.dispacher.sendPacket(TestReturnPacket)

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
        self.handler = handler

    #Used in main listen loop; expect multiple types of packets!
    async def listenForPacket(self, timeout=NET_TIMEOUT):
        pass

    #NOTE: or call receivePacket
    #Used when exact packet is expected
    async def getPacket(self, packet, timeout=NET_TIMEOUT, checkId=True):
        #Get Packet Data
        Logger.verbose(f"Expected Packet {packet.ID} Size {packet.SIZE} from {self.handler.ip}")
        rawData = await asyncio.wait_for(
            self.handler.reader.readexactly(
                packet.SIZE
            ), timeout)
        Logger.verbose(f"CLIENT -> SERVER | CLIENT: {self.handler.ip} | DATA: {rawData}")
        #Check If Packet ID is Valid
        if(checkId and rawData[0] != packet.ID):
            Logger.verbose(f"{self.ip} | Packet Invalid!")
            raise InvalidPacketError
        #Desterilize Packet
        packet.deserialize(rawData)
        packet.postDesterilization()
        return None

    #NOTE: or call dispachPacket
    async def sendPacket(self, packet, *args, timeout=NET_TIMEOUT, **kwargs):
        #Generate Packet
        rawData = packet.sterilize(*args, **kwargs)
        #Run Post Ster
        packet.postSterilization()
        #Send Packet
        Logger.verbose(f"SERVER -> CLIENT | CLIENT: {self.handler.ip} | ID: {packet.ID} | SIZE: {packet.SIZE} | DATA: {rawData}")
        self.handler.writer.write(rawData)
        await self.handler.writer.drain()


#Custom Errors
class InvalidPacketError(Exception):
    pass