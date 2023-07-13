from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE, CPEExtension
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets, packageString
from obsidian.network import NetworkHandler
from obsidian.config import AbstractConfig
from obsidian.mixins import Inject, InjectionPoint
from obsidian.errors import ServerError, ModuleError
from obsidian.log import Logger

from dataclasses import dataclass, field
from typing import cast
import struct


@Module(
    "TextHotKey",
    description="Allows the server to define hotkeys for certain commands.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="TextHotKey",
    extVersion=1,
    cpeOnly=True
)
class TextHotKeyModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.TextHotKeyConfig)

    def postInit(self):
        super().postInit()

        # Get and verify hotkeys
        hotkeys = self.config.hotkeys
        for label, data in hotkeys.items():
            if ("action" not in data) or (type(data["action"]) is not str):
                raise ModuleError(f"Invalid Action Field For Hotkey {label}!")
            if ("keyCode" not in data) or (type(data["keyCode"]) is not int):
                raise ModuleError(f"Invalid KeyCode Field For Hotkey {label}!")
            if ("keyMods" not in data) or (type(data["keyMods"]) is not int):
                raise ModuleError(f"Invalid KeyMods Field For Hotkey {label}!")

        # Send text hotkeys once user joins
        @Inject(target=NetworkHandler._processPostLogin, at=InjectionPoint.AFTER)
        async def sendTextHotkeys(self):
            # Since we are injecting, set type of self to Player
            self = cast(NetworkHandler, self)

            # Check if player is not None
            if self.player is None:
                raise ServerError("Trying To Process Post Login Actions Before Player Is Initialized!")

            # Check if player supports the TextHotKey Extension
            if CPEExtension("TextHotKey", 1) in self.player.getSupportedCPE():
                Logger.debug(f"{self.connectionInfo} | Sending Hotkeys", module="network")
                # Send hotkeys to player
                for label, data in hotkeys.items():
                    Logger.debug(f"{self.connectionInfo} | Sending Hotkey {label}", module="network")
                    await self.dispatcher.sendPacket(
                        Packets.Response.SetTextHotKey,
                        label,
                        data["action"],
                        data["keyCode"],
                        data["keyMods"]
                    )

    # Packet to send to clients to add a text hotkey
    @ResponsePacket(
        "SetTextHotKey",
        description="Sends a text hotkey macro to the client. Should only be sent once per macro.",
    )
    class SetTextHotKeyPacket(AbstractResponsePacket["TextHotKeyModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x15,
                FORMAT="!B64s64siB",
                CRITICAL=False
            )

        async def serialize(self, label: str, action: str, keyCode: int, keyMods: int):
            # <Set Text HotKey Packet>
            # (Byte) Packet ID
            # (64String) Label
            # (64String) Action
            # (Int) KeyCode
            # (Byte) KeyMods
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                bytearray(packageString(label)),
                bytearray(packageString(action)),
                keyCode,
                keyMods
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # Config for text hotkeys
    @dataclass
    class TextHotKeyConfig(AbstractConfig):
        hotkeys: dict = field(default_factory=dict)
