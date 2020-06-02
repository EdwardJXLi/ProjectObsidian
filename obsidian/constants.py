import os

# Server Version
__version__ = 'DEV-X.X.X'

# Networking Constants
NET_TIMEOUT = 15

# Console Colour
CSI = '\u001b['  # ANSI Colour Header


# Custom Errors
# Init Errors
class InitError(Exception):
    pass


# Network Errors
class InvalidPacketError(Exception):
    pass


class ClientError(Exception):
    pass


class Colour():
    BLACK = ""
    RED = ""
    GREEN = ""
    YELLOW = ""
    BLUE = ""
    MAGENTA = ""
    CYAN = ""
    WHITE = ""
    RESET = ""
    NONE = ""
    LIGHTBLACK_EX = ""
    LIGHTRED_EX = ""
    LIGHTGREEN_EX = ""
    LIGHTYELLOW_EX = ""
    LIGHTBLUE_EX = ""
    LIGHTMAGENTA_E = ""
    LIGHTCYAN_EX = ""
    LIGHTWHITE_EX = ""
    BACK_BLACK = ""
    BACK_RED = ""
    BACK_GREEN = ""
    BACK_YELLOW = ""
    BACK_BLUE = ""
    BACK_MAGENTA = ""
    BACK_CYAN = ""
    BACK_WHITE = ""
    BACK_RESET = ""
    BACK_NONE = ""
    BACK_LIGHTBLACK_EX = ""
    BACK_LIGHTRED_EX = ""
    BACK_LIGHTGREEN_EX = ""
    BACK_LIGHTYELLOW_EX = ""
    BACK_LIGHTBLUE_EX = ""
    BACK_LIGHTMAGENTA_E = ""
    BACK_LIGHTCYAN_EX = ""
    BACK_LIGHTWHITE_EX = ""

    @classmethod
    def init(cls):
        if os.name == "posix":
            # Foreground Standard
            cls.BLACK = f"{CSI}30m"
            cls.RED = f"{CSI}31m"
            cls.GREEN = f"{CSI}32m"
            cls.YELLOW = f"{CSI}33m"
            cls.BLUE = f"{CSI}34m"
            cls.MAGENTA = f"{CSI}35m"
            cls.CYAN = f"{CSI}36m"
            cls.WHITE = f"{CSI}37m"
            cls.RESET = f"{CSI}39m"
            # Foreground Semi-Supported
            cls.LIGHTBLACK_EX = f"{CSI}90m"
            cls.LIGHTRED_EX = f"{CSI}91m"
            cls.LIGHTGREEN_EX = f"{CSI}92m"
            cls.LIGHTYELLOW_EX = f"{CSI}93m"
            cls.LIGHTBLUE_EX = f"{CSI}94m"
            cls.LIGHTMAGENTA_E = f"{CSI}95m"
            cls.LIGHTCYAN_EX = f"{CSI}96m"
            cls.LIGHTWHITE_EX = f"{CSI}97m"

            # Background Standard
            cls.BACK_BLACK = f"{CSI}40m"
            cls.BACK_RED = f"{CSI}41m"
            cls.BACK_GREEN = f"{CSI}42m"
            cls.BACK_YELLOW = f"{CSI}43m"
            cls.BACK_BLUE = f"{CSI}44m"
            cls.BACK_MAGENTA = f"{CSI}45m"
            cls.BACK_CYAN = f"{CSI}46m"
            cls.BACK_WHITE = f"{CSI}47m"
            cls.BACK_RESET = f"{CSI}49m"
            # Background Semi-Supported
            cls.BACK_LIGHTBLACK_EX = f"{CSI}100m"
            cls.BACK_LIGHTRED_EX = f"{CSI}101m"
            cls.BACK_LIGHTGREEN_EX = f"{CSI}102m"
            cls.BACK_LIGHTYELLOW_EX = f"{CSI}103m"
            cls.BACK_LIGHTBLUE_EX = f"{CSI}104m"
            cls.BACK_LIGHTMAGENTA_E = f"{CSI}105m"
            cls.BACK_LIGHTCYAN_EX = f"{CSI}106m"
            cls.BACK_LIGHTWHITE_EX = f"{CSI}107m"

        else:
            print("!!! COLOUR PRINTING IS NOT SUPPORTED FOR YOUR SYSTEM !!!")
