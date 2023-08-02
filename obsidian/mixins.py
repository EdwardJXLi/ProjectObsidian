from typing import Optional, Callable, Type, Any
from enum import Enum
import inspect

from obsidian.log import Logger
from obsidian.errors import MixinError
from obsidian.constants import MANAGERS_LIST


# Enums for @Inject
class InjectionPoint(Enum):
    BEFORE = "before"
    AFTER = "after"


# Helper function used by @Override, @Extend, and @Inject.
# Replaces one function in a class with another.
def _overrideMethod(target: Callable, destination: Callable, abstract: bool = False):
    # When a method gets overridden multiple times,
    # the parent class and (original) class name gets destroyed and lost.
    # __OBSIDIAN_OVERRIDE_CACHE__ saves those two values the first time it gets overridden.
    # And every subsequent time, it just returns the cached values.
    Logger.debug(f"(Internally) Overriding Method {target} with {destination}", module="dynamic-method-override")

    # Check if the attribute is set
    if not hasattr(target, "__OBSIDIAN_OVERRIDE_CACHE__"):
        Logger.debug("First time overriding method. Getting name and parent", module="dynamic-method-override")
        # Get the name and parent class of the function to override
        funcName = target.__name__
        parentClass = _getMethodParentClass(target)
        Logger.debug(f"Method {funcName} has Parent Class: {parentClass}", module="dynamic-method-override")

        # If no parent class is found, return error
        if not parentClass:
            # Key Note: Overriding functions that are not in class
            # are not supported because imports are absolute not relative,
            # meaning any changes are not propagated to the original function.
            raise MixinError(f"Method {funcName} is not overridable. (No Parent Class Found!)")

        # Check if parent class is an abstract class (Ignore if abstract flag is set)
        if parentClass in [m.SUBMODULE for m in MANAGERS_LIST] and not abstract:
            Logger.warn(f"Caution! {destination.__name__} is trying to override an abstract module {parentClass}!", module="dynamic-method-override")
            Logger.warn("This could cause unintended side effects!", module="dynamic-method-override")
            Logger.askConfirmation()
    else:
        Logger.debug("Override Cache Found! Using Cached Information", module="dynamic-method-override")
        # Grab information out of cache
        funcName, parentClass = target.__OBSIDIAN_OVERRIDE_CACHE__
        Logger.debug(f"Method {funcName} has Parent Class: {parentClass}", module="dynamic-method-override")

    # Define method to override
    # A lambda is created so that the old (target) method can be passed in
    overriddenMethod: Callable[[Any, Any], Any] = destination

    # Save the new function name and parent class to Override Cache
    overriddenMethod.__OBSIDIAN_OVERRIDE_CACHE__ = (funcName, parentClass)

    # Override method in parent class to the new method
    setattr(parentClass, funcName, overriddenMethod)
    Logger.debug(f"Saved {overriddenMethod} to {parentClass}", module="dynamic-method-override")


# Helper method to get parent class of method
# Hybrid code by @Yoel http://stackoverflow.com/a/25959545 and @Stewori https://github.com/Stewori/pytypes
# This code is heavily shaky, so expect some bugs! But it should work for most common use cases.
def _getMethodParentClass(function: Callable):
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


