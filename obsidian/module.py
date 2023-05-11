from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Type, Optional, Callable, Generic
from pathlib import Path
import importlib
import pkgutil
import inspect

from obsidian.cpe import CPEModuleManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger
from obsidian.config import AbstractConfig
from obsidian.constants import (
    MANAGERS_LIST,
    MODULES_IMPORT,
    MODULES_FOLDER,
    SERVER_PATH
)
from obsidian.errors import (
    ModuleError,
    CPEError,
    InitRegisterError,
    ConverterError,
    DependencyError,
    InitError,
    PostInitError,
    FatalError
)
from obsidian.types import formatName, T


# Manager Skeleton
class AbstractManager(ABC):
    def __init__(self, name: str, submodule: Type[AbstractSubmodule] | Type[AbstractModule]):
        self.NAME = name
        self.SUBMODULE = submodule
        MANAGERS_LIST.append(self)

    def _initSubmodule(self, submodule: Any, module: AbstractModule):
        Logger.debug(f"Initializing {submodule.MANAGER.NAME} {submodule.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        # Create Object
        obj = submodule(
            submodule.NAME,
            submodule.DESCRIPTION,
            submodule.VERSION,
            submodule.OVERRIDE,
            submodule.MANAGER,
            module
        )

        # Append module onto list of submodules
        module.SUBMODULES.append(obj)

        return obj


# Module Skeleton
@dataclass
class AbstractModule(ABC):
    NAME: str
    DESCRIPTION: str
    AUTHOR: str
    VERSION: str
    DEPENDENCIES: list
    SUBMODULES: list[AbstractSubmodule] = field(default_factory=list)

    def initConfig(
        self,
        config: Type[T],
        *args,
        name: str = "config.json",
        overrideConfigPath: Optional[Path] = None,
        **kwargs
    ) -> T:
        # Checking if config is of right ty[e]
        if isinstance(config, AbstractConfig):
            raise Exception("Passed Config Must Extend `AbstractConfig`")

        # Generate the path
        Logger.info(f"Initializing Module Config {name} for module {self.NAME}", f"config-init-{self.NAME}")
        if overrideConfigPath:
            rootPath = overrideConfigPath
        else:
            rootPath = Path("configs", formatName(self.NAME))

        # Initialize and Return the config
        return config(name, *args, rootPath=rootPath, autoInit=True, hideWarning=True, **kwargs)

    def postInit(*args, **kwargs):
        pass

    @staticmethod
    def _convertArgument(_, argument: str) -> AbstractModule:
        try:
            # Try to grab the module from the modules list
            return ModuleManager.getModule(formatName(argument))
        except KeyError:
            # Raise error if module not found
            raise ConverterError(f"Module {argument} Not Found!")


# Submodule Skeleton
@dataclass
class AbstractSubmodule(ABC, Generic[T]):
    NAME: str
    DESCRIPTION: str
    VERSION: str
    OVERRIDE: bool
    MANAGER: AbstractManager
    MODULE: T

    def __post_init__(self):
        # Create alias for module
        self.module = self.MODULE

    @staticmethod
    def _convertArgument(ctx: Server, argument: str):
        return ConverterError(f"{T} Not Implemented")


# Internal Module Manager Singleton
class _ModuleManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("Module", AbstractModule)

        # Creates List Of Modules That Has The Module Name As Keys
        self._modulePreloadDict: dict[str, Type[AbstractModule]] = dict()
        self._moduleDict: dict[str, AbstractModule] = dict()
        self._moduleIgnorelist: list[str] = []
        self._sortedModuleGraph: list[Type[AbstractModule]] = []
        self._completed: bool = False
        self._ensureCore: bool = True
        self._initCpe: bool = False
        self._errorList: list[tuple[str, str]] = []  # Logging Which Modules Encountered Errors While Loading Up

    # Function to import all modules
    # EnsureCore ensures core module is present
    def initModules(self, ignorelist: list[str] = [], ensureCore: bool = True, initCPE: bool = False):
        # Setting Vars
        self._ensureCore = ensureCore
        self._moduleIgnorelist = ignorelist
        self._initCpe = initCPE

        # --- PreInitialization ---
        Logger.info("=== (1/6) PreInitializing Modules ===", module="init-modules")

        # Initialization Part One => Scanning and Loading Modules using PkgUtils
        Logger.info(f"Scanning modules in {MODULES_FOLDER}", module="module-import")
        self._importModules()

        # Initialization Part One and a Half => Checking CPE Support
        Logger.info("Checking for CPE Support", module="module-import")
        self._verifyCpeSupport()

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

        # --- Initialization (Modules) ---
        Logger.info("=== (4/6) Initializing Modules ===", module="init-modules")

        # Initialization Part Four => Initialize Modules
        Logger.info("Initializing Modules...", module="module-init")
        self._initModules()
        Logger.info("Modules Initialized!", module="module-init")

        Logger.info("Initializing Done!", module="module-init")

        # --- Initialization (Submodules) ---
        Logger.info("=== (5/6) Initializing Submodules ===", module="init-modules")

        # Initialization Part Five => Initialize Submodules
        Logger.info("Initializing Submodules...", module="submodule-init")
        self._initSubmodules()
        Logger.info("Submodules Initialized!", module="submodule-init")

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
        _moduleFiles = []
        # Walk Through All Packages And Import Library
        for _, moduleName, _ in pkgutil.walk_packages([str(Path(SERVER_PATH, MODULES_FOLDER))]):
            # Load Modules
            Logger.debug(f"Detected Module {moduleName}", module="module-import")
            if moduleName not in self._moduleIgnorelist:
                try:
                    Logger.verbose(f"Module {moduleName} Not In Ignore List. Adding!", module="module-import")
                    # Import Module
                    _module = importlib.import_module(MODULES_IMPORT + moduleName)
                    # Appending To A List of Module Files to be Used Later
                    _moduleFiles.append(moduleName)
                    # Set the Imported Module into the Global Scope
                    globals()[moduleName] = _module
                except FatalError as e:
                    # Pass Down Fatal Error To Base Server
                    raise e
                except Exception as e:
                    # Handle Exception if Error Occurs
                    self._errorList.append((moduleName, "PreInit-Import"))  # Module Loaded WITH Errors
                    # If the Error is a Register Error (raised on purpose), Don't print out TB
                    Logger.error(f"Error While Importing Module {moduleName} - {type(e).__name__}: {e}\n", module="module-import", printTb=not isinstance(e, InitRegisterError))
                    Logger.warn("!!! Fatal Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-import")
                    Logger.askConfirmation()
            else:
                Logger.verbose(f"Skipping Module {moduleName} Due To Ignore List", module="module-import")
        Logger.verbose(f"Detected and Imported Module Files {_moduleFiles}", module="module-import")
        # Check If Core Was Loaded
        if self._ensureCore:
            if "core" not in self._modulePreloadDict.keys():
                self._errorList.append(("core", "PreInit-EnsureCore"))  # Module Loaded WITH Errors
                raise FatalError("Error While Loading Module core - Critical Module Not Found")

    # Intermediate Function to Verify CPE Support
    def _verifyCpeSupport(self):
        # If CPE is supported by server, dont skip anything
        if self._initCpe:
            Logger.debug("CPE Support Enabled", module="verify-cpe")
            Logger.debug("Skipping CPE Support Check", module="verify-cpe")
            return

        # If CPE is not supported by server, check for CPE support in modules
        Logger.debug("CPE Support Disabled. Verifying CPE support.", module="verify-cpe")
        for moduleName, moduleType in list(self._modulePreloadDict.items()):
            try:
                Logger.debug(f"Checking CPE Support for Module {moduleName}", module="verify-cpe")
                if CPEModuleManager.hasCPE(moduleType):
                    Logger.debug(f"Module {moduleName} Implements a CPE Extension.", module="verify-cpe")
                    Logger.verbose(f"Checking whether CPE is enabled, and whether the {moduleName} module should be skipped...", module="verify-cpe")
                    if CPEModuleManager.shouldSkip(moduleType):
                        Logger.verbose(f"Skipping Module {moduleName} Due To CPE Settings", module="verify-cpe")
                        # Remove Module
                        Logger.debug(f"Removing Module {moduleName} From Loader!", module="verify-cpe")
                        del self._modulePreloadDict[moduleName]
                    else:
                        Logger.verbose(f"Module {moduleName} will not skipped.", module="verify-cpe")
                else:
                    Logger.verbose(f"Module {moduleName} does not implement a CPE Extension. Skipping Check!", module="verify-cpe")
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._errorList.append((moduleName, "PreInit-CPE-Check"))  # Module Loaded WITH Errors
                # If the Error is a CPE Error (raised on purpose), Don't print out TB
                Logger.error(f"Error While Verifying CPE Support For {moduleName} - {type(e).__name__}: {e}\n", module="verify-cpe", printTb=not isinstance(e, CPEError))
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="verify-cpe")
                Logger.warn(f"Skipping Module {moduleName}?", module="verify-cpe")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {moduleName} From Loader!", module="verify-cpe")
                if moduleName in self._modulePreloadDict:
                    del self._modulePreloadDict[moduleName]
                if moduleName in self._moduleDict:
                    del self._moduleDict[moduleName]

    # Intermediate Function to Check and Initialize Dependencies
    def _initDependencies(self):
        for moduleName, moduleType in list(self._modulePreloadDict.items()):
            try:
                Logger.debug(f"Checking Dependencies for Module {moduleName}", module="module-resolve")
                # Loop through all dependencies, check type, then check if exists
                for dependency in moduleType.DEPENDENCIES:
                    # Get Variables
                    depName = dependency.NAME
                    depVer = dependency.VERSION
                    Logger.verbose(f"Checking if Dependency {depName} Exists", module="module-resolve")
                    # Check if Dependency is "Loaded"
                    if depName in self._modulePreloadDict.keys():
                        # Check if Version should be checked
                        if depVer is None:
                            Logger.verbose(f"Skipping Version Check For Dependency {dependency}", module="module-resolve")
                            pass  # No Version Check Needed
                        elif depVer == self._modulePreloadDict[dependency.NAME].VERSION:
                            Logger.verbose(f"Dependencies {dependency} Satisfied!", module="module-resolve")
                            pass
                        else:
                            raise DependencyError(f"Dependency '{dependency}' Has Unmatched Version! (Requirement: {depVer} | Has: {self._moduleDict[dependency.NAME].VERSION})")
                        # If All Passes, Link Module Class
                        dependency.MODULE = self._modulePreloadDict[dependency.NAME]
                    else:
                        raise DependencyError(f"Dependency '{dependency}' Not Found!")
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._errorList.append((moduleName, "PreInit-Dependency"))  # Module Loaded WITH Errors
                # If the Error is a Dependency Error (raised on purpose), Don't print out TB
                Logger.error(f"Error While Initializing Dependencies For {moduleName} - {type(e).__name__}: {e}\n", module="module-resolve", printTb=not isinstance(e, DependencyError))
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-resolve")
                Logger.warn(f"Skipping Module {moduleName}?", module="module-resolve")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {moduleName} From Loader!", module="module-resolve")
                if moduleName in self._modulePreloadDict:
                    del self._modulePreloadDict[moduleName]
                if moduleName in self._moduleDict:
                    del self._moduleDict[moduleName]

    # Intermediate Function to Resolve Circular Dependencies
    def _resolveDependencyCycles(self):
        # Helper Function To Run Down Module Dependency Tree To Check For Cycles
        def _ensureNoCycles(current: Type[AbstractModule], previous: tuple[str, ...] = tuple()):
            Logger.verbose(f"Traveling Down Dependency Tree. CUR: {current} PREV: {previous}", module="cycle-check")
            # If Current Name Appears In Any Previous Dependency, There Is An Infinite Cycle
            if current.NAME in previous:
                raise DependencyError(f"Circular dependency Detected: {' -> '.join([*previous, current.NAME])}")

            Logger.verbose(f"Current Modules Has Dependencies {current.DEPENDENCIES}", module="cycle-check")
            # Run DFS through All Dependencies
            for dependency in current.DEPENDENCIES:
                _ensureNoCycles(dependency.MODULE, (*previous, current.NAME))

        for moduleName, moduleType in list(self._modulePreloadDict.items()):
            try:
                Logger.debug(f"Ensuring No Circular Dependencies For Module {moduleName}", module="module-verify")
                # Run DFS Through All Decencies To Check If Cycle Exists
                _ensureNoCycles(moduleType)
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._errorList.append((moduleName, "PreInit-Dependency"))  # Module Loaded WITH Errors
                # If the Error is a Dependency Error (raised on purpose), Don't print out TB
                Logger.error(f"Error While Resolving Dependency Cycles For {moduleName} - {type(e).__name__}: {e}\n", module="module-verify", printTb=not isinstance(e, DependencyError))
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-verify")
                Logger.warn(f"Skipping Module {moduleName}?", module="module-verify")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {moduleName} From Loader!", module="module-verify")
                if moduleName in self._modulePreloadDict:
                    del self._modulePreloadDict[moduleName]
                if moduleName in self._moduleDict:
                    del self._moduleDict[moduleName]

    # Intermediate Function to Build Dependency Graph
    def _buildDependencyGraph(self):
        Logger.debug("Generating Dependency Graph", module="module-prep")
        # Define Visited Set
        visited = set()
        # Reset and Clear Current Module Graph
        self._sortedModuleGraph = []

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
            self._sortedModuleGraph.append(module)
            Logger.verbose(f"Added {module.NAME} To Dependency Graph. DG Is Now {self._sortedModuleGraph}", module="topological-sort")

        # Run Topological Sort on All Non-Visited Modules
        for moduleName in list(self._modulePreloadDict.keys()):
            Logger.verbose(f"Attempting Topological Sort on {moduleName}", module="module-prep")
            if moduleName not in visited:
                _topologicalSort(self._modulePreloadDict[moduleName])

        # Print Out Status
        Logger.debug(f"Finished Generating Dependency Graph. Result: {self._sortedModuleGraph}", module="module-prep")

    # Intermediate Function to Initialize Modules
    def _initModules(self):
        for idx, module in enumerate(self._sortedModuleGraph):
            # Get the module name
            moduleName = module.NAME
            try:
                Logger.debug(f"Initializing Module {moduleName}", module=f"{moduleName}-init")
                # Initialize Module
                initializedModule = module(
                    module.NAME,
                    module.DESCRIPTION,
                    module.AUTHOR,
                    module.VERSION,
                    module.DEPENDENCIES
                )
                # Setting Item in _moduleDict with Initialized Version of _modulePreloadDict!
                self._moduleDict[moduleName] = initializedModule
                Logger.info(f"Initialized Module {moduleName}", module="init-module")
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._errorList.append((moduleName, "Init-Module"))  # Module Loaded WITH Errors
                # If the Error is an Init Error (raised on purpose), Don't print out TB
                Logger.error(f"Error While Initializing Modules For {moduleName} - {type(e).__name__}: {e}\n", module="module-init", printTb=not not isinstance(e, InitError))
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="module-init")
                Logger.warn(f"Skipping Module {moduleName}?", module="module-init")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {moduleName} From Loader!", module="module-init")
                if moduleName in self._modulePreloadDict:
                    del self._modulePreloadDict[moduleName]
                if moduleName in self._moduleDict:
                    del self._moduleDict[moduleName]

    # Intermediate Function to Initialize Submodules
    def _initSubmodules(self):
        # Loop through all the submodules in the order of the sorted graph
        for moduleType in self._sortedModuleGraph:
            # Get the module from the module dict
            module = self._moduleDict[moduleType.NAME]
            # Get the module name
            moduleName = module.NAME
            try:
                # Loop Through All Items within Module
                Logger.debug(f"Checking All Items in {moduleName}", module=f"{moduleName}-submodule-init")
                # Loop Through All Items In Class of Object
                for item in module.__class__.__dict__.values():
                    # Check If Item Has "obsidian_submodule" Flag
                    if hasattr(item, "obsidian_submodule"):
                        Logger.verbose(f"{item} Is A Submodule! Adding As {moduleName} Submodule.", module=f"{moduleName}-submodule-init")
                        # Register Submodule Using information Provided by Submodule Class
                        item.MANAGER.register(item, module)

                        # Check if all methods are registered
                        Logger.verbose(f"Checking if {item.MANAGER.NAME} {item.NAME} have all methods registered", module=f"{moduleName}-submodule-init")

                        # Get list of base class methods
                        baseMethods = [name for name, val in item.MANAGER.SUBMODULE.__dict__.items() if callable(val) and not name.startswith("__")]
                        Logger.verbose(f"{item.MANAGER.NAME} Base Class has methods: {baseMethods}", module=f"{moduleName}-submodule-init")
                        # Get list of currently registered methods
                        submoduleMethods = [name for name, val in item.__dict__.items() if callable(val) and not name.startswith("__")]
                        Logger.verbose(f"{item.MANAGER.NAME} {item.NAME} has methods: {submoduleMethods}", module=f"{moduleName}-submodule-init")

                        # Loop through all methods and check if they are registered
                        for methodName in baseMethods:
                            if methodName not in submoduleMethods:
                                if not methodName.startswith("_"):
                                    Logger.warn(f"{item.MANAGER.NAME} {item.NAME} Does Not Have Method {methodName} Registered!", module=f"{moduleName}-submodule-init")
                                    Logger.warn("This could cause issues when overriding methods!", module=f"{moduleName}-submodule-init")

            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._errorList.append((moduleName, "Init-Submodule"))  # Module Loaded WITH Errors
                # If the Error is an Init Error (raised on purpose), Don't print out TB
                Logger.error(f"Error While Initializing Submodules For {moduleName} - {type(e).__name__}: {e}\n", module="submodule-init", printTb=not isinstance(e, InitError))
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="submodule-init")
                Logger.warn(f"Skipping Module {moduleName}?", module="submodule-init")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {moduleName} From Loader!", module="submodule-init")
                if moduleName in self._modulePreloadDict:
                    del self._modulePreloadDict[moduleName]
                if moduleName in self._moduleDict:
                    del self._moduleDict[moduleName]

    # Intermediate Function to run Post-Initialization Scripts
    def _postInit(self):
        # Loop through all the submodules in the order of the sorted graph
        for moduleType in self._sortedModuleGraph:
            # Get the module from the module dict
            module = self._moduleDict[moduleType.NAME]
            # Get the module name
            moduleName = module.NAME
            try:
                Logger.debug(f"Running Post-Initialization for Module {moduleName}", module=f"{moduleName}-postinit")
                # Calling the Final Init function
                module.postInit()
            except FatalError as e:
                # Pass Down Fatal Error To Base Server
                raise e
            except Exception as e:
                # Handle Exception if Error Occurs
                self._errorList.append((moduleName, "Init-Final"))  # Module Loaded WITH Errors
                # If the Error is an Postinit Error (raised on purpose), Don't print out TB
                Logger.error(f"Error While Running Post-Initialization For {moduleName} - {type(e).__name__}: {e}\n", module="postinit", printTb=not isinstance(e, PostInitError))
                Logger.warn("!!! Module Errors May Cause Compatibility Issues And/Or Data Corruption !!!\n", module="postinit")
                Logger.warn(f"Skipping Module {moduleName}?", module="postinit")
                Logger.askConfirmation()
                # Remove Module
                Logger.warn(f"Removing Module {moduleName} From Loader!", module="postinit")
                if moduleName in self._modulePreloadDict:
                    del self._modulePreloadDict[moduleName]
                if moduleName in self._moduleDict:
                    del self._moduleDict[moduleName]

    # Registration. Called by Module Decorator
    def register(
        self,
        name: str,
        description: str,
        author: str,
        version: str,
        dependencies: Optional[list],
        module: Type[AbstractModule]
    ) -> Type[AbstractModule]:
        Logger.info(f"Discovered Module {name}.", module="module-import")
        Logger.debug(f"Registering Module {name}", module="module-import")

        # Format Name
        name = formatName(name)
        # Checking If Module Is Already In Modules List
        if name in self._modulePreloadDict.keys():
            raise InitRegisterError(f"Module {name} Has Already Been Registered!")
        # Check If Module Is Ignored
        if name in self._moduleIgnorelist:
            raise ModuleError("Module Is Ignored!")
        # Format Empty Dependencies
        if dependencies is None:
            dependencies = []
        # Checking If Core Is Required
        if self._ensureCore:
            if "core" not in [m.NAME for m in dependencies] and name != "core":
                dependencies.append(Dependency("core"))

        # Attach Values As Attribute
        module.NAME = name
        module.DESCRIPTION = description
        module.AUTHOR = author
        module.VERSION = version
        module.DEPENDENCIES = dependencies
        self._modulePreloadDict[name] = module

        return module

    # Generate a Pretty List of Modules
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Module", "Author", "Version"]
            # Loop Through All Modules And Add Value
            for _, module in self._moduleDict.items():
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
    def numModules(self) -> int:
        return len(self._moduleDict)

    # Function To Get Module Object From Module Name
    def getModule(self, module: str) -> AbstractModule:
        return self._moduleDict[module]

    # Handles _ModuleManager["item"]
    def __getitem__(self, *args, **kwargs) -> AbstractModule:
        return self.getModule(*args, **kwargs)

    # Handles _ModuleManager.item
    def __getattr__(self, *args, **kwargs) -> AbstractModule:
        return self.getModule(*args, **kwargs)


