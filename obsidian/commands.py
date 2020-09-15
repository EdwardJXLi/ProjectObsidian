from __future__ import annotations

from typing import Type, Optional
from dataclasses import dataclass

from obsidian.module import AbstractModule
from obsidian.utils.ptl import PrettyTableLite
from obsidian.constants import InitRegisterError, FatalError
from obsidian.log import Logger


# Commands Decorator
# Used In @Command
def Command(name: str, activators: Optional[list] = None, description: str = None, version: str = None):
    def internal(cls):
        cls.obsidian_command = dict()
        cls.obsidian_command["name"] = name
        cls.obsidian_command["activators"] = activators
        cls.obsidian_command["description"] = description
        cls.obsidian_command["version"] = version
        cls.obsidian_command["command"] = cls
        return cls
    return internal


# Command Skeleton
@dataclass
class AbstractCommand:
    # Mandatory Values Defined In Packet Init
    # Mandatory Values Defined In Module Decorator
    NAME: str = ""
    ACTIVATORS: str = ""
    # Optional Values Defined In Module Decorator
    DESCRIPTION: str = ""
    VERSION: str = ""
    # Mandatory Values Defined During Module Initialization
    MODULE: Optional[AbstractModule] = None


# Internal Command Manager Singleton
class _CommandManager:
    def __init__(self):
        # Creates List Of Commands That Has The Command Name As Keys
        self._command_list = dict()

    # Registration. Called by Command Decorator
    def register(self, name: str, activators: Optional[list], description: str, version: str, command: Type[AbstractCommand], module):
        Logger.debug(f"Registering Command {name} From Module {module.NAME}", module="init-" + module.NAME)
        obj = command()  # type: ignore    # Create Object
        # Checking If Command Name Is Already In Commands List
        if name in self._command_list.keys():
            raise InitRegisterError(f"Command {name} Has Already Been Registered!")
        # Setting Activators To Default If None
        if activators is None:
            activators = [name.lower()]
        # Attach Name, Direction, and Module As Attribute
        obj.NAME = name
        obj.ACTIVATORS = activators
        obj.DESCRIPTION = description
        obj.VERSION = version
        obj.MODULE = module
        self._command_list[name] = obj

    # Generate a Pretty List of Commands
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Command", "Activators", "Version", "Module"]
            # Loop Through All Commands And Add Value
            for _, command in self._command_list.items():
                # Add Row To Table
                table.add_row([command.NAME, command.ACTIVATORS, command.VERSION, command.MODULE.NAME])
            return table
        except FatalError as e:
            # Pass Down Fatal Error To Base Server
            raise e
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

    # Property Method To Get Number Of Commands
    @property
    def numCommands(self):
        return len(self._command_list)

    # Handles _CommandManager["item"]
    def __getitem__(self, command: str):
        return self._command_list[command]

    # Handles _CommandManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Creates Global CommandManager As Singleton
CommandManager = _CommandManager()
# Adds Alias To CommandManager
Commands = CommandManager
