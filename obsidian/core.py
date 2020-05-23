import asyncio
import threading

from obsidian.constants import *
from obsidian.log import *
from obsidian.client import *

class Server(object):
    def __init__(self, address, port, colour=True):
        self.address = address
        self.port = port
        #Init Colour
        if(colour):
            Colour.init()

    async def init(self):
        Logger.info(f"Setting Up Server", module="init")
        self.server = await asyncio.start_server(self._get_conn_handler(), self.address, self.port)
        Logger.info(f"Server Starting On {self.address} Port {self.port}")
   
    async def run(self):       
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