# Dependency Object
class Dependency:
    # Base Init - Main Data
    def __init__(self, name: str, version: Optional[str] = None):
        # User Defined Values
        self.NAME = formatName(name)
        self.VERSION = version
        # Reference To The Module Class - Handled By Init Dependencies
        self.MODULE = None

    # Implement Iter to Support Unpacking
    def __iter__(self):
        return iter((self.NAME, self.VERSION))

    # Format String
    def __str__(self) -> str:
        return f"<Name: {self.NAME}, Version: {self.VERSION}>"

    # Actions when Printing Class
    def __repr__(self) -> str:
        return self.__str__()


# Module Registration Decorator
# Used In @Module
def Module(
    name: str,
    description: str,
    author: str,
    version: str,
    dependencies: Optional[list] = None
):
    def internal(cls):
        ModuleManager.register(name, description, author, version, dependencies, cls)
        return cls
    return internal


# Global Function to Register Submodules
# Called by @ Decorators Handlers
# Returns function as per Python Spec
def Submodule(submodule: AbstractManager, name: str, description: Optional[str] = None, version: Optional[str] = None, override: bool = False):
    def internal(cls):
        Logger.verbose(f"Registered {submodule.NAME} {name} version {version}", module="submodule-import")

        # Set Class Variables
        cls.NAME = name
        cls.DESCRIPTION = description
        cls.VERSION = version
        cls.OVERRIDE = override
        cls.MANAGER = submodule

        # Set Obsidian Submodule to True -> Notifies Init that This Class IS a Submodule
        cls.obsidian_submodule = True

        # Return cls Obj for Decorator
        return cls
    return internal


