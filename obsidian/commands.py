from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.player import Player

from typing import Dict, Type, List
from dataclasses import dataclass, field
import inspect

from obsidian.module import format_name, Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger
from obsidian.constants import (
    InitRegisterError,
    CommandError,
    FatalError
)


# Command Decorator
# Used In @Command
def Command(*args, **kwargs):
    return Submodule(CommandManager, *args, **kwargs)


# Command Skeleton
@dataclass
class AbstractCommand(AbstractSubmodule):
    # TODO: Maybe enforce this as a tuple?
    ACTIVATORS: List[str] = field(default_factory=list)
    OP: bool = False

    async def execute(self, ctx: Player):
        raise NotImplementedError("Command Hander Not Implemented")


# == Command Utils ==

# Take Parameter Info + Argument Info To Automatically Convert Types
def _convertArgs(name: str, param: inspect.Parameter, arg: str):
    Logger.verbose(f"Transforming Argument Data For Argument {name}", module="command")

    # If There Is No Type To Convert, Ignore
    if param.annotation == inspect._empty:
        return arg

    # Try to parse, if error, cancel
    try:
        return param.annotation(arg)
    except ValueError:
        raise CommandError(f"Argument '{name}' Expected {param.annotation.__name__} But Got '{type(arg).__name__}'")


# Parse Command Argument Into Args and KWArgs In Accordance To Command Information
def _parseArgs(command: AbstractCommand, data: list):
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
        # InitRegisterError Because Command Was Improperly Formed + We Want To Skip The Player Error
        raise InitRegisterError(f"Command {command.NAME} Is Missing Parameter 'ctx'")

    # Loop Through Rest Of Iterators To Parse Data
    for name, param in paramsIter:
        Logger.verbose(f"Parsing Parameter {name}", module="command")
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
                if param.default == inspect._empty:
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
                if param.default == inspect._empty:
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
        raise CommandError(f"Too Many Arguments Passed Into Command '{command.NAME}'")
    except StopIteration:
        return args, kwargs


# Internal Command Manager Singleton
class _CommandManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("Command", AbstractCommand)

        # Creates List Of Commands That Has The Command Name As Keys
        self._command_list: Dict[str, AbstractCommand] = dict()
        # Create Cache Of Activator to Obj
        self._activators: Dict[str, AbstractCommand] = dict()

    # Registration. Called by Command Decorator
    def register(self, commandClass: Type[AbstractCommand], module: AbstractModule):
        Logger.debug(f"Registering Command {commandClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        command: AbstractCommand = super()._initSubmodule(commandClass, module)

        # Handling Special Cases if OVERRIDE is Set
        if command.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if command.NAME not in self._command_list.keys():
                Logger.warn(f"Command {command.NAME}  From Module {command.MODULE.NAME} Is Trying To Override A Command That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"Command {command.NAME} Is Overriding Command {self._command_list[command.NAME].NAME}", module=f"{module.NAME}-submodule-init")
                # Un-registering All Activators for the Command Being Overwritten. Prevents Issues!
                Logger.debug(f"Un-registering Activators for Command {self._command_list[command.NAME].NAME}", module=f"{module.NAME}-submodule-init")
                for activator in list(self._command_list[command.NAME].ACTIVATORS):
                    # Deleting from Cache
                    del self._activators[activator]

        # Checking If Command Name Is Already In Commands List
        # Ignoring if OVERRIDE is set
        if command.NAME in self._command_list.keys() and not command.OVERRIDE:
            raise InitRegisterError(f"Command {command.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Setting Activators To Default If None
        if command.ACTIVATORS is None:
            command.ACTIVATORS = []
        if len(command.ACTIVATORS) == 0:
            Logger.warn(f"Command {command.NAME} Was Registered Without Any Activators. Using Name As Command Activator.", module=f"{module.NAME}-submodule-init")
            command.ACTIVATORS = [format_name(command.NAME)]
        # Add Activators To Command Cache
        Logger.debug(f"Adding Activators {command.ACTIVATORS} To Activator Cache", module=f"{module.NAME}-submodule-init")
        for activator in command.ACTIVATORS:
            Logger.verbose(f"Adding Activator {activator}", module=f"{module.NAME}-submodule-init")
            # If Activator Already Exists, Error
            if activator not in self._activators:
                self._activators[activator] = command
            else:
                raise InitRegisterError(f"Another Command Has Already Registered Command Activator {activator}")

        # Add Command to Commands List
        self._command_list[command.NAME] = command

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
    def getCommandFromName(self, name: str):
        if name in self._activators.keys():
            return self._activators[name]
        else:
            raise CommandError(f"Unknown Command '{name}'")

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
