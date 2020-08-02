from __future__ import annotations

from dataclasses import dataclass
from typing import Type
import importlib
import pkgutil

from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger
from obsidian.constants import (
    InitError,
    InitRegisterError,
    FatalError,
    MODULESIMPORT,
    MODULESFOLDER
)


# Module Skeleton
@dataclass
class AbstractModule:
    # Optional Values Defined In Module Decorator
    NAME: str = ""
    DESCRIPTION: str = ""
    AUTHOR: str = ""
    VERSION: str = ""


# Internal Module Manager Singleton
class _ModuleManager:
    def __init__(self):
        # Creates List Of Modules That Has The Module Name As Keys
        self._module_list = dict()
        self._completed = False
        self._errorList = []  # Logging Which Modules Encountered Errors While Loading Up

    # Registration. Called by Module Decorator
    def register(self, name: str, description: str, author: str, version: str, module: Type[AbstractModule]):
        Logger.info(f"Discovered Module {name}.", module="init-" + name)
        Logger.debug(f"Registering Module {name}", module="init-" + name)
        # Prevent Circular Looping :/
        from obsidian.packet import PacketManager
        from obsidian.worldformat import WorldFormatManager
        from obsidian.mapgen import MapGeneratorManager
        from obsidian.blocks import BlockManager
        moduleObj = module()  # Create Object
        # Checking If Module Is Already In Modules List
        if name in self._module_list.keys():
            raise InitRegisterError(f"Module {name} Has Already Been Registered!")
        # Attach Values As Attribute
        moduleObj.NAME = name
        moduleObj.DESCRIPTION = description
        moduleObj.AUTHOR = author
        moduleObj.VERSION = version
        Logger.verbose(f"Looping Through All Items In {name}", module="init-" + name)
        for _, item in module.__dict__.items():  # Loop Through All Items In Class
            Logger.verbose(f"Checking {item}", module="init-" + name)
            if hasattr(item, "obsidian_packet"):  # Check If Item Has "obsidian_packet" Flag
                Logger.verbose(f"{item} Is A Packet! Adding As Packet.", module="init-" + name)
                packet = item.obsidian_packet
                # Register Packet Using information Provided By "obsidian_packet"
                PacketManager.register(
                    packet["direction"],
                    packet["name"],
                    packet["description"],
                    packet["packet"],
                    moduleObj
                )
            elif hasattr(item, "obsidian_world_format"):  # Check If Item Has "obsidian_world_format" Flag
                Logger.verbose(f"{item} Is A World Format! Adding As World Format.", module="init-" + name)
                generator = item.obsidian_world_format
                # Register Packet Using information Provided By "obsidian_world_format"
                WorldFormatManager.register(
                    generator["name"],
                    generator["description"],
                    generator["version"],
                    generator["format"],
                    moduleObj
                )
            elif hasattr(item, "obsidian_map_generator"):  # Check If Item Has "obsidian_map_generator" Flag
                Logger.verbose(f"{item} Is A Map Generator! Adding As Map Generator.", module="init-" + name)
                generator = item.obsidian_map_generator
                # Register Packet Using information Provided By "obsidian_map_generator"
                MapGeneratorManager.register(
                    generator["name"],
                    generator["description"],
                    generator["version"],
                    generator["map_generator"],
                    moduleObj
                )
            elif hasattr(item, "obsidian_block"):  # Check If Item Has "obsidian_block" Flag
                Logger.verbose(f"{item} Is A Block! Adding As Block.", module="init-" + name)
                generator = item.obsidian_block
                # Register Packet Using information Provided By "obsidian_block"
                BlockManager.register(
                    generator["name"],
                    generator["blockId"],
                    generator["block"],
                    moduleObj
                )
        self._module_list[name] = moduleObj

    # Function to libimport and register all modules
    # EnsureCore ensures core module is present
    def initModules(self, blacklist=[], ensureCore=True):
        if not self._completed:
            Logger.info("Initializing Modules", module="init-module")
            if ensureCore:
                try:
                    importlib.import_module(MODULESIMPORT + "core")
                    blacklist.append("core")  # Adding core to whitelist to prevent re-importing
                    Logger.debug("Loaded (mandatory) Module core", module="init-module")
                except ModuleNotFoundError:
                    Logger.fatal("Core Module Not Found! (Failed ensureCore). Check if 'core.py' module is present in modules folder!")
                    raise InitError("Core Module Not Found!")
                except FatalError as e:
                    # Pass Down Fatal Error To Base Server
                    raise e
                except Exception as e:
                    self._errorList.append("core")  # Module Loaded WITH Errors
                    Logger.fatal(f"Error While Loading Module core - {type(e).__name__}: {e}", "init-module")
                    raise FatalError()
            Logger.verbose(f"Scanning all potential modules in {MODULESFOLDER}", module="init-module")
            for loader, module_name, _ in pkgutil.walk_packages([MODULESFOLDER]):
                Logger.verbose(f"Detected Module {module_name}", module="init-module")
                if module_name not in blacklist:
                    try:
                        Logger.verbose(f"Module {module_name} Not In Blacklist. Adding!", module="init-module")
                        _module = loader.find_module(module_name).load_module(module_name)
                        globals()[module_name] = _module
                    except FatalError as e:
                        # Pass Down Fatal Error To Base Server
                        raise e
                    except Exception as e:
                        self._errorList.append(module_name)  # Module Loaded WITH Errors
                        if type(e) is InitRegisterError:
                            printTb = False
                        else:
                            printTb = True
                        Logger.error(f"Error While Loading Module {module_name} - {type(e).__name__}: {e}", "init-module", printTb=printTb)
                Logger.verbose(f"Skipping Module {module_name} Due To Blacklist", module="init-module")
            self._completed = True  # setting completed flag to prevent re-importation
        else:
            Logger.info("Modules Already Initialized; Skipping.", module="init-module")

    # Generate a Pretty List of Modules
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Module", "Author", "Version"]
            # Loop Through All Modules And Add Value
            for _, module in self._module_list.items():
                # Adding Special Characters And Handlers
                if module.VERSION is None:
                    module.VERSION = "Unknown"
                if module.AUTHOR is None:
                    module.AUTHOR = "Unknown"

                # Add Row To Table
                table.add_row([module.NAME, module.AUTHOR, module.VERSION])
            return table
        except FatalError as e:
            # Pass Down Fatal Error To Base Server
            raise e
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", "server")

    # Property Method To Get Number Of Modules
    @property
    def numModules(self):
        return len(self._module_list)

    # Handles _ModuleManager["item"]
    def __getitem__(self, module: str):
        return self._module_list[module]

    # Handles _ModuleManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Module Registration Decorator
# Used In @Module
def Module(name: str, description: str = None, author: str = None, version: str = None):
    def internal(cls):
        ModuleManager.register(name, description, author, version, cls)
    return internal


# Creates Global ModuleManager As Singleton
ModuleManager = _ModuleManager()
# Adds Alias To ModuleManager
Modules = ModuleManager