# Method Override Decorator - Provides dynamic run-time method overriding
# Used In @Override
def Override(
    target: Callable,
    passSuper: bool = False,  # passSuper allows for passing the original function as a parameter to the new function
    abstract: bool = False,  # Allows for modifying abstract methods (Removes Warning)
    additionalContext: Optional[dict[str, Any]] = None  # Allows for passing additional keyword fields to the new function
):
    def internal(destination: Callable):
        Logger.debug(f"Overriding Method {target.__name__} ({target}) with {destination.__name__}", module="dynamic-method-override")

        # Generate the additional contexts
        ctxArgs = dict()
        if additionalContext:
            ctxArgs.update(additionalContext)  # Add additional context if it exists
        if passSuper:
            ctxArgs.update({"_super": target})  # Add super if passSuper is set

        # Check if both the target and the destination are either both async or both non async
        if inspect.iscoroutinefunction(target) is False and inspect.iscoroutinefunction(destination) is True:
            raise MixinError(f"Cannot override non-async function {target.__name__} with async function {destination.__name__}!")
        elif inspect.iscoroutinefunction(target) is True and inspect.iscoroutinefunction(destination) is False:
            raise MixinError(f"Cannot override async function {target.__name__} with non-async function {destination.__name__}!")
        # If both target and destination are async, implement the async override
        elif inspect.iscoroutinefunction(target) is True and inspect.iscoroutinefunction(destination) is True:
            async def _asyncoverride(*args, **kwargs):
                return await destination(*args, **kwargs, **ctxArgs)

            # Spoof the signature of the original function
            _asyncoverride.__signature__ = inspect.signature(target)

            _overrideMethod(
                target,
                _asyncoverride,
                abstract=abstract
            )
        # Both target and destination are non-async, implement the non-async override
        else:
            # Create the new override function
            def _override(*args, **kwargs):
                return destination(*args, **kwargs, **ctxArgs)

            # Spoof the signature of the original function
            _override.__signature__ = inspect.signature(target)

            _overrideMethod(
                target,
                _override,
                abstract=abstract
            )

        return destination
    return internal


# Method Inject Decorator - Provides dynamic run-time method injection at various points in the function
# Used In @Inject
def Inject(
    target: Callable,
    at: InjectionPoint = InjectionPoint.AFTER,
    passResult: bool = False,  # passResult allows for passing the output of the original function as a parameter to the new function
    abstract: bool = False,  # Allows for modifying abstract methods (Removes Warning)
    additionalContext: Optional[dict[str, Any]] = None  # Allows for passing additional keyword fields to the new function
):
    def internal(destination: Callable):
        Logger.debug(f"Injecting Method {destination.__name__} {at} class {target.__name__} ({target})", module="dynamic-method-inject")

        # Generate the additional contexts
        ctxArgs = dict()
        if additionalContext:
            ctxArgs.update(additionalContext)  # Add additional context if it exists

        # Sanity check PassResult
        if passResult and at == InjectionPoint.BEFORE:
            raise MixinError("Cannot pass result of original function to new function if injection point is BEFORE!")

        # Check if both the target and the destination are either both async or both non async
        if inspect.iscoroutinefunction(target) is False and inspect.iscoroutinefunction(destination) is True:
            raise MixinError(f"Cannot inject async function {destination.__name__} into non-async function {target.__name__}!")
        elif inspect.iscoroutinefunction(target) is True and inspect.iscoroutinefunction(destination) is False:
            raise MixinError(f"Cannot inject non-async function {destination.__name__} into async function {target.__name__}!")
        # If both target and destination are async, implement the async injection
        elif inspect.iscoroutinefunction(target) is True and inspect.iscoroutinefunction(destination) is True:
            if at == InjectionPoint.BEFORE:
                async def _asyncinject(*args, **kwargs):
                    # Call new function
                    await destination(*args, **kwargs, **ctxArgs)

                    # Call original function
                    return await target(*args, **kwargs)
            elif at == InjectionPoint.AFTER:
                if passResult:
                    async def _asyncinject(*args, **kwargs):
                        # Call original function
                        output = await target(*args, **kwargs)

                        # Call and return the new function
                        return await destination(*args, **kwargs, **ctxArgs, _output=output)
                else:
                    async def _asyncinject(*args, **kwargs):
                        # Call original function
                        await target(*args, **kwargs)

                        # Call and return the new function
                        return await destination(*args, **kwargs, **ctxArgs)
            else:
                raise MixinError(f"Invalid Injection Point: {at}")

            # Spoof the signature of the original function
            _asyncinject.__signature__ = inspect.signature(target)

            _overrideMethod(
                target,
                _asyncinject,
                abstract=abstract
            )
        # Both target and destination are non-async, implement the non-async injection
        else:
            if at == InjectionPoint.BEFORE:
                def _inject(*args, **kwargs):
                    # Call new function
                    destination(*args, **kwargs, **ctxArgs)

                    # Call original function
                    return target(*args, **kwargs)
            elif at == InjectionPoint.AFTER:
                if passResult:
                    def _inject(*args, **kwargs):
                        # Call original function
                        output = target(*args, **kwargs)

                        # Call and return the new function
                        return destination(*args, **kwargs, **ctxArgs, _output=output)
                else:
                    def _inject(*args, **kwargs):
                        # Call original function
                        target(*args, **kwargs)

                        # Call and return the new function
                        return destination(*args, **kwargs, **ctxArgs)
            else:
                raise MixinError(f"Invalid Injection Point: {at}")

            # Spoof the signature of the original function
            _inject.__signature__ = inspect.signature(target)

            _overrideMethod(
                target,
                _inject,
                abstract=abstract
            )

        return destination
    return internal


