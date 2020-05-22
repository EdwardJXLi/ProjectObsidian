import os

#Server Version
__version__ = 'DEV-X.X.X'

CSI = '\u001b[' #ANSII Colour Header 

class Colour():
    BLACK  = ""
    RED    = ""
    GREEN  = ""
    YELLOW = ""
    BLUE   = ""
    MAGENT = ""
    CYAN   = ""
    WHITE  = ""
    RESET  = ""
    NONE   = ""
    LIGHTBLACK_EX   = ""
    LIGHTRED_EX     = ""
    LIGHTGREEN_EX   = ""
    LIGHTYELLOW_EX  = ""
    LIGHTBLUE_EX    = ""
    LIGHTMAGENTA_EX = ""
    LIGHTCYAN_EX    = ""
    LIGHTWHITE_EX   = ""
    BACK_BLACK  = ""
    BACK_RED    = ""
    BACK_GREEN  = ""
    BACK_YELLOW = ""
    BACK_BLUE   = ""
    BACK_MAGENT = ""
    BACK_CYAN   = ""
    BACK_WHITE  = ""
    BACK_RESET  = ""
    BACK_NONE   = ""
    BACK_LIGHTBLACK_EX   = ""
    BACK_LIGHTRED_EX     = ""
    BACK_LIGHTGREEN_EX   = ""
    BACK_LIGHTYELLOW_EX  = ""
    BACK_LIGHTBLUE_EX    = ""
    BACK_LIGHTMAGENTA_EX = ""
    BACK_LIGHTCYAN_EX    = ""
    BACK_LIGHTWHITE_EX   = ""

    @classmethod
    def init(cls):
        if(os.name == "posix"):
            #Foreground Standard
            cls.BLACK  = f"{CSI}30m"
            cls.RED    = f"{CSI}31m"
            cls.GREEN  = f"{CSI}32m"
            cls.YELLOW = f"{CSI}33m"
            cls.BLUE   = f"{CSI}34m"
            cls.MAGENT = f"{CSI}35m"
            cls.CYAN   = f"{CSI}36m"
            cls.WHITE  = f"{CSI}37m"
            cls.RESET  = f"{CSI}39m"
            #Foreground Semi-Supported
            cls.LIGHTBLACK_EX   = f"{CSI}90"
            cls.LIGHTRED_EX     = f"{CSI}91"
            cls.LIGHTGREEN_EX   = f"{CSI}92"
            cls.LIGHTYELLOW_EX  = f"{CSI}93"
            cls.LIGHTBLUE_EX    = f"{CSI}94"
            cls.LIGHTMAGENTA_EX = f"{CSI}95"
            cls.LIGHTCYAN_EX    = f"{CSI}96"
            cls.LIGHTWHITE_EX   = f"{CSI}97"

            #Background Standard
            cls.BACK_BLACK   = f"{CSI}40"
            cls.BACK_RED     = f"{CSI}41"
            cls.BACK_GREEN   = f"{CSI}42"
            cls.BACK_YELLOW  = f"{CSI}43"
            cls.BACK_BLUE    = f"{CSI}44"
            cls.BACK_MAGENTA = f"{CSI}45"
            cls.BACK_CYAN    = f"{CSI}46"
            cls.BACK_WHITE   = f"{CSI}47"
            cls.BACK_RESET   = f"{CSI}49"
            #Background Semi-Supported
            cls.BACK_LIGHTBLACK_EX   = f"{CSI}100"
            cls.BACK_LIGHTRED_EX     = f"{CSI}101"
            cls.BACK_LIGHTGREEN_EX   = f"{CSI}102"
            cls.BACK_LIGHTYELLOW_EX  = f"{CSI}103"
            cls.BACK_LIGHTBLUE_EX    = f"{CSI}104"
            cls.BACK_LIGHTMAGENTA_EX = f"{CSI}105"
            cls.BACK_LIGHTCYAN_EX    = f"{CSI}106"
            cls.BACK_LIGHTWHITE_EX   = f"{CSI}107"

        else:
            print("!!! COLOUR PRINTING IS NOT SUPPORTED FOR YOUR SYSTEM !!!")
