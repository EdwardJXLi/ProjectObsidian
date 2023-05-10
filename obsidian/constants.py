from __future__ import annotations

import os
import asyncio

# Server Version
__version__ = "1.0.0"

# Server Location
SERVER_PATH = os.path.dirname(os.path.abspath(__file__))

# Networking Constants
NET_TIMEOUT = 5
CRITICAL_REQUEST_ERRORS = [
    # These errors will bypass the packet.onError() handler and get forced raised
]
CRITICAL_RESPONSE_ERRORS = [
    # These errors will bypass the packet.onError() handler and get forced raised
    BrokenPipeError,
    ConnectionResetError,
    asyncio.IncompleteReadError
]

# Message Constants
MAX_MESSAGE_LENGTH = 64

# Console Colour
CSI = "\u001b["  # ANSI Colour Header

# Module Constants
MODULES_FOLDER = "modules"
MODULES_IMPORT = "obsidian.modules."

# Managers
# Dynamically generated list of registered managers.
MANAGERS_LIST = []


# Colour handler
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
    LIGHT_BLACK_EX = ""
    LIGHT_RED_EX = ""
    LIGHT_GREEN_EX = ""
    LIGHT_YELLOW_EX = ""
    LIGHT_BLUE_EX = ""
    LIGHT_MAGENTA_E = ""
    LIGHT_CYAN_EX = ""
    LIGHT_WHITE_EX = ""
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
    BACK_LIGHT_BLACK_EX = ""
    BACK_LIGHT_RED_EX = ""
    BACK_LIGHT_GREEN_EX = ""
    BACK_LIGHT_YELLOW_EX = ""
    BACK_LIGHT_BLUE_EX = ""
    BACK_LIGHT_MAGENTA_E = ""
    BACK_LIGHT_CYAN_EX = ""
    BACK_LIGHT_WHITE_EX = ""

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
            cls.LIGHT_BLACK_EX = f"{CSI}90m"
            cls.LIGHT_RED_EX = f"{CSI}91m"
            cls.LIGHT_GREEN_EX = f"{CSI}92m"
            cls.LIGHT_YELLOW_EX = f"{CSI}93m"
            cls.LIGHT_BLUE_EX = f"{CSI}94m"
            cls.LIGHT_MAGENTA_E = f"{CSI}95m"
            cls.LIGHT_CYAN_EX = f"{CSI}96m"
            cls.LIGHT_WHITE_EX = f"{CSI}97m"

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
            cls.BACK_LIGHT_BLACK_EX = f"{CSI}100m"
            cls.BACK_LIGHT_RED_EX = f"{CSI}101m"
            cls.BACK_LIGHT_GREEN_EX = f"{CSI}102m"
            cls.BACK_LIGHT_YELLOW_EX = f"{CSI}103m"
            cls.BACK_LIGHT_BLUE_EX = f"{CSI}104m"
            cls.BACK_LIGHT_MAGENTA_E = f"{CSI}105m"
            cls.BACK_LIGHT_CYAN_EX = f"{CSI}106m"
            cls.BACK_LIGHT_WHITE_EX = f"{CSI}107m"

        else:
            print("!!! COLOUR PRINTING IS NOT SUPPORTED FOR YOUR SYSTEM !!!")
