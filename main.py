"""
Copyright (C) RadioactiveHydra (Edward)
"""

# import sys
import argparse
import asyncio
# import time

from obsidian.server import Server
from obsidian.log import Logger


async def main():
    # Initiate Argument Parser
    parser = argparse.ArgumentParser(description="TODO")
    # parser.add_argument('--TEMPLATE', type=int, nargs='?', help='TEMPLATE', default=TEMPLATE)
    parser.add_argument('-a', "--address", type=str, nargs='?', help="The Address The Minecraft Server Would Bind To.", default="localhost")
    parser.add_argument('-p', "--port", type=int, nargs='?', help="The Port The Minecraft Server Would Bind To.", default=25565)
    parser.add_argument('-n', "--name", type=str, nargs='?', help="The Name Of The Minecraft Server", default="Minecraft Server")
    parser.add_argument('-m', "--motd", type=str, nargs='?', help="The MOTD Of The Minecraft Server", default="Python Server Implementation")
    parser.add_argument('-d', "--debug", help="Enable Debug Logging", action="store_true")
    parser.add_argument('-v', "--verbose", help="Increase Debug output verbosity", action="store_true")
    args = parser.parse_args()

    # Set Logging Levels
    Logger.DEBUG = args.debug
    Logger.VERBOSE = args.verbose

    # Create and Init Main Server
    server = Server(args.address, args.port, args.name, args.motd, colour=True, moduleBlacklist=["errortest", "errortest2", "errortest3"])
    await server.init()
    asyncio.create_task(server.run())

    # Busy Operation To Keep Main Thread Alive
    while True:
        await asyncio.sleep(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        Logger.fatal(f"Unhandled Server Exception - {type(e).__name__}: {e}", "main", printTb=False)
