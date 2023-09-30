from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE, CPEExtension
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets
from obsidian.network import NetworkHandler
from obsidian.config import AbstractConfig
from obsidian.mixins import Inject, InjectionPoint
from obsidian.errors import ServerError, ModuleError
from obsidian.commands import AbstractCommand, Command
from obsidian.player import Player
from obsidian.log import Logger

from dataclasses import dataclass, field
from typing import cast
import struct


@Module(
    "TextColors",
    description="This extension allows the server to define custom text colors.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core"), Dependency("ColorPicker")]
)
@CPE(
    extName="TextColors",
    extVersion=1,
    cpeOnly=True
)
class TextColorsModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.TextColorsConfig)

        # Verify color config
        self.verifyColorConfig()

    def postInit(self):
        super().postInit()

        # Send text colors once user joins
        @Inject(target=NetworkHandler._processPostLogin, at=InjectionPoint.AFTER, additionalContext={"textColorsConfig": self.config})
        async def sendTextColors(self, *, textColorsConfig: "TextColorsModule.TextColorsConfig"):
            # Since we are injecting, set type of self to Player
            self = cast(NetworkHandler, self)

            # Check if player is not None
            if self.player is None:
                raise ServerError("Trying To Process Post Login Actions Before Player Is Initialized!")

            # Check if player supports the TextColors Extension
            if self.player.supports(CPEExtension("TextColors", 1)):
                Logger.debug(f"{self.connectionInfo} | Sending Text Colors", module="network")
                # Send colors to player
                for label, data in textColorsConfig.colors.items():
                    Logger.debug(f"{self.connectionInfo} | Sending Text Color {label}", module="network")
                    await self.dispatcher.sendPacket(
                        Packets.Response.SetTextColor,
                        data["red"],
                        data["green"],
                        data["blue"],
                        data["alpha"],
                        data["colorCode"]
                    )

    # Helper method to verify color config
    def verifyColorConfig(self):
        Logger.info("Verifying Color Config", module="textcolors")

        # Get and verify colors
        colors = self.config.colors
        for label, data in colors.items():
            # Check the red label
            if "red" not in data:
                raise ModuleError(f"Missing red value for color {label}!")
            elif type(data["red"]) is not int:
                raise ModuleError(f"Red value for color {label} must be int!")
            elif data["red"] > 255 or data["red"] < 0:
                raise ModuleError(f"Red value for color {label} must be between 0 and 255!")

            # Check the green label
            if "green" not in data:
                raise ModuleError(f"Missing green value for color {label}!")
            elif type(data["green"]) is not int:
                raise ModuleError(f"Green value for color {label} must be int!")
            elif data["green"] > 255 or data["green"] < 0:
                raise ModuleError(f"Green value for color {label} must be between 0 and 255!")

            # Check the blue label
            if "blue" not in data:
                raise ModuleError(f"Missing blue value for color {label}!")
            elif type(data["blue"]) is not int:
                raise ModuleError(f"Blue value for color {label} must be int!")
            elif data["blue"] > 255 or data["blue"] < 0:
                raise ModuleError(f"Blue value for color {label} must be between 0 and 255!")

            # Check the alpha label
            if "alpha" not in data:
                raise ModuleError(f"Missing alpha value for color {label}!")
            elif type(data["alpha"]) is not int:
                raise ModuleError(f"Alpha value for color {label} must be int!")
            elif data["alpha"] > 255 or data["alpha"] < 0:
                raise ModuleError(f"Alpha value for color {label} must be between 0 and 255!")

            # Check the color code
            if "colorCode" not in data:
                raise ModuleError(f"Missing color code value for color {label}!")
            elif type(data["colorCode"]) is not str or len(data["colorCode"]) != 1:
                raise ModuleError(f"Color code value for color {label} must be a single character string!")

        # Finish config verification
        Logger.info(f"{len(colors)} Colors Loaded: {colors}", module="textcolors")

    # Packet to send to clients to add a text color
    @ResponsePacket(
        "SetTextColor",
        description="Sends a text color definition to the client. Can be sent anytime.",
    )
    class SetTextColorPacket(AbstractResponsePacket["TextColorsModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x27,
                FORMAT="!BBBBBB",
                CRITICAL=False
            )

        async def serialize(self, red: int, green: int, blue: int, alpha: int, colorCode: str):
            # <Set Text Color Packet>
            # (Byte) Packet ID
            # (Byte) Red Value
            # (Byte) Green Value
            # (Byte) Blue Value
            # (Byte) Alpha Value
            # (Byte) Color Code
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                red, green, blue, alpha,
                ord(colorCode)
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    @Command(
        "ReloadTextColors",
        description="Reloads all the text colors",
        version="v1.0.0"
    )
    class ReloadTextColorsCommand(AbstractCommand["TextColorsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["reloadcolors"], OP=True)

        async def execute(self, ctx: Player):
            # Reload and Verify Config
            self.module.config.reload()
            self.module.verifyColorConfig()

            # Send new colors to all players
            Logger.debug("Sending new colors to all players", module="textcolors")
            for player in ctx.playerManager.getPlayers():
                Logger.debug(f"Sending Text Colors to Player {player}", module="textcolors")
                # Send colors to player
                for label, data in self.module.config.colors.items():
                    Logger.verbose(f"Sending Text Color {label}", module="textcolors")
                    await player.networkHandler.dispatcher.sendPacket(
                        Packets.Response.SetTextColor,
                        data["red"],
                        data["green"],
                        data["blue"],
                        data["alpha"],
                        data["colorCode"]
                    )

            # Notify the user
            await ctx.sendMessage("&aText Colors Reloaded!")

    # Create command to test out colors.
    # Override the original ColorCommand to use the new TextColors packet
    @Command(
        "Color",
        description="Prints out all the colors + custom colors",
        version="v1.0.0",
        override=True
    )
    class ColorCommand(AbstractCommand["TextColorsModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["colors", "c"])

        async def execute(self, ctx: Player, *, msg: str = "TEST"):
            additionalColors = [c.get("colorCode") for c in self.module.config.colors.values()]
            for c in "0123456789abcdef" + "".join(additionalColors):
                await ctx.sendMessage(f"&{c}{c}: {msg}")

    # Config for text colors
    @dataclass
    class TextColorsConfig(AbstractConfig):
        colors: dict = field(default_factory=dict)
