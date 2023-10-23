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

            # Add dictionary of additional hard-coded text macros for the emojis
            # This is for adding additional functionality as well as providing
            # compatibility with the fcraft emoji system
            self.textMacros.update({
                # fCraft Emojis
                ":)": Emojis.SMILE,
                "<3": Emojis.HEART,
                "8": Emojis.EIGHTH_NOTE,
                "!!": Emojis.DOUBLE_EXCLAMATION_MARK,
                "p": Emojis.PARAGRAPH,
                "s": Emojis.SELECTION,
                "*": Emojis.BULLET,
                "o": Emojis.CIRCLE,
                "-": Emojis.BAR,
                "_": Emojis.BAR,
                "l": Emojis.RIGHT_ANGLE,
                "^": Emojis.UP_ARROW,
                "v": Emojis.DOWN_ARROW,
                ">": Emojis.RIGHT_ARROW,
                "->": Emojis.RIGHT_ARROW,
                "<": Emojis.LEFT_ARROW,
                "<-": Emojis.LEFT_ARROW,
                "^^": Emojis.UP_TRIANGLE,
                "vv": Emojis.DOWN_TRIANGLE,
                ">>": Emojis.RIGHT_TRIANGLE,
                "<<": Emojis.LEFT_TRIANGLE,
                "<>": Emojis.LEFT_RIGHT_ARROW,
                "<->": Emojis.LEFT_RIGHT_ARROW,
                "^v": Emojis.UP_DOWN_ARROW,
                "^v_": Emojis.UP_DOWN_ARROW_WITH_BASE,
                # Add caret, tilde, and grave characters for vanilla classic client compatibility
                "caret": "^",
                "hat": "^",
                "tilde": "~",
                "wave": "~",
                "'": "`",
                "grave": "`",
                # Custom ProjectObsidian Emoji Macros
                ":D": Emojis.SMILE,
                ".": Emojis.DOT,
                "<=>": Emojis.LEFT_RIGHT_ARROW,
                "?_": Emojis.INVERSE_QUESTION_MARK,
                "!_": Emojis.INVERSE_EXCLAMATION_MARK,
                "1/2": Emojis.ONE_HALF,
                "1/4": Emojis.ONE_FOURTH,
                "<<<": Emojis.LEFT_GUILLEMET,
                ">>>": Emojis.RIGHT_GUILLEMET,
                "|": Emojis.BOX_DRAWINGS_LIGHT_VERTICAL,
                "==": Emojis.IDENTICAL_TO,
                "+-": Emojis.PLUS_MINUS,
                ">=": Emojis.GREATER_THAN_OR_EQUAL_TO,
                "<=": Emojis.LESS_THAN_OR_EQUAL_TO,
                "/": Emojis.DIVISION_SIGN,
                "~=": Emojis.ALMOST_EQUAL_TO,
                "^n": Emojis.SUPERSCRIPT_N,
                "^2": Emojis.SUPERSCRIPT_TWO,
                "[]": Emojis.BLACK_SQUARE,
            })

            # Add additional text macros
            Logger.debug(f"{len(self.textMacros)} Emoji Text Macros Loaded", module="textmacros")

        # Load custom text macros from config
        Logger.info("Loading Custom Text Macros", module="textmacros")
        customMacros = self.config.customMacros
        for key, value in customMacros.items():
            if not isinstance(key, str) and not isinstance(value, str):
                raise ModuleError(f"Invalid Key or Value for Custom Macro {key}: {value}!")
            self.textMacros[key.lower()] = value
        Logger.debug(f"{len(customMacros)} Custom Text Macros Loaded: {customMacros}", module="texthotkey")

        # Log total number of text macros loaded
        Logger.info(f"{len(self.textMacros)} Total Text Macros Loaded", module="textmacros")

    # Config for TextMacrosConfig
    @dataclass
    class TextMacrosConfig(AbstractConfig):
        macroStartChar: str = "{"
        macroEndChar: str = "}"
        emojiMacros: bool = True
        customMacros: dict = field(default_factory=dict)
