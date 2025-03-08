"""
Copyright (C) RadioactiveHydra (Edward) 2023
"""

import argparse
import asyncio
import signal
import sys
import traceback

from obsidian.server import Server
from obsidian.log import Logger

# Check python version to see if compatible
if sys.version_info.major < 3 or sys.version_info.minor < 10:
    raise RuntimeError("Python Version Out Of Date! Minimum Required: 3.10.0")


async def main():
    # Initiate Argument Parser
    parser = argparse.ArgumentParser(
        description="Project Obsidian - Open Source Minecraft Classic Server Reverse Engineer And Reimplementation Project"
    )
    # parser.add_argument('-x', "--TEMPLATE", type=int, nargs='?', help="TEMPLATE", default=TEMPLATE)
    parser.add_argument('-a', "--address", type=str, nargs='?', help="The Address The Minecraft Server Would Bind To.", default="0.0.0.0")
    parser.add_argument('-p', "--port", type=int, nargs='?', help="The Port The Minecraft Server Would Bind To.", default=25565)
    parser.add_argument('-n', "--name", type=str, nargs='?', help="The Name Of The Minecraft Server", default="Minecraft Server")
    parser.add_argument('-m', "--motd", type=str, nargs='?', help="The MOTD Of The Minecraft Server", default="Python Server Implementation")
    parser.add_argument('-d', "--debug", help="Enable Debug Logging", action="store_true")
    parser.add_argument('-v', "--verbose", help="Increase Debug Output Verbosity", action="store_true")
    parser.add_argument('-q', "--quiet", help="Disabled Logging To File", action="store_true")
    parser.add_argument('-s', "--server", help="Auto-Denys Confirmation Dialogs", action="store_true")
    parser.add_argument('-nc', "--no-color", help="Disable Color While Logging", action="store_true")
    args = parser.parse_args()

    # Set Logging Levels
    Logger.DEBUG = args.debug
    Logger.VERBOSE = args.verbose
    Logger.SERVER_MODE = args.server
    Logger.COLOR = not args.no_color

    # Set Up Logging File
    if not args.quiet:
        Logger.setupLogFile()

    # Create and Init Main Server
    server = Server(args.address, args.port, args.name, args.motd, color=True)
    await server.init()
    asyncio.create_task(server.run())

    # Capture and Handle Crl-C
    signal.signal(
        signal.SIGINT,
        server.asyncStop  # Use this function to run async stop from outside async
    )

    # Capture SIGTERM and handle it
    if hasattr(signal, "SIGTERM"):
        signal.signal(
            signal.SIGTERM,
            server.asyncStop  # Use this function to run async stop from outside async
        )

    # Capture SIGQUIT and handle it
    if hasattr(signal, "SIGQUIT"):
        signal.signal(
            signal.SIGQUIT,
            server.asyncStop  # Use this function to run async stop from outside async
        )

    # Busy Operation To Keep Main Thread Alive
    # In the future, this would be dominated by a console thread
    while True:
        await asyncio.sleep(1)


# Make sure main gets asynced when run
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        Logger.fatal(f"Unhandled Server Exception - {type(e).__name__}: {e}", module="main", printTb=False)
        traceback.print_exc()
