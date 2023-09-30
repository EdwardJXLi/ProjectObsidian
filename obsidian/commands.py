from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.player import Player
    from obsidian.server import Server

from typing import Any, Union, Type, Generic, get_args, get_origin
from dataclasses import dataclass, field
from types import UnionType, GenericAlias, NoneType
import inspect

from obsidian.module import Submodule, AbstractModule, AbstractSubmodule, AbstractManager
from obsidian.utils.ptl import PrettyTableLite
from obsidian.log import Logger
from obsidian.errors import (
    InitRegisterError,
    CommandError,
    ServerError,
    ConverterError,
)
from obsidian.types import formatName, T


# Command Decorator
# Used In @Command
def Command(*args, **kwargs):
    return Submodule(CommandManager, *args, **kwargs)


# Command Skeleton
@dataclass
class AbstractCommand(AbstractSubmodule[T], Generic[T]):
    # TODO: Maybe enforce this as a tuple?
    ACTIVATORS: list[str] = field(default_factory=list)
    OP: bool = False

    async def execute(self, ctx: Player, *args, **kwargs):
        raise NotImplementedError("Command Handler Not Implemented")

    @staticmethod
    def _convertArgument(_, argument: str) -> AbstractCommand:
        try:
            # Try to grab the command as a name first
            return CommandManager.getCommand(argument)
        except KeyError:
            try:
                # If failed, try to grab as an activator
                return CommandManager.getCommandFromActivator(argument.lower())
            except KeyError:
                # Raise error if command not found
                raise ConverterError(f"Command {argument} Not Found!")


# == Command Utils ==

def _typeToString(annotation) -> str:
    if annotation == inspect._empty:
        return "None"
    elif isinstance(annotation, str):
        return annotation
    elif isinstance(annotation, list):
        return f"[{', '.join([_typeToString(x) for x in annotation])}]"
    elif get_origin(annotation):
        if get_origin(annotation) is Union or get_origin(annotation) is UnionType:
            args = get_args(annotation)
            if NoneType in args:
                return f"optional[{' | '.join([_typeToString(a) for a in args if a is not NoneType])}]"
            else:
                return f"{' | '.join([_typeToString(a) for a in args])}"
        return f"{_typeToString(get_origin(annotation))}[{', '.join([_typeToString(arg) for arg in get_args(annotation)])}]"
    elif hasattr(annotation, "__name__"):
        return annotation.__name__
    else:
        Logger.warn(f"Unknown annotation type {annotation}", module="command")
        return "Unknown"


