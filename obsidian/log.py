import time

from obsidian.constants import Colour


class Logger:
    DEBUG = False
    VERBOSE = False

    @staticmethod
    def getTimestamp():
        return time.strftime("%H:%M:%S", time.localtime())

    @classmethod
    def log(cls, message, level=None, module=None, colour=Colour.NONE, textColour=Colour.NONE):
        if level is not None:
            # Generate Strings
            timestampStr = f"{colour}{cls.getTimestamp()}{Colour.RESET}{Colour.BACK_RESET}"
            levelStr = f"{colour}{level.upper()}{Colour.RESET}{Colour.BACK_RESET}"
            moduleStr = f"{colour}{module.upper()}{Colour.RESET}{Colour.BACK_RESET}"
            msgString = f"{textColour}{message}{Colour.RESET}{Colour.BACK_RESET}"
            # Concatenate String
            print(f"[{timestampStr}][{levelStr}][{moduleStr}]: {msgString}")
        else:
            print(message)

    @classmethod
    def info(cls, message, module="obsidian"):
        cls.log(message, level="log", module=module, colour=Colour.GREEN, textColour=Colour.WHITE)

    @classmethod
    def warn(cls, message, module="obsidian"):
        cls.log(message, level="warn", module=module, colour=Colour.YELLOW, textColour=Colour.WHITE)

    @classmethod
    def error(cls, message, module="obsidian"):
        cls.log(message, level="log", module=module, colour=Colour.RED, textColour=Colour.WHITE)

    @classmethod
    def fatal(cls, message, module="obsidian"):
        cls.log(message, level="FATAL", module=module, colour=Colour.BLACK + Colour.BACK_RED, textColour=Colour.BLACK + Colour.BACK_RED)

    @classmethod
    def debug(cls, message, module="obsidian"):
        if cls.DEBUG:
            cls.log(message, level="debug", module=module, colour=Colour.CYAN, textColour=Colour.WHITE)

    @classmethod
    def verbose(cls, message, module="obsidian"):
        if cls.DEBUG and cls.VERBOSE:
            cls.log(message, level="verbose", module=module, colour=Colour.CYAN, textColour=Colour.WHITE)
