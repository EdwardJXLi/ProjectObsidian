"""
Copyright (C) TODO
"""

import sys
import argparse
import asyncio

from obsidian.core import *
#from obsidian import server

async def main():
    #Initiate Argument Parser
    parser = argparse.ArgumentParser(description="TODO")
    #parser.add_argument('--TEMPLATE', type=int, nargs='?', help='TEMPLATE', default=TEMPLATE)
    parser.add_argument('-a', '--address', type=str, nargs='?', help='The address the Minecraft server would bind to.', default='localhost')
    parser.add_argument('-p', '--port', type=int, nargs='?', help='The port the Minecraft server would bind to.', default=25565)
    args = parser.parse_args()

    #Init Server
    server = Server(args.address, args.port, colour=True)
    server.setup()
    server.start()

if __name__ == '__main__':
    asyncio.run(main())