# Take Parameter Info + Argument Info To Automatically Convert Types
def _convertArgs(ctx: Server, name: str, param: inspect.Parameter, arg: Any):
    Logger.debug(f"Transforming Argument Data For Argument {name} with data '{arg}'", module="converter")

    # If There Is No Type To Convert, Ignore
    if param.annotation == inspect._empty:
        return arg

    # Try to parse, if error, cancel
    try:
        # Check if the type has an custom arg converter
        # This supports execute(self, ctx: Player, player2: Player)
        if hasattr(param.annotation, "_convertArgument") and callable(param.annotation._convertArgument):
            Logger.debug("Argument Type has _convertArgument. Using that to convert", module="converter")
            try:
                return param.annotation._convertArgument(ctx, arg)
            except ConverterError as e:
                raise CommandError(e)
        # Check if type is a generic class and a var positional argument. Special considerations for those cases.
        # This supports execute(self, ctx: Player, *args: Tuple[int])
        if isinstance(param.annotation, GenericAlias) and param.kind == param.VAR_POSITIONAL:
            Logger.debug("Argument Type is part of a VAR_POSITIONAL iterable. Converting based on base type", module="converter")
            nested_type = get_args(param.annotation)[0]  # Getting the first type. This may cause issues, but oh well.
            return _convertArgs(ctx, name, inspect.Parameter(param.name, param.kind, annotation=nested_type), arg)
        # Check if type is a union (also encapsulates optional types). If so, loop through all types and try to convert to them.
        # This supports execute(self, ctx: Player, arg1: int | str, arg2: Optional[Player])
        if get_origin(param.annotation) is Union or get_origin(param.annotation) is UnionType:
            Logger.debug("Argument Type is part of a Union. Attempting to convert to each type", module="converter")
            union_types = get_args(param.annotation)  # Getting the different types.
            # Try every type in order and check if it works
            for annotation in union_types:
                Logger.debug(f"Attempting to convert to type {annotation}", module="converter")
                # If the type is a None type, ignore for now...
                # This fixes some unexpected behavior with Optional s
                if annotation is NoneType:
                    Logger.debug("Argument Type is NoneType. Skipping", module="converter")
                    continue
                # Attempting to convert...
                try:
                    return _convertArgs(ctx, name, inspect.Parameter(param.name, param.kind, annotation=annotation), arg)
                except CommandError:
                    Logger.debug("Conversion Failed. Trying Next Type", module="converter")
                    pass
            # If none of the types work, raise an error
            raise CommandError(f"Arg '{name}' Expected {' or '.join([getattr(annotation, '__name__', 'Unknown') for annotation in union_types if annotation is not NoneType])} But Got '{type(arg).__name__}'")
        # Check if type is an "ignore type" -> Types that are not supported by the converter
        # Any is ignored, as any type is allowed. GenericAlias is allowed to python satisfy type checking LOL
        if param.annotation is Any or param.annotation is GenericAlias:
            Logger.debug("Argument Type is part of ignored types.", module="converter")
            return arg
        # Check if the type is a boolean, run special logic to convert it
        if param.annotation is bool:
            Logger.debug("Argument Type is a boolean. Attempting to convert", module="converter")
            if arg.lower() in ["true", "t", "yes", "y", "1"]:
                return True
            elif arg.lower() in ["false", "f", "no", "n", "0"]:
                return False
            else:
                raise CommandError(f"Arg '{name}' Expected {' or '.join(['True', 'False'])} But Got '{arg}'")
        # Check if the type is a string. If so, tell the developer that stringed types are not supported.
        if isinstance(param.annotation, str):
            # TODO: ONCE PEP 563 – Postponed Evaluation of Annotations (https://peps.python.org/pep-0563/) IS INTEGRATED,
            # NEED TO FIND A WAY TO MAKE ARGUMENT PARSING WORK WITH ONLY STRINGS!!!
            raise ServerError(
                f"Argument Type {name} is a string. This is not supported by the command parser!\n\n"
                "[IMPORTANT] Check if you have `from __future__ import annotations` added to the top of the file!\n"
                "If so, REMOVE IT! Modules do not support this feature yet (PEP 563 - Postponed Evaluation of Annotation)!\n"
            )

        # Transform the argument
        Logger.debug(f"Converting Argument of Type {param.annotation}", module="converter")
        transformed = param.annotation.__call__(arg)
        # Check if transformation is successful
        if isinstance(transformed, param.annotation):
            return transformed
        else:
            raise ConverterError(f"Unexpected Conversion. Expected {param.annotation} But Got {type(transformed)}")
    except ValueError:
        raise CommandError(f"Arg '{name}' Expected {getattr(param.annotation, '__name__', 'Unknown')} But Got '{type(arg).__name__}'")
    except TypeError:
        # Probably cant instantiate. Raise an error so it does not silently fail
        raise ConverterError(f"Cant instantiate type. {getattr(param.annotation, '__name__', 'Unknown')} Cannot Convert Types. Try adding a _convertArgument method to add custom conversions.")