# Method Extension Decorator - Provides dynamic run-time method extension. Passes output of original function as argument of new function.
# Used In @Extend
def Extend(
    target: Callable,
    abstract: bool = False,  # Allows for modifying abstract methods (Removes Warning)
    additionalContext: Optional[dict[str, Any]] = None  # Allows for passing additional keyword fields to the new function
):
    def internal(destination: Callable):
        Logger.debug(f"Extending Method {target.__name__} ({target}) with {destination.__name__}", module="dynamic-method-extend")

        # Generate the additional contexts
        ctxArgs = dict()
        if additionalContext:
            ctxArgs.update(additionalContext)  # Add additional context if it exists

        # Check if both the target and the destination are either both async or both non async
        if inspect.iscoroutinefunction(target) is False and inspect.iscoroutinefunction(destination) is True:
            raise MixinError(f"Cannot extend non-async function {target.__name__} with async function {destination.__name__}!")
        elif inspect.iscoroutinefunction(target) is True and inspect.iscoroutinefunction(destination) is False:
            raise MixinError(f"Cannot extend async function {target.__name__} with non-async function {destination.__name__}!")
        # If both target and destination are async, implement the async extension
        elif inspect.iscoroutinefunction(target) is True and inspect.iscoroutinefunction(destination) is True:
            async def _asyncextend(*args, **kwargs):
                output = await target(*args, **kwargs, **ctxArgs)
                return await destination(output)

            # Spoof the signature of the original function
            _asyncextend.__signature__ = inspect.signature(target)

            _overrideMethod(
                target,
                _asyncextend,
                abstract=abstract
            )
        # Both target and destination are non-async, implement the non-async extension
        else:
            def _extend(*args, **kwargs):
                output = target(*args, **kwargs, **ctxArgs)
                return destination(output)

            # Spoof the signature of the original function
            _extend.__signature__ = inspect.signature(target)

            _overrideMethod(
                target,
                _extend,
                abstract=abstract
            )

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
            raise MixinError(f"Method {destName} already exists in class {targetName}")

        # Adding method to destination class
        setattr(target, destName, destination)
        Logger.debug(f"Added {destName} to {targetName}", module="dynamic-method-inject")

    return internal


# Add Attribute Decorator. Used to dynamically add new attributes to classes at runtime
def addAttribute(
    target: Type[object],
    name: str,
    default: Any = None
):
    Logger.debug(f"Injecting Attribute {name} into class {target.__name__} ({target})", module="dynamic-attribute-inject")

    # Check if if attribute of name target already exists
    if hasattr(target, name):
        # Attribute registered under the same name
        conflict = getattr(target, name)
        # Return error to user
        Logger.error(f"Class {target.__name__} already contains attribute of name {name} ({conflict})", module="dynamic-attribute-inject")
        raise MixinError(f"Attribute {name} already exists in class {target.__name__}")

    # Adding attribute initialization to __init__ method of destination class
    oldInit = target.__init__

    def _attribute_init(self, *args, **kwargs):
        oldInit(self, *args, **kwargs)
        setattr(self, name, default)

    # Check if method has an init method to inject to
    if hasattr(target, "__init__"):
        _overrideMethod(target.__init__, _attribute_init)
    else:
        # Add init method to class
        setattr(target, "__init__", _attribute_init)

    Logger.debug(f"Added {name} to {target.__name__}", module="dynamic-attribute-inject")
