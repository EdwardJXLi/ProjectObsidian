from __future__ import annotations

from dataclasses import dataclass, field
from typing import Type, Optional, List, Any
import importlib
import pkgutil
import os

from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger
from obsidian.constants import (
    InitRegisterError,
    DependencyError,
    InitError,
    PostInitError,
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

    def postInit(*args, **kwargs):
        pass


# Manager Skeleton
@dataclass
class AbstractManager:
    NAME: str

    def _initSubmodule(self, submodule: Any, module: AbstractModule):
        Logger.debug(f"Initializing {submodule.MANAGER.NAME} {submodule.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        # Create Object
        obj = submodule()
        # Initialize and Transfer Object Variables
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
        self._module_blacklist = []
        self._sorted_module_graph = []
        self._completed = False
        self._ensure_core = True
        self._error_list = []  # Logging Which Modules Encountered Errors While Loading Up

    # Function to libimport all modules
    # EnsureCore ensures core module is present
    def initModules(self, blacklist: List[str] = [], ensureCore: bool = True):
        # Setting Vars
        self._ensure_core = ensureCore
        self._module_blacklist = blacklist

        # --- PreInitialization ---
        Logger.info("=== (1/6) PreInitializing Modules ===", module="init-modules")

        # Initialization Step One => Scanning and Loading Modules using PkgUtils
        Logger.info(f"Scanning modules in {MODULESFOLDER}", module="module-import")
        self._importModules()

        # --- Dependency Resolving ---
        Logger.info("=== (2/6) Resolving Dependencies ===", module="init-modules")

        # Initialization Part Two => Checking and Initializing Dependencies
        Logger.info("Checking and Initializing Dependencies...", module="module-resolve")
        self._initDependencies()
        Logger.info("Dependencies Initialized!", module="module-resolve")

        # Initialization Part Two and a Half => Resolving Dependency Cycles
        Logger.info("Resolving Dependency Cycles...", module="module-verify")
        self._resolveDependencyCycles()
        Logger.info("Cycles Resolved!", module="module-verify")

        # --- Initialization Preparation ---
        Logger.info("=== (3/6) Preparing Initialization ===", module="init-modules")

        # Initialization Part Three => Building Dependency Graph
        Logger.info("Building Dependency Graph...", module="module-prep")
        self._buildDependencyGraph()
        Logger.info("Dependency Graph Generated!", module="module-prep")

        Logger.info("Dependencies Resolved!", module="module-resolve")
        Logger.info("PreInitializing Done!", module="module-preinit")

        # --- Initialization (Submodules) ---
        Logger.info("=== (4/6) Initializing Submodules ===", module="init-modules")

        # Initialization Part Four => Initialize Submodules
        Logger.info("Initializing Submodules...", module="submodule-init")
        self._initSubmodules()
        Logger.info("Submodules Initialized!", module="submodule-init")

        # --- Initialization (Modules) ---
        Logger.info("=== (5/6) Initializing Submodules ===", module="init-modules")

        # Initialization Part Five => Initialize Modules
        Logger.info("Initializing Modules...", module="module-init")
        self._initModules()
        Logger.info("Modules Initialized!", module="module-init")

        Logger.info("Initializing Done!", module="module-init")

        # --- Finalizing Initialization ---
        Logger.info("=== (6/6) Finalizing Initialization ===", module="init-modules")

        # Initialization Part Six => Running Post-Initialization
        Logger.info("Running Post-Initializing...", module="post-init")
        self._postInit()
        Logger.info("Post-Initializing Done!...", module="post-init")

        Logger.info("Module Done Finalizing!", module="module-init")

        # Initialization Procedure Done!

    # Intermediate Function To Import All Modules
    def _importModules(self):
        # Initialize Temporary List of Files Imported
        _module_files = []
        # Walk Through All Packages And Import Library
        for _, module_name, _ in pkgutil.walk_packages([os.path.join(SERVERPATH, MODULESFOLDER)]):
            # Load Modules
            Logger.debug(f"Detected Module {module_name}", module="module-import")
            if module_name not in self._module_blacklist:
                try:
                    Logger.verbose(f"Module {module_name} Not In Blacklist. Adding!", module="module-import")
                    # Import Module
                    _module = importlib.import_module(MODULESIMPORT + module_name)
                    # Appending To A List of Module Files to be Used Later
                    _module_files.append(module_name)
                    # Set the Imported Module into the Global Scope
                    globals()[module_name] = _module
                except FatalError as e:
                    # Pass Down Fatal Error To Base Server
                    raise e
                except Exception as e:
                    # Handle Exception if Error Occurs
                    self._error_list.append((module_name, "PreInit-Import"))  # Module Loaded WITH Errors
                    # If the Error is a Register Error (raised on purpose), Don't print out TB
                    if type(e) is InitRegisterError:
                        printTb = False
                    else:
                        printTb = True
                    Logger.error(f"Error While Importing Module {module_name} - {type(e).__name__}: {e}\n", module="module-import", printTb=printTb)
                    Logger.warn("!!! Fatal Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-import")
                    Logger.askConfirmation()
            else:
                Logger.verbose(f"Skipping Module {module_name} Due To Blacklist", module="module-import")
        Logger.verbose(f"Detected and Imported Module Files {_module_files}", module="module-import")
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
                    # Get Variables
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
                # Handle Exception if Error Occurs
                self._error_list.append((module_name, "PreInit-Dependency"))  # Module Loaded WITH Errors
                # If the Error is a Dependency Error (raised on purpose), Don't print out TB
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
            # Run DFS through All Dependencies
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
                # Handle Exception if Error Occurs
                self._error_list.append((module_name, "PreInit-Dependency"))  # Module Loaded WITH Errors
                # If the Error is a Dependency Error (raised on purpose), Don't print out TB
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

            # DFS Going Bottom First
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
                # Loop Through All Items within Module
                Logger.debug(f"Checking All Items in {module.NAME}", module=f"{module.NAME}-submodule-init")
                # Loop Through All Items In Class
                for _, item in module.__dict__.items():
                    # Check If Item Has "obsidian_submodule" Flag
                    if hasattr(item, "obsidian_submodule"):
                        Logger.verbose(f"{item} Is A Submodule! Adding As {module.NAME} Submodule.", module=f"{module.NAME}-submodule-init")
                        # Register Submodule Using information Provided by Submodule Class
                        item.MANAGER.register(item, module)
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._error_list.append((module.NAME, "Init-Submodule"))  # Module Loaded WITH Errors
                # If the Error is an Init Error (raised on purpose), Don't print out TB
                if type(e) is InitError:
                    printTb = False
                else:
                    printTb = True
                Logger.error(f"Error While Initializing Submodules For {module.NAME} - {type(e).__name__}: {e}\n", module="submodule-init", printTb=printTb)
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="submodule-init")
                Logger.warn(f"Skipping Module {module.NAME}?", module="submodule-init")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {module.NAME} From Loader!", module="submodule-init")
                del self._module_list[module.NAME]

    # Intermediate Function to Initialize Modules
    def _initModules(self):
        for module in self._sorted_module_graph:
            try:
                Logger.debug(f"Initializing Module {module.NAME}", module=f"{module.NAME}-init")
                # Initialize Module
                initializedModule = module()
                # Initialize and Transfer Module Variables
                initializedModule.NAME = module.NAME
                initializedModule.DESCRIPTION = module.DESCRIPTION
                initializedModule.AUTHOR = module.AUTHOR
                initializedModule.VERSION = module.VERSION
                initializedModule.DEPENDENCIES = module.DEPENDENCIES
                # Replacing Item in _module_list with the Initialized Version!
                self._module_list[module.NAME] = initializedModule
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._error_list.append((module.NAME, "Init-Module"))  # Module Loaded WITH Errors
                # If the Error is an Init Error (raised on purpose), Don't print out TB
                if type(e) is InitError:
                    printTb = False
                else:
                    printTb = True
                Logger.error(f"Error While Initializing Modules For {module.NAME} - {type(e).__name__}: {e}\n", module="module-init", printTb=printTb)
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-init")
                Logger.warn(f"Skipping Module {module.NAME}?", module="module-init")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {module.NAME} From Loader!", module="module-init")
                del self._module_list[module.NAME]

    # Intermediate Function to run Post-Initialization Scripts
    def _postInit(self):
        for module_name, module_obj in list(self._module_list.items()):
            try:
                Logger.debug(f"Running Post-Initialization for Module {module_name}", module=f"{module_name}-postinit")
                # Calling the Final Init function
                module_obj.postInit()
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._error_list.append((module_name, "Init-Final"))  # Module Loaded WITH Errors
                # If the Error is an Postinit Error (raised on purpose), Don't print out TB
                if type(e) is PostInitError:
                    printTb = False
                else:
                    printTb = True
                Logger.error(f"Error While Running Post-Initialization For {module_name} - {type(e).__name__}: {e}\n", module="postinit", printTb=printTb)
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="postinit")
                Logger.warn(f"Skipping Module {module_name}?", module="postinit")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {module_name} From Loader!", module="postinit")
                del self._module_list[module_name]

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
            if "core" not in [m.NAME for m in dependencies] and name != "core":
                dependencies.append(Dependency("core"))

        # Attach Values As Attribute
        module.NAME = name
        module.DESCRIPTION = description
        module.AUTHOR = author
        module.VERSION = version
        module.DEPENDENCIES = dependencies
        self._module_list[name] = module

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
    def __init__(self, name: str, version: Optional[str] = None):
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
