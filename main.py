"""
Copyright (C) RadioactiveHydra (Edward) 2020
"""

# import sys
import argparse
import asyncio
import signal
import os
import datetime

from obsidian.server import Server
from obsidian.log import Logger


async def main():
    # Initiate Argument Parser
    parser = argparse.ArgumentParser(description="Project Obsidian - Open Source Minecraft Classic Server Reverse Engineer And Reimplementation Project")
    # parser.add_argument('--TEMPLATE', type=int, nargs='?', help='TEMPLATE', default=TEMPLATE)
    parser.add_argument('-a', "--address", type=str, nargs='?', help="The Address The Minecraft Server Would Bind To.", default="0.0.0.0")
    parser.add_argument('-p', "--port", type=int, nargs='?', help="The Port The Minecraft Server Would Bind To.", default=25565)
    parser.add_argument('-n', "--name", type=str, nargs='?', help="The Name Of The Minecraft Server", default="Minecraft Server")
    parser.add_argument('-m', "--motd", type=str, nargs='?', help="The MOTD Of The Minecraft Server", default="Python Server Implementation")
    parser.add_argument('-d', "--debug", help="Enable Debug Logging", action="store_true")
    parser.add_argument('-v', "--verbose", help="Increase Debug Output Verbosity", action="store_true")
    parser.add_argument('-q', "--quiet", help="Disabled Logging To File", action="store_true")
    args = parser.parse_args()

    # Set Logging Levels
    Logger.DEBUG = args.debug
    Logger.VERBOSE = args.verbose

    # Set Up Logging File
    if not args.quiet:
        Logger.setupLogFile()

    # Create and Init Main Server
    server = Server(args.address, args.port, args.name, args.motd, colour=True)
    await server.init()
    asyncio.create_task(server.run())

    # Capture and Handle Crl-C
    signal.signal(
        signal.SIGINT,
        server.asyncstop  # Use this function to run async stop from outside async
    )

    # Busy Operation To Keep Main Thread Alive
    while True:
        await asyncio.sleep(1)


# Make sure main gets asynced when run
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        Logger.fatal(f"Unhandled Server Exception - {type(e).__name__}: {e}", module="main", printTb=False)
