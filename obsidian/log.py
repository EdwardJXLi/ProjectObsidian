import time
import traceback

from obsidian.constants import Colour


class Logger:
    DEBUG = False
    VERBOSE = False

    @staticmethod
    def _getTimestamp():
        return time.strftime("%H:%M:%S", time.localtime())

    @classmethod
    def log(cls, message, level=None, module=None, colour=Colour.NONE, textColour=Colour.NONE):
        if level is not None:
            # Generate Strings
            timestampStr = f"{colour}{cls._getTimestamp()}{Colour.RESET}{Colour.BACK_RESET}"
            levelStr = f"{colour}{level.upper()}{Colour.RESET}{Colour.BACK_RESET}"
            moduleStr = f"{colour}{module.upper()}{Colour.RESET}{Colour.BACK_RESET}"
            msgString = f"{textColour}{message}{Colour.RESET}{Colour.BACK_RESET}"
            # Concatenate String
            print(f"[{timestampStr}][{levelStr}][{moduleStr}]: {msgString}")
        else:
            print(message)

    @classmethod
    def info(cls, message, module="obsidian"):
        cls.log(
            str(message),
            level="log",
            module=module,
            colour=Colour.GREEN,
            textColour=Colour.WHITE
        )

    @classmethod
    def warn(cls, message, module="obsidian"):
        cls.log(
            str(message),
            level="warn",
            module=module,
            colour=Colour.YELLOW,
            textColour=Colour.WHITE
        )

    @classmethod
    def error(cls, message, module="obsidian", printTb=True):
        if cls.DEBUG and printTb:
            traceback.print_exc()
        cls.log(
            str(message) + (" | Enable Debug For More Information" if not cls.DEBUG and printTb else ""),
            level="log",
            module=module,
            colour=Colour.RED,
            textColour=Colour.WHITE
        )

    @classmethod
    def fatal(cls, message, module="obsidian", printTb=True):
        if cls.DEBUG and printTb:
            traceback.print_exc()
        cls.log(
            str(message) + (" | Enable Debug For More Information" if not cls.DEBUG and printTb else ""),
            level="FATAL",
            module=module,
            colour=Colour.BLACK + Colour.BACK_RED,
            textColour=Colour.WHITE
        )

    @classmethod
    def debug(cls, message, module="obsidian"):
        if cls.DEBUG:
            cls.log(
                str(message),
                level="debug",
                module=module,
                colour=Colour.CYAN,
                textColour=Colour.WHITE
            )

    @classmethod
    def verbose(cls, message, module="obsidian"):
        if cls.DEBUG and cls.VERBOSE:
            cls.log(
                str(message),
                level="verbose",
                module=module,
                colour=Colour.MAGENTA,
                textColour=Colour.WHITE
            )
