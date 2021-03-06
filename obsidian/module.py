from __future__ import annotations

from dataclasses import dataclass, field
from typing import Type, Optional, List, Any
from typing import TypeVar
import importlib
import pkgutil
import os

from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger
from obsidian.constants import (
    InitError,
    InitRegisterError,
    DependencyError,
    FatalError,
    MODULESIMPORT,
    MODULESFOLDER,
    SERVERPATH
)


# Module Skeleton
@dataclass
class AbstractModule:
    NAME: str = ""
    DESCRIPTION: str = ""
    AUTHOR: str = ""
    VERSION: str = ""
    DEPENDENCIES: list = field(default_factory=list)


# Submodule Manager Skeleton
@dataclass
class AbstractManager:
    NAME: str

    def _initSubmodule(self, submodule: Any, module: AbstractModule):
        Logger.debug(f"Registering Block {submodule.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        # Create Object
        obj = submodule()
        # Initialize Object Variables
        obj.NAME = submodule.NAME
        obj.DESCRIPTION = submodule.DESCRIPTION
        obj.VERSION = submodule.VERSION
        obj.OVERRIDE = submodule.OVERRIDE
        obj.MANAGER = submodule.MANAGER
        obj.MODULE = module

        return obj


# Submodule Skeleton
@dataclass
class AbstractSubmodule:
    NAME: str = ""
    DESCRIPTION: str = ""
    VERSION: str = ""
    OVERRIDE: bool = False
    MANAGER: Optional[AbstractManager] = None
    MODULE: Optional[AbstractModule] = None


# Internal Module Manager Singleton
class _ModuleManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("Module")

        # Creates List Of Modules That Has The Module Name As Keys
        self._module_list = dict()
        self._module_files = []
        self._module_blacklist = []
        self._sorted_module_graph = []
        self._completed = False
        self._ensure_core = True
        self._error_list = []  # Logging Which Modules Encountered Errors While Loading Up

    # Function to libimport all modules
    # EnsureCore ensures core module is present
    def initModules(self, blacklist=[], ensureCore=True):
        # Setting Vars
        self._ensure_core = ensureCore
        self._module_blacklist = blacklist

        # --- PreInitialization ---
        Logger.info("=== (1/X) PreInitializing Modules ===", module="init-modules")

        # Initialization Step One => Scanning and Loading Modules using PkgUtils
        Logger.info(f"Scanning modules in {MODULESFOLDER}", module="module-import")
        self._importModules()

        # --- Dependency Resolving ---
        Logger.info("=== (2/X) Resolving Dependencies ===", module="init-modules")

        # Initialization Part Two => Checking and Initializing Dependencies
        Logger.info("Checking and Initializing Dependencies...", module="module-resolve")
        self._initDependencies()
        Logger.info("Dependencies Initialized!", module="module-resolve")

        # Initialization Part Two and a Half => Resolving Dependency Cycles
        Logger.info("Resolving Dependency Cycles...", module="module-verify")
        self._resolveDependencyCycles()
        Logger.info("Cycles Resolved!", module="module-verify")

        # --- Initialization Preparation ---
        Logger.info("=== (3/X) Preparing Initialization ===", module="init-modules")

        # Initialization Part Three => Building Dependency Graph
        Logger.info("Building Dependency Graph...", module="module-prep")
        self._buildDependencyGraph()
        Logger.info("Dependency Graph Generated!", module="module-prep")

        Logger.info("Dependencies Resolved!", module="module-resolve")
        Logger.info("PreInitializing Done!", module="module-preinit")

        # --- Initialization ---
        Logger.info("=== (4/X) Initializing Modules ===", module="init-modules")

        # Initialization Part Four => Initialize Submodules
        Logger.info("Initializing Submodules...", module="submodule-init")
        self._initSubmodules()

        # TODO: Temporarily Stop Program
        Logger.log(self._module_files)
        Logger.log(self._module_list)
        Logger.log(self._sorted_module_graph)
        # TEMPORARY IMPORT FOR PRINTING BLOCKS
        from obsidian.blocks import BlockManager
        Logger.log(BlockManager._block_list)
        Logger.askConfirmation()
        raise NotImplementedError("TODO")

    # Intermediate Function To Import All Modules
    def _importModules(self):
        # Walk Through All Packages And Import Library
        for _, module_name, _ in pkgutil.walk_packages([os.path.join(SERVERPATH, MODULESFOLDER)]):
            # Lowercase Name
            module_name = module_name.lower()
            # Load Modules
            Logger.debug(f"Detected Module {module_name}", module="module-import")
            if module_name not in self._module_blacklist:
                try:
                    Logger.verbose(f"Module {module_name} Not In Blacklist. Adding!", module="module-import")
                    _module = importlib.import_module(MODULESIMPORT + module_name)
                    self._module_files.append(module_name)
                    globals()[module_name] = _module
                except FatalError as e:
                    # Pass Down Fatal Error To Base Server
                    raise e
                except Exception as e:
                    self._error_list.append((module_name, "PreInit-Import"))  # Module Loaded WITH Errors
                    if type(e) is InitRegisterError:
                        printTb = False
                    else:
                        printTb = True
                    Logger.error(f"Error While Importing Module {module_name} - {type(e).__name__}: {e}\n", module="module-import", printTb=printTb)
                    Logger.warn("!!! Fatal Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-import")
                    Logger.askConfirmation()
            else:
                Logger.verbose(f"Skipping Module {module_name} Due To Blacklist", module="module-import")
        Logger.verbose(f"Detected and Imported Module Files {self._module_files}", module="module-import")
        # Check If Core Was Loaded
        if self._ensure_core:
            if "core" not in self._module_list.keys():
                self._error_list.append(("core", "PreInit-EnsureCore"))  # Module Loaded WITH Errors
                raise FatalError("Error While Loading Module core - Critical Module Not Found")

    # Intermediate Function to Check and Initialize Dependencies
    def _initDependencies(self):
        for module_name, module_obj in list(self._module_list.items()):
            try:
                Logger.debug(f"Checking Dependencies for Module {module_name}", module="module-resolve")
                # Loop through all dependencies, check type, then check if exists
                for dependency in module_obj.DEPENDENCIES:
                    dep_name = dependency.NAME
                    dep_ver = dependency.VERSION
                    Logger.verbose(f"Checking if Dependency {dep_name} Exists", module="module-resolve")
                    # Check if Dependency is "Loaded"
                    if dep_name in self._module_list.keys():
                        # Check if Version should be checked
                        if dep_ver is None:
                            Logger.verbose(f"Skipping Version Check For Dependency {dependency}", module="module-resolve")
                            pass  # No Version Check Needed
                        elif dep_ver == self._module_list[dependency.NAME].VERSION:
                            Logger.verbose(f"Dependencies {dependency} Statisfied!", module="module-resolve")
                            pass
                        else:
                            raise DependencyError(f"Dependency '{dependency}' Has Unmatched Version! (Requirement: {dep_ver} | Has: {self._module_list[dependency.NAME].VERSION})")
                        # If All Passes, Link Module Class
                        dependency.MODULE = self._module_list[dependency.NAME]
                    else:
                        raise DependencyError(f"Dependency '{dependency}' Not Found!")
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                self._error_list.append((module_name, "PreInit-Dependency"))  # Module Loaded WITH Errors
                if type(e) is DependencyError:
                    printTb = False
                else:
                    printTb = True
                Logger.error(f"Error While Initializing Dependencies For {module_name} - {type(e).__name__}: {e}\n", module="module-resolve", printTb=printTb)
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-resolve")
                Logger.warn(f"Skipping Module {module_name}?", module="module-resolve")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {module_name} From Loader!", module="module-resolve")
                del self._module_list[module_name]

    # Intermediate Function to Resolve Circular Dependencies
    def _resolveDependencyCycles(self):
        # Helper Function To Run Down Module Dependency Tree To Check For Cycles
        def _ensureNoCycles(current: Type[AbstractModule], previous: List[str]):
            Logger.verbose(f"Travelling Down Dependency Tree. CUR: {current} PREV: {previous}", module="cycle-check")
            # If Current Name Appears In Any Previous Dependency, There Is An Infinite Cycle
            if current.NAME in previous:
                raise DependencyError(f"Circular dependency Detected: {' -> '.join([*previous, current.NAME])}")

            Logger.verbose(f"Current Modules Has Dependencies {current.DEPENDENCIES}", module="cycle-check")
            for dependency in current.DEPENDENCIES:
                _ensureNoCycles(dependency.MODULE, [*previous, current.NAME])

        for module_name, module_obj in list(self._module_list.items()):
            try:
                Logger.debug(f"Ensuring No Circular Dependencies For Module {module_name}", module="module-verify")
                # Run DFS Through All Decencies To Check If Cycle Exists
                _ensureNoCycles(module_obj, [])
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                self._error_list.append((module_name, "PreInit-Dependency"))  # Module Loaded WITH Errors
                if type(e) is DependencyError:
                    printTb = False
                else:
                    printTb = True
                Logger.error(f"Error While Resolving Dependency Cycles For {module_name} - {type(e).__name__}: {e}\n", module="module-verify", printTb=printTb)
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-verify")
                Logger.warn(f"Skipping Module {module_name}?", module="module-verify")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {module_name} From Loader!", module="module-verify")
                del self._module_list[module_name]

    # Intermediate Function to Build Dependency Graph
    def _buildDependencyGraph(self):
        Logger.debug("Generating Dependency Graph", module="module-prep")
        # Define Visited Set
        visited = set()
        # Reset and Clear Current Module Graph
        self._sorted_module_graph = []

        # Helper Function to Run Topological Sort DFS
        def _topologicalSort(module):
            Logger.verbose(f"Running Topological Sort on {module.NAME}", module="topological-sort")
            # Adding Module to Visited Set to Prevent Looping
            visited.add(module.NAME)

            # Going Bottom First
            Logger.verbose(f"Attempting Topological Sort on {module.NAME}'s Dependencies {module.DEPENDENCIES}", module="topological-sort")
            for dependency in module.DEPENDENCIES:
                if dependency.NAME not in visited:
                    _topologicalSort(dependency.MODULE)

            # Current Module has No Further Dependencies. Adding To Graph!
            self._sorted_module_graph.append(module)
            Logger.verbose(f"Added {module.NAME} To Dependency Graph. DG Is Now {self._sorted_module_graph}", module="topological-sort")

        # Run Topological Sort on All Non-Visited Modules
        for module_name in list(self._module_list.keys()):
            Logger.verbose(f"Attempting Topological Sort on {module_name}", module="module-prep")
            if module_name not in visited:
                _topologicalSort(self._module_list[module_name])

        # Print Out Status
        Logger.debug(f"Finished Generating Dependency Graph. Result: {self._sorted_module_graph}", module="module-prep")

    # Intermediate Function to Initialize Submodules
    def _initSubmodules(self):
        # Loop through all the submodules in the order of the sorted graph
        for module in self._sorted_module_graph:
            try:
                Logger.debug(f"Checking All Items in {module.NAME}", module=f"{module.NAME}-submodule-init")
                for _, item in module.__dict__.items():  # Loop Through All Items In Class
                    if hasattr(item, "obsidian_submodule"):  # Check If Item Has "obsidian_submodule" Flag
                        Logger.verbose(f"{item} Is A Submodule! Adding As {module.NAME} Submodule.", module=f"{module.NAME}-submodule-init")
                        # Register Submodule Using information Provided by Submodule Class
                        item.MANAGER.register(item, module)
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                self._error_list.append((module.NAME, "Init-Submodule"))  # Module Loaded WITH Errors
                Logger.error(f"Error While Initializing Dependencies For {module.NAME} - {type(e).__name__}: {e}\n", module="submodule-init")
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="submodule-init")
                Logger.warn(f"Skipping Module {module.NAME}?", module="submodule-init")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {module.NAME} From Loader!", module="submodule-init")
                del self._module_list[module.NAME]

    # Intermediate Function to Initialize Modules
    def _initModules(self):
        for modules in self._sorted_module_graph:
            Logger.verbose(f"TEMP {modules}")
            pass

    # Registration. Called by Module Decorator
    def register(
        self,
        name: str,
        description: str,
        author: str,
        version: str,
        dependencies: Optional[list],
        module: Type[AbstractModule]
    ):
        Logger.info(f"Discovered Module {name}.", module="module-import")
        Logger.debug(f"Registering Module {name}", module="module-import")

        # Lowercase Name
        name = name.lower()
        # Checking If Module Is Already In Modules List
        if name in self._module_list.keys():
            raise InitRegisterError(f"Module {name} Has Already Been Registered!")
        # Check If Module Is Blacklisted
        if name in self._module_blacklist:
            return  # Skip
        # Format Empty Dependencies
        if dependencies is None:
            dependencies = []
        # Checking If Core Is Required
        if self._ensure_core:
            if "core" not in [m.NAME for m in dependencies]:
                dependencies.append(Dependency("core"))

        # Attach Values As Attribute
        module.NAME = name
        module.DESCRIPTION = description
        module.AUTHOR = author
        module.VERSION = version
        module.DEPENDENCIES = dependencies
        self._module_list[name] = module

    '''
    # Registration. Called by Module Decorator
    def register(self, name: str, description: str, author: str, version: str, module: Type[AbstractModule]):
        Logger.info(f"Discovered Module {name}.", module="init-" + name)
        Logger.debug(f"Registering Module {name}", module="init-" + name)
        # Prevent Circular Looping :/
        from obsidian.packet import PacketManager
        from obsidian.worldformat import WorldFormatManager
        from obsidian.mapgen import MapGeneratorManager
        from obsidian.commands import CommandManager
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
            elif hasattr(item, "obsidian_command"):  # Check If Item Has "obsidian_command" Flag
                Logger.verbose(f"{item} Is A Command! Adding As Command.", module="init-" + name)
                generator = item.obsidian_command
                # Register Packet Using information Provided By "obsidian_block"
                CommandManager.register(
                    generator["name"],
                    generator["activators"],
                    generator["description"],
                    generator["version"],
                    generator["command"],
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
                    Logger.fatal("Core Module Not Found! (Failed ensureCore). Check if 'core.py' module is present in modules folder!", module="init-module")
                    raise InitError("Core Module Not Found!")
                except FatalError as e:
                    # Pass Down Fatal Error To Base Server
                    raise e
                except Exception as e:
                    self._errorList.append("core")  # Module Loaded WITH Errors
                    Logger.fatal(f"Error While Loading Module core - {type(e).__name__}: {e}", "init-module")
                    raise FatalError()
            Logger.verbose(f"Scanning all potential modules in {MODULESFOLDER}", module="init-module")
            for loader, module_name, _ in pkgutil.walk_packages([os.path.join(SERVERPATH, MODULESFOLDER)]):
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
                        Logger.error(f"Error While Loading Module {module_name} - {type(e).__name__}: {e}\n", module="init-module", printTb=printTb)
                        Logger.warn("!!! Fatal Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="init-module")
                        Logger.askConfirmation()
                Logger.verbose(f"Skipping Module {module_name} Due To Blacklist", module="init-module")
            self._completed = True  # setting completed flag to prevent re-importation
        else:
            Logger.info("Modules Already Initialized; Skipping.", module="init-module")

    '''

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
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

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


# Dependency Object
@dataclass
class Dependency:
    # Base Init - Main Data
    def __init__(self, name, version=None):
        # User Defined Values
        self.NAME = name.lower()
        self.VERSION = version
        # Reference To The Module Class - Handeled By Init Dependencies
        self.MODULE = None

    # Implement Iter to Support Unpacking
    def __iter__(self):
        return iter((self.NAME, self.VERSION))

    # Format String
    def __str__(self):
        return f"<Name: {self.NAME}, Version: {self.VERSION}>"

    # Actions when Printing Class
    def __repr__(self):
        return self.__str__()


# Module Registration Decorator
# Used In @Module
def Module(
    name: str,
    description: str = None,
    author: str = None,
    version: str = None,
    dependencies: Optional[list] = None
):
    def internal(cls):
        ModuleManager.register(name, description, author, version, dependencies, cls)
        return cls
    return internal


# Creates Global ModuleManager As Singleton
ModuleManager = _ModuleManager()
# Adds Alias To ModuleManager
Modules = ModuleManager
