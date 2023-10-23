from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Type, Optional, Generic
from pathlib import Path
import importlib
import pkgutil
import fnmatch

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
    SOFT_DEPENDENCIES: list
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

        # Helper method to load and initialize a discovered module
        # Takes in the module name as an absolute module path
        # i.e. obsidian.modules.core or obsidian.modules.lib.nbtlib
        def loadModule(moduleName: str):
            # Check if module is part of the moduleIgnoreList.
            # For the moduleIgnoreList, we match 3 cases:
            # 1. moduleName is the same as the ignorelist entry
            # 2. the stem of the moduleName is the same as the ignorelist entry
            # 3. the path of the moduleName (converted from dot to slash notation) matches the ignorelist wildcard
            #    (i.e. obsidian.modules.lib.*)
            for ignore in self._moduleIgnorelist:
                if moduleName == ignore or moduleName.split(".")[-1] == ignore or fnmatch.fnmatch(moduleName.replace(".", "/"), ignore.replace(".", "/")):
                    Logger.verbose(f"Module {moduleName} In Ignore List. Skipping!", module="module-import")
                    return

            try:
                Logger.verbose(f"Module {moduleName} Not In Ignore List. Adding!", module="module-import")
                # Import Module
                _module = importlib.import_module(moduleName)
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

        # Helper function to recursively iterate through a directory for modules
        # If folder contains __init__.py, assume the entire directory is a single module and load it as such
        # Else, load each python file individually and continue iterating through subfolders
        def recursiveModuleLoader(path: Path):
            Logger.debug(f"Recursively Loading Modules From {path}", module="module-import")
            # Get the relative path of the module from the server path in dot notation
            relative_path = path.relative_to(Path(SERVER_PATH, MODULES_FOLDER))

            # Get the absolute import path of the module
            # i.e.
            if path == Path(SERVER_PATH, MODULES_FOLDER):
                abs_import = MODULES_IMPORT
            else:
                abs_import = MODULES_IMPORT + "." + relative_path.as_posix().replace("/", ".")

            # Check if the relative path matches one in the ignore list.
            # i.e obsidian.modules.lib.* will match obsidian.modules.lib.nbtlib
            # If so, break out
            for ignore in self._moduleIgnorelist:
                if fnmatch.fnmatch(relative_path.as_posix(), ignore.replace(".", "/")):
                    Logger.verbose(f"Directory {relative_path.as_posix()} In Ignore List. Skipping!", module="module-import")
                    return

            # If a .obignore file exists in the folder, ignore the entire folder
            if Path(path, ".obignore").exists():
                Logger.verbose(f"Directory {relative_path.as_posix()} has '.obignore' file. Skipping!", module="module-import")
                return
            # If __init__.py is defined in the folder, treat the entire directory as the module
            elif Path(path, "__init__.py").exists():
                Logger.debug(f"Detected __init__.py in {path}. Treating as module.", module="module-import")
                # abs_import is already in the correct format to load the module
                loadModule(abs_import)
            # Treat the directory as a collection of modules
            else:
                for _, moduleName, _ in pkgutil.iter_modules(
                    path=[str(path)],
                    prefix=abs_import + "."
                ):
                    # moduleName is already formatted with abs_import, as is the point of the prefix parameter
                    loadModule(moduleName)

                # Recursively iterate through all sub-folders of current directory
                for folder in path.iterdir():
                    if folder.is_dir():
                        recursiveModuleLoader(folder)

        # Begin recursive module discovery on the initial modules path
        recursiveModuleLoader(Path(SERVER_PATH, MODULES_FOLDER))

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
            # If CPE is supported by server, check for CPE naming conflicts
            Logger.debug("CPE Support Enabled", module="verify-cpe")
            Logger.debug("Checking for CPE naming conflicts", module="verify-cpe")
            for moduleName, moduleType in list(self._modulePreloadDict.items()):
                try:
                    # Check CPE Support
                    Logger.debug(f"Checking CPE Support for Module {moduleName}", module="verify-cpe")
                    if CPEModuleManager.hasCPE(moduleType):
                        Logger.debug(f"Module {moduleName} Implements a CPE Extension.", module="verify-cpe")

                        # Check if there is a naming conflict
                        if CPEModuleManager.hasCPENameConflict(moduleType):
                            raise CPEError(f"Module {moduleName} has a CPE Name Conflict. Please Rename the Module or the CPE Extension.")
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
        else:
            # If CPE is not supported by server, check for CPE support in modules
            Logger.debug("CPE Support Disabled. Verifying CPE support.", module="verify-cpe")
            for moduleName, moduleType in list(self._modulePreloadDict.items()):
                try:
                    # Check CPE Support
                    Logger.debug(f"Checking CPE Support for Module {moduleName}", module="verify-cpe")
                    if CPEModuleManager.hasCPE(moduleType):
                        Logger.debug(f"Module {moduleName} Implements a CPE Extension.", module="verify-cpe")

                        # Check if CPE module meets the conditions for skip
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
                            Logger.verbose(f"Dependency {dependency} Satisfied (Version Check Not Specified)!", module="module-resolve")
                            pass  # No Version Check Needed
                        elif depVer == self._modulePreloadDict[dependency.NAME].VERSION:
                            Logger.verbose(f"Dependency {dependency} Satisfied!", module="module-resolve")
                            pass
                        else:
                            raise DependencyError(f"Dependency '{dependency}' Has Unmatched Version! (Requirement: {depVer} | Has: {self._modulePreloadDict[dependency.NAME].VERSION})")
                        # If All Passes, Link Module Class
                        dependency.MODULE = self._modulePreloadDict[dependency.NAME]
                    else:
                        raise DependencyError(f"Dependency '{dependency}' Not Found!")

                Logger.debug(f"Checking Soft/Optional Dependencies for Module {moduleName}", module="module-resolve")
                # Keep track of dependencies to remove
                invalid_soft_dependencies = []

                # Loop through all soft dependencies, check type, then check if exists
                for dependency in moduleType.SOFT_DEPENDENCIES:
                    # Get Variables
                    depName = dependency.NAME
                    depVer = dependency.VERSION
                    Logger.verbose(f"Checking if Soft/Optional Dependency {depName} Exists", module="module-resolve")
                    # Check if Soft Dependency is "Loaded"
                    if depName in self._modulePreloadDict.keys():
                        # Check if Version should be checked
                        if depVer is None:
                            Logger.verbose(f"Soft/Optional Dependency {dependency} Satisfied (Version Check Not Specified)!", module="module-resolve")
                            pass  # No Version Check Needed
                        elif depVer == self._modulePreloadDict[dependency.NAME].VERSION:
                            Logger.verbose(f"Soft/Optional Dependency {dependency} Satisfied!", module="module-resolve")
                            pass
                        else:
                            Logger.warn(f"Soft/Optional Dependency '{dependency}' Has Unmatched Version! (Requirement: {depVer} | Has: {self._modulePreloadDict[dependency.NAME].VERSION})", module="module-resolve")
                        # If All Passes, Link Module Class
                        dependency.MODULE = self._modulePreloadDict[dependency.NAME]
                    else:
                        Logger.info(f"Soft/Optional Dependency '{dependency}' Not Found! Continuing...", module="module-resolve")
                        invalid_soft_dependencies.append(dependency)

                # Remove all invalid soft dependencies
                if invalid_soft_dependencies:
                    Logger.debug(f"Removing Invalid Soft/Optional Dependencies {invalid_soft_dependencies} From Module {moduleName}", module="module-resolve")
                    for dependency in invalid_soft_dependencies:
                        moduleType.SOFT_DEPENDENCIES.remove(dependency)

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

            Logger.verbose(f"Current Modules Has Dependencies {current.DEPENDENCIES} and Soft Dependencies {current.SOFT_DEPENDENCIES}", module="cycle-check")
            # Run DFS through All Dependencies
            for dependency in current.DEPENDENCIES + current.SOFT_DEPENDENCIES:
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
            Logger.verbose(f"Attempting Topological Sort on {module.NAME}'s Dependencies {module.DEPENDENCIES} and Soft Dependencies {module.SOFT_DEPENDENCIES}", module="topological-sort")
            for dependency in module.DEPENDENCIES + module.SOFT_DEPENDENCIES:
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
                    module.DEPENDENCIES,
                    module.SOFT_DEPENDENCIES
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
        soft_dependencies: Optional[list],
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
        if soft_dependencies is None:
            soft_dependencies = []
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
        module.SOFT_DEPENDENCIES = soft_dependencies
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

    # Function To Get Module Object From Module Name
    def getModule(self, module: str, ignoreCase: bool = True) -> AbstractModule:
        if ignoreCase:
            for mName, mObject in self._moduleDict.items():
                if mName.lower() == module.lower():
                    return mObject
            else:
                raise KeyError(module)
        else:
            return self._moduleDict[formatName(module)]

    # Handles _ModuleManager["item"]
    def __getitem__(self, *args, **kwargs) -> AbstractModule:
        return self.getModule(*args, **kwargs)

    # Handles _ModuleManager.item
    def __getattr__(self, *args, **kwargs) -> AbstractModule:
        return self.getModule(*args, **kwargs)

    # Get Number Of Modules
    def __len__(self) -> int:
        return len(self._moduleDict)

    # Check if module exists
    def __contains__(self, item: str) -> bool:
        return item in self._moduleDict


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
    dependencies: Optional[list] = None,
    soft_dependencies: Optional[list] = None,
):
    def internal(cls):
        ModuleManager.register(name, description, author, version, dependencies, soft_dependencies, cls)
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


# Creates Global ModuleManager As Singleton
ModuleManager = _ModuleManager()
# Adds Alias To ModuleManager
Modules = ModuleManager