# Parse Command Argument Into Args and KWArgs In Accordance To Command Information
def _parseArgs(ctx: Server, command: AbstractCommand, data: list):
    # This entire section is inspired by Discord.py 's Approach To Message Parsing and Handing
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
        # Check Parameter Type To Determining Parsing Method
        # -> Positional Methods (AKA POSITIONAL_OR_KEYWORD)
        # -> Keyword Only Methods (AKA KEYWORD_ONLY)
        # -> Positional "Rest" Methods (AKA VAR_POSITIONAL)

        if param.kind == param.POSITIONAL_OR_KEYWORD:
            Logger.debug("Parsing Parameter As Positional Or Keyword", module="command")
            # Parse as Normal Keyword
            try:
                # Convert Type
                transformed = _convertArgs(ctx, name, param, next(dataIter))
                args.append(transformed)
            except StopIteration:
                # Not Enough Data, Check If Error Or Use Default Value
                if param.default == inspect._empty:
                    raise CommandError(f"Expected Field '{name}' But Got Nothing")
                else:
                    args.append(param.default)

        elif param.kind == param.KEYWORD_ONLY:
            Logger.debug("Parsing Parameter As Keyword Only", module="command")
            # KWarg Only Params Mean "Consume Rest"
            rest = []
            for value in dataIter:
                rest.append(value)

            # If Empty, Check If Default Value Was Requested
            if rest == []:
                if param.default == inspect._empty:
                    raise CommandError(f"Expected Field '{name}' But Got Nothing")
                else:
                    kwargs[name] = param.default
            else:
                # Join and Convert
                joinedRest = " ".join(rest)
                kwargs[name] = _convertArgs(ctx, name, param, joinedRest)
            # End of loop. Ignore rest
            break

        elif param.kind == param.VAR_POSITIONAL:
            Logger.debug("Parsing Parameter As Var Positional", module="command")
            # Var Positional means to just append all extra values to the end of the function
            for value in dataIter:
                transformed = _convertArgs(ctx, name, param, value)
                args.append(transformed)

        else:
            raise ServerError(f"Unknown Parameter Type {param.kind}")

    # At the end, if there were extra values, give error
    try:
        next(dataIter)
        raise CommandError(f"Too Many Arguments! Expected: {len(params)-1} Got: {len(data)}")
    except StopIteration:
        return args, kwargs


