"""
Copyright (C) TODO
"""

import sys
import argparse

import obsidian
from obsidian import *
#from obsidian import server

def main():
    #Initiate Argument Parser
    parser = argparse.ArgumentParser(description="TODO")
    #parser.add_argument('--TEMPLATE', type=int, nargs='?', help='TEMPLATE', default=TEMPLATE)
    parser.add_argument('-a', '--address', type=str, nargs='?', help='The address the Minecraft server would bind to.', default='localhost')
    parser.add_argument('-p', '--port', type=int, nargs='?', help='The port the Minecraft server would bind to.', default=25565)
    args = parser.parse_args()

    #Init Server
    server = MinecraftServer(args.address, args.port)
    server.start()

if __name__ == '__main__':
    main()
    sys.exit()