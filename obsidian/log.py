from __future__ import annotations

import time
import traceback
import sys

from obsidian.constants import Colour


class Logger:
    DEBUG = False
    VERBOSE = False

    @staticmethod
    def _getTimestamp():
        return time.strftime("%H:%M:%S", time.localtime())

    @classmethod
    def log(cls, message, tags=[], colour=Colour.NONE, textColour=Colour.NONE):
        # Generating Message (Add Tags, Message, Format, Etc)
        output = ""
        # Adding Tags
        for tag in tags:
            output = f"{output}[{colour}{tag.upper()}{Colour.RESET}{Colour.BACK_RESET}]"
        # Add Message
        if len(tags) != 0:
            output = f"{output}: {textColour}{message}{Colour.BACK_RESET}"
        else:
            output = f"{textColour}{message}{Colour.BACK_RESET}]{message}"
        # Print Final String
        print(output)

    @classmethod
    def info(cls, message, module="obsidian"):
        cls.log(
            str(message),
            tags=[cls._getTimestamp(), "log", module],
            colour=Colour.GREEN,
            textColour=Colour.WHITE
        )

    @classmethod
    def warn(cls, message, module="obsidian", askConfirmation=False):
        cls.log(
            str(message),
            tags=[cls._getTimestamp(), "warn", module],
            colour=Colour.YELLOW,
            textColour=Colour.WHITE
        )

    @classmethod
    def error(cls, message, module="obsidian", printTb=True, askConfirmation=False):
        if cls.DEBUG and printTb:
            traceback.print_exc()
        cls.log(
            str(message) + (" | Enable Debug For More Information" if not cls.DEBUG and printTb else ""),
            tags=[cls._getTimestamp(), "error", module],
            colour=Colour.RED,
            textColour=Colour.WHITE
        )
        if askConfirmation:
            while True:
                print()
                # Give user Warning, and ask them for further input
                cls.warn("Do you want to continue? y/n", module="error")
                userInput = input()
                if userInput.lower() == "y" or userInput.lower() == "yes":
                    break
                elif userInput.lower() == "n" or userInput.lower() == "no":
                    cls.warn("Ok Exiting...", module="error")
                    sys.exit()

    @classmethod
    def fatal(cls, message, module="obsidian", printTb=True, askConfirmation=False):
        if cls.DEBUG and printTb:
            traceback.print_exc()
        cls.log(
            str(message) + (" | Enable Debug For More Information" if not cls.DEBUG and printTb else ""),
            tags=[cls._getTimestamp(), "fatal", module],
            colour=Colour.BLACK + Colour.BACK_RED,
            textColour=Colour.WHITE
        )

    @classmethod
    def debug(cls, message, module="obsidian"):
        if cls.DEBUG:
            cls.log(
                str(message),
                tags=[cls._getTimestamp(), "debug", module],
                colour=Colour.CYAN,
                textColour=Colour.WHITE
            )

    @classmethod
    def verbose(cls, message, module="obsidian"):
        if cls.DEBUG and cls.VERBOSE:
            cls.log(
                str(message),
                tags=[cls._getTimestamp(), "obsidian", module],
                colour=Colour.MAGENTA,
                textColour=Colour.WHITE
            )
