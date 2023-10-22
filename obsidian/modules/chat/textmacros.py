from obsidian.module import Module, AbstractModule, Dependency, Modules
from obsidian.player import Player
from obsidian.mixins import Override
from obsidian.config import AbstractConfig
from obsidian.errors import ModuleError
from obsidian.log import Logger
from obsidian.utils.replace import restricted_replace

import re
from typing import Callable
from dataclasses import dataclass, field


@Module(
    "TextMacros",
    description="Adds Customized Text Macros for Emojis and More!",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")],
    soft_dependencies=[Dependency("essentials"), Dependency("emojilib")]
)
class TextMacrosModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.TextMacrosConfig)
        self.textMacros: dict[str, str] = {}

        # Initialize Text Macros
        self.initTextMacros()

    def postInit(self):
        super().postInit()

        # Inject emoji parsing into
        @Override(
            target=Player.parsePlayerMessage,
            passSuper=True,
            additionalContext={"textMacroConfig": self.config, "textMacros": self.textMacros}
        )
        def parseTextMacros(
            self,
            message: str,
            *,  # Get additional contexts
            _super: Callable[..., None],
            textMacroConfig: "TextMacrosModule.TextMacrosConfig",
            textMacros: dict[str, str]
        ):
            # Quick optimization to make sure we don't parse if there the start and end char dont exist
            if textMacroConfig.macroStartChar in message and textMacroConfig.macroEndChar in message:
                Logger.debug("Potential text macro detected. Parsing...", module="textmacros")
                # Iterate through all text macros and replace them
                for key, value in textMacros.items():
                    message = restricted_replace(
                        message,
                        f"{textMacroConfig.macroStartChar}{key}{textMacroConfig.macroEndChar}",
                        value,
                        regex_flags=re.IGNORECASE
                    )

            # Return the parsed message
            return _super(self, message)

    def initTextMacros(self):
        Logger.info("Initializing Text Macros", module="textmacros")
        # Clear existing text macros
        self.textMacros = {}

        # Load emoji macros
        if self.config.emojiMacros and "emojilib" in Modules:
            Logger.info("Loading Emoji Text Macros", module="textmacros")
            from obsidian.modules.lib.emojilib import Emojis

            # Iterate through all Emojis and add its value as the macro
            for key, value in Emojis.__dict__.items():
                # Skip all dunder fields
                if key.startswith("_"):
                    continue

                # Add emoji to text macros
                self.textMacros[key.lower()] = value

            # Add additional text macros
            Logger.info(f"{len(self.textMacros)} Emoji Text Macros Loaded", module="textmacros")

        # Load custom text macros from config
        Logger.info("Loading Custom Text Macros", module="textmacros")
        customMacros = self.config.customMacros
        for key, value in customMacros.items():
            if not isinstance(key, str) and not isinstance(value, str):
                raise ModuleError(f"Invalid Key or Value for Custom Macro {key}: {value}!")
            self.textMacros[key.lower()] = value
        Logger.info(f"{len(customMacros)} Custom Text Macros Loaded: {customMacros}", module="texthotkey")

    # Config for TextMacrosConfig
    @dataclass
    class TextMacrosConfig(AbstractConfig):
        macroStartChar: str = "{"
        macroEndChar: str = "}"
        emojiMacros: bool = True
        customMacros: dict = field(default_factory=dict)