# Internal Command Manager Singleton
class _CommandManager(AbstractManager):
    def __init__(self):
        # Initialize Overarching Manager Class
        super().__init__("Command", AbstractCommand)

        # Creates List Of Commands That Has The Command Name As Keys
        self._commandDict: dict[str, AbstractCommand] = dict()
        # Create Cache Of Activator to Obj
        self._activators: dict[str, AbstractCommand] = dict()

    # Registration. Called by Command Decorator
    def register(self, commandClass: Type[AbstractCommand], module: AbstractModule) -> AbstractCommand:
        Logger.debug(f"Registering Command {commandClass.NAME} From Module {module.NAME}", module=f"{module.NAME}-submodule-init")
        command: AbstractCommand = super()._initSubmodule(commandClass, module)

        # Check if the name has a space. If so, raise warning
        if " " in commandClass.NAME:
            Logger.warn(f"Command '{commandClass.NAME}' has white space in its name!", module=f"{module.NAME}-submodule-init")

        # Handling Special Cases if OVERRIDE is Set
        if command.OVERRIDE:
            # Check If Override Is Going To Do Anything
            # If Not, Warn
            if command.NAME not in self._commandDict.keys():
                Logger.warn(f"Command {command.NAME}  From Module {command.MODULE.NAME} Is Trying To Override A Command That Does Not Exist! If This Is An Accident, Remove The 'override' Flag.", module=f"{module.NAME}-submodule-init")
            else:
                Logger.debug(f"Command {command.NAME} Is Overriding Command {self._commandDict[command.NAME].NAME}", module=f"{module.NAME}-submodule-init")
                # Un-registering All Activators for the Command Being Overwritten. Prevents Issues!
                Logger.debug(f"Un-registering Activators for Command {self._commandDict[command.NAME].NAME}", module=f"{module.NAME}-submodule-init")
                for activator in list(self._commandDict[command.NAME].ACTIVATORS):
                    # Deleting from Cache
                    del self._activators[activator]

        # Checking If Command Name Is Already In Commands List
        # Ignoring if OVERRIDE is set
        if command.NAME in self._commandDict.keys() and not command.OVERRIDE:
            raise InitRegisterError(f"Command {command.NAME} Has Already Been Registered! If This Is Intentional, Set the 'override' Flag to True")

        # Setting Activators To Default If None
        if command.ACTIVATORS is None:
            command.ACTIVATORS = []
        if len(command.ACTIVATORS) <= 0:
            Logger.warn(f"Command {command.NAME} Was Registered Without Any Activators. Using Name As Command Activator.", module=f"{module.NAME}-submodule-init")
            command.ACTIVATORS = [formatName(command.NAME)]
        # Add Activators To Command Cache
        Logger.debug(f"Adding Activators {command.ACTIVATORS} To Activator Cache", module=f"{module.NAME}-submodule-init")
        for activator in command.ACTIVATORS:
            Logger.verbose(f"Adding Activator {activator}", module=f"{module.NAME}-submodule-init")
            # CHECK IF ACTIVATOR IS VALID
            # Checking If:
            # Activator is blank
            # Activator contains whitespace
            # Activator contains is just all number
            # Activator contains uppercase letters
            # Activator is not alphanumeric
            # This is so that /help knows if its referring to a page number or command
            if (activator == "") or (activator.strip() != activator) or (activator.isdecimal()) or (not activator.islower()) or (not activator.isalnum()):
                raise InitRegisterError(f"Command Activator '{activator}' for Command {command.NAME} Is Not Valid!")
            # If Activator Already Exists, Error
            if activator not in self._activators:
                self._activators[activator] = command
            else:
                raise InitRegisterError(f"Another Command Has Already Registered Command Activator {activator}")

        # Add Command to Commands List
        self._commandDict[command.NAME] = command

        return command

    # Generate a Pretty List of Commands
    def generateTable(self):
        try:
            table = PrettyTableLite()  # Create Pretty List Class

            table.field_names = ["Command", "Activators", "Version", "Module"]
            # Loop Through All Commands And Add Value
            for _, command in self._commandDict.items():
                # Add Row To Table
                table.add_row([command.NAME, command.ACTIVATORS, command.VERSION, command.MODULE.NAME])
            return table
        except Exception as e:
            Logger.error(f"Error While Printing Table - {type(e).__name__}: {e}", module="table")

    # FUnction To Get Command Object From Command Name
    def getCommandFromName(self, name: str) -> AbstractCommand:
        if name in self._activators.keys():
            return self._activators[name]
        else:
            raise CommandError(f"Unknown Command '{name}'")

    # Function To Get Command Object From Command Name
    def getCommand(self, command: str, ignoreCase: bool = True) -> AbstractCommand:
        if ignoreCase:
            for cName, cObject in self._commandDict.items():
                if cName.lower() == command.lower():
                    return cObject
            else:
                raise KeyError(command)
        else:
            return self._commandDict[command]

    # Function To Get Command Object From Command Name
    def getCommandFromActivator(self, command: str) -> AbstractCommand:
        return self._activators[command]

    # Handles _CommandManager["item"]
    def __getitem__(self, *args, **kwargs) -> AbstractCommand:
        return self.getCommand(*args, **kwargs)

    # Handles _CommandManager.item
    def __getattr__(self, *args, **kwargs) -> AbstractCommand:
        return self.getCommand(*args, **kwargs)

    # Get Number Of Commands
    def __len__(self) -> int:
        return len(self._commandDict)

    # Check if command exists
    def __contains__(self, command: str) -> bool:
        return command in self._commandDict


# Creates Global CommandManager As Singleton
CommandManager = _CommandManager()
# Adds Alias To CommandManager
Commands = CommandManager
