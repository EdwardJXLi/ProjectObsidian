from __future__ import annotations

from typing import Type, Optional, List
from dataclasses import dataclass, field
import inspect

from obsidian.module import AbstractModule
from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger
from obsidian.constants import (
    InitRegisterError,
    CommandError,
    FatalError
)


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
    ACTIVATORS: List[str] = field(default_factory=list)
    # Optional Values Defined In Module Decorator
    DESCRIPTION: str = ""
    VERSION: str = ""
    # Mandatory Values Defined During Module Initialization
    MODULE: Optional[AbstractModule] = None


# Command Utils

# Take Parameter Info + Argument Info To Automatically Convert Types
def _convertArgs(name, param, arg):
    Logger.verbose(f"Transforming Argument Data For Argument {name}", module="command")

    if param.annotation == inspect._empty:  # type: ignore
        return arg

    try:
        return param.annotation(arg)
    except ValueError:
        raise CommandError(f"Argument '{name}' Expected {param.annotation.__name__} But Got '{type(arg).__name__}'")


# Parse Command Argument Into Args and KWArgs In Accordance To Command Information
def _parseArgs(command, data: list):
    # This entire section is inspired by Discord.py 's Aprroach To Message Parsing and Handing
    # TODO: IGNORE_EXTRA, REST_IS_RAW, REQUIRE_VAR_POSITIONAL
    Logger.debug(f"Parsing Command Arguments {data} For Command {command.NAME}", module="command")
    # Define Important Vars
    args = []
    kwargs = {}
    # Extract Parameters From Execute Function
    params = inspect.signature(command.execute).parameters
    # Create Iterators To Parse Through Params and Data
    paramsIter = iter(params.items())
    dataIter = iter(data)

    # Parse Out The 'ctx' parameter
    try:
        next(paramsIter)
    except StopIteration:
        # InitRegisterError Because Command Was Improperly Formed + We WAnt To Skip The Player Error
        raise InitRegisterError(f"Command {command.NAME} Is Missing Parameter 'ctx'")

    # Loop Through Rest Of Iterators To Parse Data
    for name, param in paramsIter:
        # Check Parameter Type To Determing Parsing Method
        # -> Positional Methods (AKA POSITIONAL_OR_KEYWORD)
        # -> Keyword Only Methods (AKA KEYWORD_ONLY)
        # -> Positional "Rest" Methods (AKA VAR_POSITIONAL)

        if param.kind == param.POSITIONAL_OR_KEYWORD:
            # Parse as Normal Keyword
            try:
                # Convert Type
                transformed = _convertArgs(name, param, next(dataIter))
                args.append(transformed)
            except StopIteration:
                # Not Enough Data, Check If Error Or Use Default Value
                if param.default == inspect._empty:  # type: ignore
                    raise CommandError(f"Command {command.NAME} Expected Field '{name}' But Got Nothing")
                else:
                    args.append(param.default)

        elif param.kind == param.KEYWORD_ONLY:
            # KWarg Only Params Mean "Consume Rest"
            rest = []
            for value in dataIter:
                rest.append(value)

            # If Empty, Check If Default Value Was Requested
            if rest == []:
                if param.default == inspect._empty:  # type: ignore
                    raise CommandError(f"Command {command.NAME} Expected Field '{name}' But Got Nothing")
                else:
                    kwargs[name] = param.default
            else:
                # Join and Convert
                joinedRest = " ".join(rest)
                kwargs[name] = _convertArgs(name, param, joinedRest)
            # End of loop. Ignore rest
            break

        elif param.kind == param.VAR_POSITIONAL:
            # Var Positional means to just append all extra values to the end of the function
            for value in dataIter:
                transformed = _convertArgs(name, param, value)
                args.append(transformed)

    # At the end, if there were extra values, give error
    try:
        next(dataIter)
        raise CommandError(f"Too Many Arguments Passed Into Command {command.NAME}")
    except StopIteration:
        return args, kwargs


# Internal Command Manager Singleton
class _CommandManager:
    def __init__(self):
        # Creates List Of Commands That Has The Command Name As Keys
        self._command_list = dict()
        # Create Cache Of Activator to Obj
        self._activators = dict()

    # Registration. Called by Command Decorator
    def register(self, name: str, activators: Optional[list], description: str, version: str, command: Type[AbstractCommand], module):
        Logger.debug(f"Registering Command {name} From Module {module.NAME}", module="init-" + module.NAME)
        obj = command()  # type: ignore    # Create Object
        # Checking If Command Name Is Already In Commands List
        if name in self._command_list.keys():
            raise InitRegisterError(f"Command {name} Has Already Been Registered!")

        # Setting Activators To Default If None
        if activators is None:
            Logger.warn(f"Command {name} Was Registered Without Any Activators. Using Name As Command Activator.", module="init-" + module.NAME)
            activators = [name.lower()]
        # Add Activators To Command Cache
        Logger.debug(f"Adding Activators {activators} To Activator Cache", module="init-" + module.NAME)
        for activator in activators:
            Logger.verbose(f"Adding Activator {activator}", module="init-" + module.NAME)
            # If Activator Already Exists, Error
            if activator not in self._activators:
                self._activators[activator] = obj
            else:
                raise InitRegisterError(f"Another Command Has Already Registered Command Activator {activator}")

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

    # FUnction To Get Command Object From Command Name
    def getCommandFromName(self, name):
        if name in self._activators.keys():
            return self._activators[name]
        else:
            raise CommandError(f"Unknown Command {name}")

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
