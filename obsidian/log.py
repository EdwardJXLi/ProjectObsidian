import time

from obsidian.constants import *

class Logger:
    @staticmethod
    def getTimestamp():
        return time.strftime("%H:%M:%S", time.localtime())

    @classmethod
    def log(cls, message, level=None, module=None, colour=Colour.NONE, textColour=Colour.NONE):
        if(level != None):
            #Generate Strings
            timestampStr = f"{colour}{cls.getTimestamp()}{Colour.RESET}"
            levelStr = f"{colour}{level.upper()}{Colour.RESET}"
            moduleStr = f"{colour}{module.upper()}{Colour.RESET}"
            msgString = f"{textColour}{message}{Colour.RESET}"
            #Concatenate String
            print(f"[{timestampStr}][{levelStr}][{moduleStr}]: {msgString}")
        else:
            print(message)

    @classmethod
    def info(cls, message, module="obsidian"):
        cls.log(message, level="log", module=module, colour=Colour.GREEN, textColour=Colour.WHITE)
    
    @classmethod
    def debug(cls, message, module="obsidian"):
        cls.log(message, level="debug", module=module, colour=Colour.CYAN, textColour=Colour.WHITE)