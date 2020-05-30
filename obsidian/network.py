import asyncio

from obsidian.packet import *

class NetworkHandler:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.dispacher = NetworkDispacher(self)
        self.player = None

    async def initConnection(self):
        #Start the server <-> client login protocol
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
        temp = await self.dispacher.getPacket(TestPacket)
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
        self.hander = handler

    #NOTE: or call dispachPacket
    async def getPacket(self, packet, timeout=NET_TIMEOUT, checkId=True):
        #Get Packet Data
        rawData = await asyncio.wait_for(
            self.hander.reader.readexactly(
                packet.SIZE
            ), timeout)
        #Check If Packet ID is Valid
        if(checkId and rawData[0] != packet.ID):
            raise InvalidPacketError
        #Desterilize Packet
        packet.deserialize(rawData)
        packet.postDesterilization()
        return None

    #NOTE: or call receivePacket
    async def sendPacket(self, packet, *args, timeout=NET_TIMEOUT, **kwargs):
        #Generate Packet
        rawData = packet.sterilize(*args, **kwargs)
        #Run Post Ster
        packet.postSterilization()
        #Send Packet
        self.hander.writer.write(rawData)
        await self.hander.writer.drain()


#Custom Errors
class InvalidPacketError(Exception):
    pass