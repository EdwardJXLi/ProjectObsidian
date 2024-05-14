from obsidian.module import Module, AbstractModule, Dependency, Modules
from obsidian.cpe import CPE, CPEExtension
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player, WorldPlayerManager
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets
from obsidian.world import World, WorldMetadata
from obsidian.worldformat import WorldFormatManager, WorldFormats
from obsidian.config import AbstractConfig
from obsidian.mixins import Inject, InjectionPoint
from obsidian.errors import CPEError, CommandError, ConverterError
from obsidian.log import Logger

from dataclasses import dataclass
from typing import Optional, cast
from enum import Enum
import struct


class WeatherType(Enum):
    SUN = 0
    RAIN = 1
    SNOW = 2

    @staticmethod
    def _convertArgument(_, argument: str):
        try:
            # Try to get the weather type as an int
            return WeatherType(int(argument))
        except (KeyError, ValueError):
            # If fail, try to get weather type as a string
            try:
                return WeatherType[argument.upper()]
            except (KeyError, ValueError):
                # Raise error if weather type not found
                raise ConverterError(f"WeatherType {argument} Not Found!")


@Module(
    "EnvWeatherType",
    description="This extension allows the server to trigger special weather conditions (like rain and snow) on demand.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="EnvWeatherType",
    extVersion=1,
    cpeOnly=True
)
class EnvWeatherTypeModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.EnvWeatherTypeConfig)

    def initMetadata(self):
        # Create readers and writers for ObsidianWorld
        def readWeatherType(data: dict):
            weatherTypeMetadata = EnvWeatherTypeModule.EnvWeatherTypeMetadata()

            # Read weather type
            Logger.debug(f"Reading Weather Type Metadata: {data}", module="envweathertype")
            weatherTypeMetadata.setWeatherType(WeatherType(data["weatherType"]))  # Convert weather type to WeatherType enum
            Logger.debug(f"Weather Type: {weatherTypeMetadata.getWeatherType().name}", module="envweathertype")

            return weatherTypeMetadata

        def writeWeatherType(weatherTypeMetadata: EnvWeatherTypeModule.EnvWeatherTypeMetadata):
            Logger.debug(f"Writing Weather Type Metadata: {weatherTypeMetadata.getWeatherType().name}", module="envweathertype")
            return {"weatherType": weatherTypeMetadata.getWeatherType().value}

        # Register readers and writers
        WorldFormatManager.registerMetadataReader(WorldFormats.ObsidianWorld, "CPE", "envWeatherType", readWeatherType)
        WorldFormatManager.registerMetadataWriter(WorldFormats.ObsidianWorld, "CPE", "envWeatherType", writeWeatherType)

        # If ClassicWorld is installed, create readers and writers for ClassicWorld
        if "ClassicWorld" in WorldFormats:
            from obsidian.modules.lib.nbtlib import NBTLib

            # Create readers and writers for ClassicWorld
            def cwReadWeatherType(data: NBTLib.TAG_Compound):
                weatherTypeMetadata = EnvWeatherTypeModule.EnvWeatherTypeMetadata()

                # Check if ExtensionVersion is supported
                # Some software (cough classicube) has this missing, so check if it exists first
                if "ExtensionVersion" in data and data["ExtensionVersion"].value != 1:
                    raise CPEError(f"ClassicWorld EnvWeatherType ExtensionVersion {data['ExtensionVersion'].value} is not supported!")

                # Read weather type
                Logger.debug(f"Reading Weather Type Metadata: {data}", module="envweathertype")
                weatherTypeMetadata.setWeatherType(WeatherType(data["WeatherType"].value))  # Convert weather type to WeatherType enum
                Logger.debug(f"Weather Type: {weatherTypeMetadata.getWeatherType().name}", module="envweathertype")

                return weatherTypeMetadata

            def cwWriteWeatherType(weatherTypeMetadata: EnvWeatherTypeModule.EnvWeatherTypeMetadata):
                metadataNbt = NBTLib.TAG_Compound(name="EnvWeatherType")

                # Write version info
                metadataNbt.tags.append(NBTLib.TAG_Short(name="ExtensionVersion", value=1))

                # Write weather type
                Logger.debug(f"Writing Weather Type Metadata: {weatherTypeMetadata.getWeatherType().name}", module="envweathertype")
                metadataNbt.tags.append(NBTLib.TAG_Short(name="WeatherType", value=weatherTypeMetadata.getWeatherType().value))

                return metadataNbt

            # Register readers and writers
            WorldFormatManager.registerMetadataReader(WorldFormats.ClassicWorld, "CPE", "envWeatherType", cwReadWeatherType)
            WorldFormatManager.registerMetadataWriter(WorldFormats.ClassicWorld, "CPE", "envWeatherType", cwWriteWeatherType)

    def initMixins(self):
        # Send world weather type on join
        @Inject(target=WorldPlayerManager.joinPlayer, at=InjectionPoint.AFTER)
        async def sendWorldEnvWeatherType(self, player: Player, *args, **kwargs):
            # Since we are injecting, set type of self to WorldPlayerManager
            self = cast(WorldPlayerManager, self)

            # Check if player supports the EnvWeatherType Extension
            if player.supports(CPEExtension("EnvWeatherType", 1)):
                # Send weather type packet to player
                await EnvWeatherTypeModule.setPlayerWeatherType(player, EnvWeatherTypeModule.getWorldWeatherType(self.world))

        # Load weather type during world load
        @Inject(target=World.__init__, at=InjectionPoint.AFTER)
        def loadWorldEnvWeatherType(self, *args, **kwargs):
            # Since we are injecting, set type of self to World
            self = cast(World, self)

            # Get default weather type from config
            defaultWeatherType = WeatherType(cast(EnvWeatherTypeModule, Modules.EnvWeatherType).config.defaultWeatherType)

            # If "weatherType" metadata is not present, create it
            if self.additionalMetadata.get(("CPE", "envWeatherType")) is None:
                Logger.info(f"Creating weather type metadata for {self.name}", module="envweathertype")
                weatherTypeMetadata = EnvWeatherTypeModule.EnvWeatherTypeMetadata()
                weatherTypeMetadata.setWeatherType(defaultWeatherType)
                self.additionalMetadata[("CPE", "envWeatherType")] = weatherTypeMetadata

            setattr(self, "weatherTypeMetadata", self.additionalMetadata[("CPE", "envWeatherType")])

    def postInit(self):
        super().postInit()

        # Set up metadata handlers
        self.initMetadata()

        # Set up mixins
        self.initMixins()

    # Create helper function to set weather type of a player
    @staticmethod
    async def setPlayerWeatherType(player: Player, weatherType: WeatherType):
        # Check if player supports the EnvWeatherType Extension
        if not player.supports(CPEExtension("EnvWeatherType", 1)):
            raise CPEError(f"Player {player.name} Does Not Support EnvWeatherType Extension!")

        Logger.info(f"Setting weather type to {weatherType.name} for {player.username}", module="envweathertype")
        await player.networkHandler.dispatcher.sendPacket(Packets.Response.SetEnvWeatherType, weatherType)

    # Create helper function to set weather type of a world
    @staticmethod
    async def setWorldWeatherType(world: World, weatherType: WeatherType, notifyPlayers: bool = True):
        # Get the weather type metadata
        weatherTypeMetadata: EnvWeatherTypeModule.EnvWeatherTypeMetadata = getattr(world, "weatherTypeMetadata")

        # Set weather type
        Logger.info(f"Setting world weather type to {weatherType.name} ({weatherType.value}) for {world.name}", module="envweathertype")
        weatherTypeMetadata.setWeatherType(weatherType)

        # If notifyPlayers is True, notify players of the change
        if notifyPlayers:
            for player in world.playerManager.getPlayers():
                # Only send weather type to players that support the EnvWeatherType Extension
                if player.supports(CPEExtension("EnvWeatherType", 1)):
                    await EnvWeatherTypeModule.setPlayerWeatherType(player, weatherType)

    # Create helper function to get weather type of a world
    @staticmethod
    def getWorldWeatherType(world: World) -> WeatherType:
        # Return weather type
        return getattr(world, "weatherTypeMetadata").getWeatherType()

    # Packet to send to clients to change weather type
    @ResponsePacket(
        "SetEnvWeatherType",
        description="Changes weather type of world.",
    )
    class SetEnvWeatherTypePacket(AbstractResponsePacket["EnvWeatherTypeModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x1F,
                FORMAT="!BB",
                CRITICAL=False
            )

        async def serialize(self, weatherType: WeatherType):
            # <Set Env Weather Type Packet>
            # (Byte) Packet ID
            # (Byte) WeatherType
            msg = struct.pack(self.FORMAT, self.ID, weatherType.value)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # Command to get and set the world weather type
    @Command(
        "WorldWeatherType",
        description="Gets and sets the weather type for the world",
        version="v1.0.0"
    )
    class WorldEnvWeatherTypeCommand(AbstractCommand["EnvWeatherTypeModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["weathertype", "envweathertype", "wt"],
                OP=True
            )

        async def execute(self, ctx: Player, weatherType: Optional[WeatherType] = None, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Check if weather type is specified. If not, then simply print the weather type
            if weatherType is None:
                weatherType = getattr(world, 'weatherTypeMetadata').getWeatherType()

                if weatherType is not None:  # Add a none check to make type checker happy, even when it should never happen
                    return await ctx.sendMessage(f"&aWeather Type for world {world.name} is {weatherType.name}")
                return  # Add a return to make type checker happy, even when it should never happen

            # Set world Weather Type
            await EnvWeatherTypeModule.setWorldWeatherType(world, weatherType, notifyPlayers=True)

            # Notify Sender
            await ctx.sendMessage(f"&aSet weather for world {world.name} to {weatherType.name}")

    # World Metadata for weather type
    class EnvWeatherTypeMetadata(WorldMetadata):
        def __init__(self):
            self.weatherType: int = WeatherType.SUN.value

        def setWeatherType(self, weatherType: WeatherType):
            self.weatherType = weatherType.value

        def getWeatherType(self) -> WeatherType:
            return WeatherType(self.weatherType)

    # Config for default weather type
    @dataclass
    class EnvWeatherTypeConfig(AbstractConfig):
        defaultWeatherType: int = 0
