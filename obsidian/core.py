import asyncio
import threading

from obsidian.constants import *
from obsidian.log import *
from obsidian.network import *

class Server(object):
    def __init__(self, address, port, name, motd, colour=True):
        self.address = address
        self.port = port
        self.name = name
        self.motd = motd
        #Init Colour
        if(colour):
            Colour.init()

    async def init(self):
        #Create Asyncio Socket Server
        Logger.info(f"Setting Up Server {self.name}", module="init")
        self.server = await asyncio.start_server(self._get_conn_handler(), self.address, self.port)
   
    async def run(self):
        #Start Server
        Logger.info(f"Starting Server {self.name} On {self.address} Port {self.port}")
        async with self.server as s:
            await s.serve_forever()
    
    def _get_conn_handler(self):
        async def handler(reader, writer):
            while True:
                data = await reader.readuntil(b'\n')
                message = data.decode()
                addr = writer.get_extra_info('peername')

                print(f"Received {message!r} from {addr!r}")

                print(f"Send: {message!r}")
                writer.write(data)
                await writer.drain()

        return handler