# Method Override Decorator - Provides dynamic run-time method overriding
# Used In @Override
def Override(
    target: Callable,
    abstract: bool = False  # Allows for modifying abstract methods (Removes Warning)
):
    def internal(destination: Callable):
        # Because when someone overrides a method multiple times,
        # the parent class and (original) class name gets destroyed and lost.
        # _OBSIDIAN_OVERRIDE_CACHE saves those two values the first time it gets overridden.
        # And every subsequent time, it just returns the cached values.
        Logger.debug(f"Overriding Method {target} with {destination}", module="dynamic-method-override")

        # Check if the attribute is set
        if not hasattr(target, "_OBSIDIAN_OVERRIDE_CACHE"):
            Logger.debug("First time overriding method. Getting name and parent", module="dynamic-method-override")
            # Get the name and parent class of the function to override
            funcName = target.__name__
            parentClass = getMethodParentClass(target)
            Logger.debug(f"Method {funcName} has Parent Class: {parentClass}", module="dynamic-method-override")

            # If no parent class is found, return error
            if not parentClass:
                # Key Note: Overriding functions that are not in class
                # are not supported because imports are absolute not relative,
                # meaning any changes are not propagated to the original function.
                raise InitError(f"Method {funcName} is not overridable. (No Parent Class Found!)")

            # Check if parent class is an abstract class (Ignore if abstract flag is set)
            if parentClass in [m.SUBMODULE for m in MANAGERS_LIST] and not abstract:
                Logger.warn(f"Caution! {destination.__name__} is trying to override an abstract module {parentClass}!", module="dynamic-method-override")
                Logger.warn("This could cause unintended side effects!", module="dynamic-method-override")
                Logger.askConfirmation()
        else:
            Logger.debug("Override Cache Found! Using Cached Information", module="dynamic-method-override")
            # Grab information out of cache
            funcName, parentClass = target._OBSIDIAN_OVERRIDE_CACHE
            Logger.debug(f"Method {funcName} has Parent Class: {parentClass}", module="dynamic-method-override")

        # Define method to override
        # A lambda is created so that the old (target) method can be passed in
        overriddenMethod: Callable[[Any, Any], Any] = lambda *args, **kwargs: destination(target, *args, **kwargs)

        # Save the new function name and parent class to Override Cache
        overriddenMethod._OBSIDIAN_OVERRIDE_CACHE = (funcName, parentClass)

        # Override method in parent class to the new method
        setattr(parentClass, funcName, overriddenMethod)
        Logger.debug(f"Saved {overriddenMethod} to {parentClass}", module="dynamic-method-override")

        return destination
    return internal


