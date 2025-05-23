from __future__ import annotations

from typing import Type, TYPE_CHECKING
from collections import namedtuple

from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger
from obsidian.errors import CPEError, FatalError

if TYPE_CHECKING:
    from obsidian.module import AbstractModule


# Define new type for extension classes
CPEExtension = namedtuple("CPEExtension", ["name", "version"])


# CPE (Classic Protocol Extension) Registration Decorator
# Used In @CPE
def CPE(
    extName: str,
    extVersion: int,
    cpeOnly: bool = True
):
    def internal(cls):
        CPEModuleManager.registerCPE(extName, extVersion, cpeOnly, cls)
        return cls
    return internal


# Internal CPE (Classic Protocol Extension) Module Manager Singleton
# This does not extend ModuleManager as the rest, as it works slightly differently
# This ONLY Handles the initialization and allocation of CPE Extensions during Module Initialization
# This does NOT handle the usage of CPE Extensions during the server runtime
class _CPEModuleManager():
    def __init__(self):
        # List of modules (by type) and the CPE Extension they implement (ExtName, ExtVersion)
        self._cpeExtensions: dict[Type[AbstractModule], CPEExtension] = {}
        self._cpeSkipList: set[Type[AbstractModule]] = set()  # List of modules to skip if CPE is disabled

    # CPE Registration. Called by CPE Decorator
    def registerCPE(
        self,
        extName: str,
        extVersion: int,
        cpeOnly: bool,
        module: Type[AbstractModule]
    ) -> Type[AbstractModule]:
        Logger.info(f"Module {module.__name__} implements CPE Extension {extName} version {extVersion}.", module="module-import")

        # Check if module already implements a CPE
        if module in self._cpeExtensions:
            raise CPEError(f"Module {module.__name__} already implements CPE Extension {self._cpeExtensions[module].name} version {self._cpeExtensions[module].version}.")

        # Add CPE Extension to list
        self._cpeExtensions[module] = CPEExtension(extName, extVersion)

        # Check if module should be skipped if CPE support is disabled
        if cpeOnly:
            self._cpeSkipList.add(module)

        return module

    # Returns True if module implements CPE
    def hasCPE(self, module: Type[AbstractModule]) -> bool:
        return module in self._cpeExtensions

    # Returns True if module should be skipped if CPE support is disabled
    def shouldSkip(self, module: Type[AbstractModule]) -> bool:
        return module in self._cpeSkipList

    # Returns CPE Extension Name and Version for module
    def getCPE(self, module: Type[AbstractModule]) -> CPEExtension:
        if not self.hasCPE(module):
            raise CPEError(f"Module {module.__name__} does not implement a CPE Extension.")
        return self._cpeExtensions[module]

    # Returns True if there is a naming conflict with the given CPE Extension
    def hasCPENameConflict(self, checkModule: Type[AbstractModule]) -> bool:
        moduleCpeName = self.getCPE(checkModule).name
        for module, (extName, _) in self._cpeExtensions.items():
            # Ignore self
            if module == checkModule:
                continue

            if extName == moduleCpeName:
                return True
        return False

    # Generate a Pretty List of Modules
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Extension", "Version", "Implementation"]
            # Loop Through All CPE's And Add Value
            for module, (extName, extVersion) in self._cpeExtensions.items():
                # Add Row To Table
                table.add_row([extName, extVersion, module.NAME])
            return table
        except FatalError as e:
            # Pass Down Fatal Error To Base Server
            raise e
            return None
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")
            return None

    # Property Method To Get Number Of CPE Extensions
    @property
    def numCPE(self) -> int:
        return len(self._cpeExtensions)

    # Get Number Of CPE Extensions
    def __len__(self) -> int:
        return len(self._cpeExtensions)

    # Check if cpe exists
    def __contains__(self, cpe: str) -> bool:
        return cpe in self._cpeExtensions


# Creates Global CPEModuleManager As Singleton
CPEModuleManager = _CPEModuleManager()
