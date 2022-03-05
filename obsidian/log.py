from __future__ import annotations

from pathlib import Path
import time
import traceback
import datetime
import sys

from typing import Optional
from obsidian.constants import Colour, SERVERPATH


class Logger:
    DEBUG = False
    VERBOSE = False
    SERVERMODE = False
    LOGFILE = None
    # These might be somewhat dangerous if the server crashes and stuff isnt logged.
    # Either way, its an option for servers with slower RWs.
    BUFFER_SIZE = 1
    MESSAGES_LOGGED = 0

    @staticmethod
    def _getTimestamp():
        return time.strftime("%H:%M:%S", time.localtime())

    @classmethod
    def setBufferSize(cls, size: int):
        cls.BUFFER_SIZE = size

    @classmethod
    def setupLogFile(cls, logPath: Optional[Path] = None):
        # Setup LogPath If Not Defined
        if logPath is None:
            logPath = Path(SERVERPATH, "logs")
        # Ensure File Exists
        logPath.mkdir(parents=True, exist_ok=True)
        # Open File
        logPath = Path(logPath, f"{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log")
        cls.LOGFILE = open(logPath, "a")

    @classmethod
    def _log(cls, message: str, tags: tuple[str, ...] = tuple(), colour: str = Colour.NONE, textColour: str = Colour.NONE):
        cls.MESSAGES_LOGGED += 1
        # Generating Message (Add Tags, Message, Format, Etc)
        output = ""
        # Adding Tags
        for tag in tags:
            output += f"[{colour}{tag.upper()}{Colour.RESET}{Colour.BACK_RESET}]"
        # Add Message
        if len(tags) != 0:
            output += f": {textColour}{message}{Colour.BACK_RESET}"
        else:
            output += f"{textColour}{message}{Colour.BACK_RESET}"
        # Log String Into LogFile (If Fail Skip)
        if cls.LOGFILE is not None:
            try:
                # Write Tags
                for tag in tags:
                    cls.LOGFILE.write(f"[{tag.upper()}]")
                # Write Message
                if len(tags) != 0:
                    cls.LOGFILE.write(f": {message}\n")
                else:
                    cls.LOGFILE.write(f"{message}\n")
                # Save File If Buffer Is Reached
                if cls.MESSAGES_LOGGED % cls.BUFFER_SIZE == 0:
                    cls.LOGFILE.flush()
            except Exception as e:
                print(f"Error While Handing Log Message - {type(e).__name__}: {e}")
        # Print Final String
        print(output)

    @classmethod
    def askConfirmation(cls, message: str = "Do you want to continue?", exit_on_no: bool = True):
        if not cls.SERVERMODE:
            while True:
                # Give user Warning, and ask them for further input
                cls.warn(f"{message} (y/n)", module="confirmation")
                userInput = input()
                if userInput.lower() == "y" or userInput.lower() == "yes":
                    cls._log("")
                    return True
                elif userInput.lower() == "n" or userInput.lower() == "no":
                    if exit_on_no:
                        cls.warn("Ok Exiting...", module="confirmation")
                        sys.exit()
                    return False
        else:
            cls.warn(f"{message} [SKIPPING (servermode enabled)]", module="confirmation")
            if exit_on_no:
                cls.warn("Stopping Server due to Unsafe Status", module="confirmation")
                sys.exit()
            return False

    @classmethod
    def info(cls, message: str, module: str = "unknown"):
        cls._log(
            str(message),
            tags=(cls._getTimestamp(), "log", module),
            colour=Colour.GREEN,
            textColour=Colour.WHITE
        )

    @classmethod
    def warn(cls, message: str, module: str = "unknown"):
        cls._log(
            str(message),
            tags=(cls._getTimestamp(), "warn", module),
            colour=Colour.YELLOW,
            textColour=Colour.WHITE
        )

    @classmethod
    def error(cls, message: str, module: str = "unknown", printTb: bool = True):
        if cls.DEBUG and printTb:
            cls._log(f"{traceback.format_exc()}")
        cls._log(
            str(message) + (" | Enable Debug For More Information" if not cls.DEBUG and printTb else ""),
            tags=(cls._getTimestamp(), "error", module),
            colour=Colour.RED,
            textColour=Colour.WHITE
        )

    @classmethod
    def fatal(cls, message: str, module: str = "unknown", printTb: bool = True):
        if cls.DEBUG and printTb:
            cls._log(f"{traceback.format_exc()}")
        cls._log(
            str(message) + (" | Enable Debug For More Information" if not cls.DEBUG and printTb else ""),
            tags=(cls._getTimestamp(), "fatal", module),
            colour=Colour.BLACK + Colour.BACK_RED,
            textColour=Colour.WHITE
        )

    @classmethod
    def debug(cls, message: str, module: str = "unknown"):
        if cls.DEBUG:
            cls._log(
                str(message),
                tags=(cls._getTimestamp(), "debug", module),
                colour=Colour.CYAN,
                textColour=Colour.WHITE
            )

    @classmethod
    def verbose(cls, message: str, module: str = "unknown"):
        if cls.DEBUG and cls.VERBOSE:
            cls._log(
                str(message),
                tags=(cls._getTimestamp(), "verbose", module),
                colour=Colour.MAGENTA,
                textColour=Colour.WHITE
            )