# Inject Method Decorator. Used to dynamically add new methods to classes at runtime
# Used In @InjectMethod
def InjectMethod(
    target: Type[object]
):
    def internal(destination: Callable):
        # Save name of target class and destination function
        targetName = target.__name__
        destName = destination.__name__
        Logger.debug(f"Injecting Method {destName} into class {targetName} ({target})", module="dynamic-method-inject")

        # Check if if function of name target already exists
        if hasattr(target, destName):
            # Method registered under the same name
            conflict = getattr(target, destName)
            # Return error to user
            Logger.error(f"Class {targetName} already contains method of name {destName} ({conflict})", module="dynamic-method-inject")
            Logger.error("This could be because two modules are injecting a function of the same name or that the author meant to use @Override", module="dynamic-method-inject")
            raise InitError(f"Method {destName} already exists in class {targetName}")

        # Adding method to destination class
        setattr(target, destName, destination)
        Logger.debug(f"Added {destName} to {targetName}", module="dynamic-method-inject")

    return internal


# Helper method to get parent class of method
# Hybrid code by @Yoel http://stackoverflow.com/a/25959545 and @Stewori https://github.com/Stewori/pytypes
# This code is heavily shaky, so expect some bugs! But it should work for most common use cases.
def getMethodParentClass(function: Callable):
    Logger.verbose(f"Getting parent class for method {function}", module="get-method-parent-class")
    # After this point, I have little idea what it does...
    cls = getattr(inspect.getmodule(function), function.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0], None)
    if cls is None:
        clsNames = function.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0].split('.')
        cls = inspect.getmodule(function)
        for cls_name in clsNames:
            cls = getattr(cls, cls_name)
    if isinstance(cls, type):
        return cls
    return getattr(function, '__objclass__', None)  # handle special descriptor objects


# Creates Global ModuleManager As Singleton
ModuleManager = _ModuleManager()
# Adds Alias To ModuleManager
Modules = ModuleManager
