from obsidian.module import Module, AbstractModule, Dependency, Modules
from obsidian.cpe import CPE, CPEExtension
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player, WorldPlayerManager
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets, packageString
from obsidian.world import World, WorldMetadata
from obsidian.worldformat import WorldFormatManager, WorldFormats
from obsidian.blocks import AbstractBlock, Blocks
from obsidian.config import AbstractConfig
from obsidian.mixins import Inject, InjectionPoint
from obsidian.errors import CPEError, CommandError, ConverterError
from obsidian.log import Logger

from dataclasses import dataclass
from typing import Callable, Any, Optional, cast
from enum import Enum
import struct


class AspectPropertyType(Enum):
    SIDE_BLOCK = 0
    EDGE_BLOCK = 1
    EDGE_HEIGHT = 2
    CLOUD_HEIGHT = 3
    MAX_FOG = 4
    CLOUD_SPEED = 5
    WEATHER_SPEED = 6
    WEATHER_FADE = 7
    EXPONENTIAL_FOG = 8
    MAP_EDGE_OFFSET = 9
    SKYBOX_HORIZONTAL_SPEED = 10
    SKYBOX_VERTICAL_SPEED = 11

    @staticmethod
    def _convertArgument(_, argument: str):
        try:
            # Try to get the weather type as an int
            return AspectPropertyType(int(argument))
        except (KeyError, ValueError):
            # If fail, try to get weather type as a string
            try:
                return AspectPropertyType[argument.upper()]
            except (KeyError, ValueError):
                # Raise error if weather type not found
                raise ConverterError(f"AspectPropertyType {argument} Not Found!")


# Map between AspectPropertyType and attribute name, type
_AspectPropertyAttributeMap = {
    AspectPropertyType.SIDE_BLOCK: ("sideBlock", AbstractBlock),
    AspectPropertyType.EDGE_BLOCK: ("edgeBlock", AbstractBlock),
    AspectPropertyType.EDGE_HEIGHT: ("edgeHeight", int),
    AspectPropertyType.CLOUD_HEIGHT: ("cloudHeight", int),
    AspectPropertyType.MAX_FOG: ("maxFog", int),
    AspectPropertyType.CLOUD_SPEED: ("cloudSpeed", float),
    AspectPropertyType.WEATHER_SPEED: ("weatherSpeed", float),
    AspectPropertyType.WEATHER_FADE: ("weatherFade", float),
    AspectPropertyType.EXPONENTIAL_FOG: ("exponentialFog", int),
    AspectPropertyType.MAP_EDGE_OFFSET: ("mapEdgeOffset", int),
    AspectPropertyType.SKYBOX_HORIZONTAL_SPEED: ("skyboxHorizontalSpeed", float),
    AspectPropertyType.SKYBOX_VERTICAL_SPEED: ("skyboxVerticalSpeed", float)
}


@Module(
    "EnvMapAspect",
    description="This extension allows the server to specify custom appearance packs, and tweak appearance of a map",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="EnvMapAspect",
    extVersion=1,
    cpeOnly=True
)
class EnvMapAspectModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.EnvMapAspectConfig)

    def initMetadata(self):
        # Create readers and writers for ObsidianWorld
        def readMapAspect(data: dict):
            mapAspectMetadata = EnvMapAspectModule.EnvMapAspectMetadata()

            # Read map aspect
            Logger.debug(f"Reading Map Aspect Metadata: {data}", module="extmapaspect")
            # Tuple of attribute key, conversion function, and default value
            mapAspectKeys: list[tuple[str, Callable, Any]] = [
                ("sideBlock", Blocks.getBlockById, Blocks.BEDROCK),
                ("edgeBlock", Blocks.getBlockById, Blocks.STATIONARYWATER),
                ("edgeHeight", int, 0),
                ("cloudHeight", int, 0),
                ("maxFog", int, 0),
                ("cloudSpeed", float, 1.0),
                ("weatherSpeed", float, 1.0),
                ("weatherFade", float, 1.0),
                ("exponentialFog", int, 0),
                ("mapEdgeOffset", int, -2),
                ("skyboxHorizontalSpeed", float, 0.0),
                ("skyboxVerticalSpeed", float, 0.0),
            ]

            mapAspectValues = list()
            for key, conversion, default in mapAspectKeys:
                if key in data:
                    mapAspectValues.append(conversion(data[key]))
                else:
                    mapAspectValues.append(default)
                    Logger.warn(f"{key} not found in map aspect metadata. Defaulting to {default}", module="extmapaspect")

            mapAspectMetadata.setBulkMapAspect(
                *mapAspectValues
            )

            Logger.debug(f"Map Aspect: {mapAspectMetadata.getBulkMapAspect()}", module="extmapaspect")

            return mapAspectMetadata

        def writeMapAspect(mapAspectMetadata: EnvMapAspectModule.EnvMapAspectMetadata):
            Logger.debug(f"Writing Map Aspect Metadata: {mapAspectMetadata.getBulkMapAspect()}", module="extmapaspect")
            return {
                "sideBlock": mapAspectMetadata.sideBlock.ID,
                "edgeBlock": mapAspectMetadata.edgeBlock.ID,
                "edgeHeight": mapAspectMetadata.edgeHeight,
                "cloudHeight": mapAspectMetadata.cloudHeight,
                "maxFog": mapAspectMetadata.maxFog,
                "cloudSpeed": mapAspectMetadata.cloudSpeed,
                "weatherSpeed": mapAspectMetadata.weatherSpeed,
                "weatherFade": mapAspectMetadata.weatherFade,
                "exponentialFog": mapAspectMetadata.exponentialFog,
                "mapEdgeOffset": mapAspectMetadata.mapEdgeOffset
            }

        def readEnvMapAppearance(data: dict):
            mapAppearance = EnvMapAspectModule.EnvMapAppearanceMetadata()

            # Read map appearance
            Logger.debug(f"Reading Map Appearance Metadata: {data}", module="extmapaspect")
            if "textureUrl" in data:
                mapAppearance.setTexturePack(data["textureUrl"])
            else:
                Logger.warn("textureUrl not found in map appearance metadata", module="extmapaspect")

            Logger.debug(f"Map Appearance: Texture Pack: {mapAppearance.getTexturePack()}", module="extmapaspect")

            return mapAppearance

        def writeEnvMapAppearance(mapAppearance: EnvMapAspectModule.EnvMapAppearanceMetadata):
            Logger.debug(f"Writing Map Appearance Metadata: Texture Pack: {mapAppearance.getTexturePack()}", module="extmapaspect")
            return {
                "textureUrl": mapAppearance.getTexturePack()
            }

        # Register readers and writers
        WorldFormatManager.registerMetadataReader(WorldFormats.ObsidianWorld, "CPE", "envMapAspect", readMapAspect)
        WorldFormatManager.registerMetadataWriter(WorldFormats.ObsidianWorld, "CPE", "envMapAspect", writeMapAspect)
        WorldFormatManager.registerMetadataReader(WorldFormats.ObsidianWorld, "CPE", "envMapAppearance", readEnvMapAppearance)
        WorldFormatManager.registerMetadataWriter(WorldFormats.ObsidianWorld, "CPE", "envMapAppearance", writeEnvMapAppearance)

        # If ClassicWorld is installed, create readers and writers for ClassicWorld
        if "ClassicWorld" in WorldFormats:
            from obsidian.modules.lib.nbtlib import NBTLib

            # Create readers and writers for ClassicWorld
            def cwReadMapAspect(data: NBTLib.TAG_Compound):
                mapAspectMetadata = EnvMapAspectModule.EnvMapAspectMetadata()

                # Check if ExtensionVersion is supported
                # Some software (cough classicube) has this missing, so check if it exists first
                if "ExtensionVersion" in data and data["ExtensionVersion"].value != 1:
                    raise CPEError(f"ClassicWorld EnvMapAspect ExtensionVersion {data['ExtensionVersion'].value} is not supported!")

                # Read map aspect
                Logger.debug(f"Reading Map Aspect Metadata: {data}", module="extmapaspect")
                # Tuple of attribute key, conversion function, and default value
                mapAspectKeys: list[tuple[str, Callable, Any]] = [
                    ("SideBlock", Blocks.getBlockById, Blocks.BEDROCK),
                    ("EdgeBlock", Blocks.getBlockById, Blocks.STATIONARYWATER),
                    ("EdgeHeight", int, 0),
                    ("CloudsHeight", int, 0),
                    ("MaxFog", int, 0),
                    ("CloudsSpeed", float, 1.0),
                    ("WeatherSpeed", float, 1.0),
                    ("WeatherFade", float, 1.0),
                    ("ExpFog", int, 0),
                    ("SidesOffset", int, -2),
                    ("SkyboxHor", float, 0.0),
                    ("SkyboxVer", float, 0.0),
                ]

                mapAspectValues = list()
                for key, conversion, default in mapAspectKeys:
                    if key in data:
                        mapAspectValues.append(conversion(data[key].value))
                    else:
                        mapAspectValues.append(default)
                        Logger.warn(f"{key} not found in map aspect metadata. Defaulting to {default}", module="extmapaspect")

                mapAspectMetadata.setBulkMapAspect(
                    *mapAspectValues
                )

                Logger.debug(f"Map Aspect: {mapAspectMetadata.getBulkMapAspect()}", module="extmapaspect")

                return mapAspectMetadata

            def cwWriteMapAspect(mapAspectMetadata: EnvMapAspectModule.EnvMapAspectMetadata):
                metadataNbt = NBTLib.TAG_Compound(name="EnvMapAspect")

                # Write version info
                metadataNbt.tags.append(NBTLib.TAG_Short(name="ExtensionVersion", value=1))

                # Write map aspect
                Logger.debug(f"Writing Map Aspect Metadata: {mapAspectMetadata.getBulkMapAspect()}", module="extmapaspect")
                metadataNbt.tags.append(NBTLib.TAG_Short(name="SideBlock", value=mapAspectMetadata.getMapAspect(AspectPropertyType.SIDE_BLOCK).ID))
                metadataNbt.tags.append(NBTLib.TAG_Short(name="EdgeBlock", value=mapAspectMetadata.getMapAspect(AspectPropertyType.EDGE_BLOCK).ID))
                metadataNbt.tags.append(NBTLib.TAG_Int(name="EdgeHeight", value=mapAspectMetadata.getMapAspect(AspectPropertyType.EDGE_HEIGHT)))
                metadataNbt.tags.append(NBTLib.TAG_Int(name="CloudsHeight", value=mapAspectMetadata.getMapAspect(AspectPropertyType.CLOUD_HEIGHT)))
                metadataNbt.tags.append(NBTLib.TAG_Short(name="MaxFog", value=mapAspectMetadata.getMapAspect(AspectPropertyType.MAX_FOG)))
                metadataNbt.tags.append(NBTLib.TAG_Float(name="CloudsSpeed", value=mapAspectMetadata.getMapAspect(AspectPropertyType.CLOUD_SPEED)))
                metadataNbt.tags.append(NBTLib.TAG_Float(name="WeatherSpeed", value=mapAspectMetadata.getMapAspect(AspectPropertyType.WEATHER_SPEED)))
                metadataNbt.tags.append(NBTLib.TAG_Float(name="WeatherFade", value=mapAspectMetadata.getMapAspect(AspectPropertyType.WEATHER_FADE)))
                metadataNbt.tags.append(NBTLib.TAG_Byte(name="ExpFog", value=mapAspectMetadata.getMapAspect(AspectPropertyType.EXPONENTIAL_FOG)))
                metadataNbt.tags.append(NBTLib.TAG_Int(name="SidesOffset", value=mapAspectMetadata.getMapAspect(AspectPropertyType.MAP_EDGE_OFFSET)))
                metadataNbt.tags.append(NBTLib.TAG_Float(name="SkyboxHor", value=mapAspectMetadata.getMapAspect(AspectPropertyType.SKYBOX_HORIZONTAL_SPEED)))
                metadataNbt.tags.append(NBTLib.TAG_Float(name="SkyboxVer", value=mapAspectMetadata.getMapAspect(AspectPropertyType.SKYBOX_VERTICAL_SPEED)))

                return metadataNbt

            def cwReadMapAppearance(data: NBTLib.TAG_Compound):
                mapAppearance = EnvMapAspectModule.EnvMapAppearanceMetadata()

                # Read map appearance
                Logger.debug(f"Reading Map Appearance Metadata: {data}", module="extmapaspect")
                if "TextureURL" in data:
                    mapAppearance.setTexturePack(data["TextureURL"].value)
                else:
                    Logger.warn("TextureURL not found in map appearance metadata", module="extmapaspect")

                Logger.debug(f"Map Appearance: Texture Pack: {mapAppearance.getTexturePack()}", module="extmapaspect")

                return mapAppearance

            def cwWriteMapAppearance(mapAppearance: EnvMapAspectModule.EnvMapAppearanceMetadata):
                metadataNbt = NBTLib.TAG_Compound(name="EnvMapAppearance")

                # Write map appearance
                Logger.debug(f"Writing Map Appearance Metadata: Texture Pack: {mapAppearance.getTexturePack()}", module="extmapaspect")
                metadataNbt.tags.append(NBTLib.TAG_String(name="TextureURL", value=mapAppearance.getTexturePack() or ""))
                metadataNbt.tags.append(NBTLib.TAG_Byte(name="EdgeBlock", value=-1))
                metadataNbt.tags.append(NBTLib.TAG_Byte(name="SideBlock", value=-1))
                metadataNbt.tags.append(NBTLib.TAG_Short(name="SideLevel", value=-1))

                return metadataNbt

            # Register readers and writers
            WorldFormatManager.registerMetadataReader(WorldFormats.ClassicWorld, "CPE", "envMapAspect", cwReadMapAspect)
            WorldFormatManager.registerMetadataWriter(WorldFormats.ClassicWorld, "CPE", "envMapAspect", cwWriteMapAspect)
            WorldFormatManager.registerMetadataReader(WorldFormats.ClassicWorld, "CPE", "envMapAppearance", cwReadMapAppearance)
            WorldFormatManager.registerMetadataWriter(WorldFormats.ClassicWorld, "CPE", "envMapAppearance", cwWriteMapAppearance)

    def initMixins(self):
        # Send map aspect on join
        @Inject(target=WorldPlayerManager.joinPlayer, at=InjectionPoint.AFTER)
        async def sendEnvMapAspect(self, player: Player, *args, **kwargs):
            # Since we are injecting, set type of self to WorldPlayerManager
            self = cast(WorldPlayerManager, self)

            # Get the map aspect metadata
            mapAspectMetadata: EnvMapAspectModule.EnvMapAspectMetadata = getattr(self.world, "mapAspectMetadata")

            # Check if player supports the EnvMapAspect Extension
            if player.supports(CPEExtension("EnvMapAspect", 1)):
                # Send map aspects to player
                for aspectPropertyType, (attrName, _) in _AspectPropertyAttributeMap.items():
                    await EnvMapAspectModule.setMapAspect(player, aspectPropertyType, getattr(mapAspectMetadata, attrName))

                # Send map appearance
                await EnvMapAspectModule.setMapAppearance(player, getattr(self.world, "mapAppearanceMetadata").getTexturePack())

        # Load map aspect during world load
        @Inject(target=World.__init__, at=InjectionPoint.AFTER)
        def loadWorldEnvMapAspect(self, *args, **kwargs):
            # Since we are injecting, set type of self to World
            self = cast(World, self)

            # Get default map aspect from config
            mapAspectConfig = cast(EnvMapAspectModule, Modules.EnvMapAspect).config
            defaultMapAspect = {
                AspectPropertyType.SIDE_BLOCK: Blocks.getBlockById(mapAspectConfig.defaultSideBlock),
                AspectPropertyType.EDGE_BLOCK: Blocks.getBlockById(mapAspectConfig.defaultEdgeBlock),
                AspectPropertyType.EDGE_HEIGHT: self.sizeY // 2 if mapAspectConfig.automaticallySetEdgeHeight else mapAspectConfig.defaultEdgeHeight,
                AspectPropertyType.CLOUD_HEIGHT: self.sizeY + 2 if mapAspectConfig.automaticallySetCloudHeight else mapAspectConfig.defaultCloudHeight,
                AspectPropertyType.MAX_FOG: mapAspectConfig.defaultMaxFog,
                AspectPropertyType.CLOUD_SPEED: mapAspectConfig.defaultCloudSpeed,
                AspectPropertyType.WEATHER_SPEED: mapAspectConfig.defaultWeatherSpeed,
                AspectPropertyType.WEATHER_FADE: mapAspectConfig.defaultWeatherFade,
                AspectPropertyType.EXPONENTIAL_FOG: mapAspectConfig.defaultExponentialFog,
                AspectPropertyType.MAP_EDGE_OFFSET: mapAspectConfig.defaultMapEdgeOffset,
                AspectPropertyType.SKYBOX_HORIZONTAL_SPEED: mapAspectConfig.defaultSkyboxHorizontalSpeed,
                AspectPropertyType.SKYBOX_VERTICAL_SPEED: mapAspectConfig.defaultSkyboxVerticalSpeed
            }

            # Get default map appearance from config
            defaultTexturePack = mapAspectConfig.defaultTexturePack

            # If "mapAspectMetadata" metadata is not present, create it
            if self.additionalMetadata.get(("CPE", "envMapAspect")) is None:
                Logger.debug(f"Creating Map Aspect Metadata for {self.name}", module="extmapaspect")
                mapAspectMetadata = EnvMapAspectModule.EnvMapAspectMetadata()
                mapAspectMetadata.setBulkMapAspect(*defaultMapAspect.values())
                self.additionalMetadata[("CPE", "envMapAspect")] = mapAspectMetadata

            # If "mapAppearanceMetadata" metadata is not present, create it
            if self.additionalMetadata.get(("CPE", "envMapAppearance")) is None:
                Logger.debug(f"Creating Map Appearance Metadata for {self.name}", module="extmapaspect")
                mapAppearanceMetadata = EnvMapAspectModule.EnvMapAppearanceMetadata()
                mapAppearanceMetadata.setTexturePack(defaultTexturePack)
                self.additionalMetadata[("CPE", "envMapAppearance")] = mapAppearanceMetadata

            setattr(self, "mapAspectMetadata", self.additionalMetadata[("CPE", "envMapAspect")])
            setattr(self, "mapAppearanceMetadata", self.additionalMetadata[("CPE", "envMapAppearance")])

    def postInit(self):
        super().postInit()

        # Set up metadata handlers
        self.initMetadata()

        # Set up mixins
        self.initMixins()

    # Create helper function to set map aspect for a player
    @staticmethod
    async def setMapAspect(player: Player, aspectPropertyType: AspectPropertyType, value: Any):
        # Check if player supports the EnvMapAspect Extension
        if not player.supports(CPEExtension("EnvMapAspect", 1)):
            raise CPEError(f"Player {player.name} Does Not Support EnvMapAspect Extension!")

        Logger.info(f"Setting map aspect {aspectPropertyType.name} to {value} for {player.username}", module="extmapaspect")
        await player.networkHandler.dispatcher.sendPacket(Packets.Response.SetMapAspect, aspectPropertyType, value)

    # Create helper function to set map aspect of a world
    @staticmethod
    async def setWorldMapAspect(world: World, aspectPropertyType: AspectPropertyType, value: Any, notifyPlayers: bool = True):
        # Get the map aspect metadata
        mapAspectMetadata: EnvMapAspectModule.EnvMapAspectMetadata = getattr(world, "mapAspectMetadata")

        # Set the map aspect
        Logger.info(f"Setting map aspect {aspectPropertyType.name} to {value} for {world.name}", module="extmapaspect")
        mapAspectMetadata.setMapAspect(aspectPropertyType, value)

        # If notifyPlayers is True, notify players of the change
        if notifyPlayers:
            for player in world.playerManager.getPlayers():
                # Only send map aspect to players that support the extension
                if player.supports(CPEExtension("EnvMapAspect", 1)):
                    await EnvMapAspectModule.setMapAspect(player, aspectPropertyType, value)

    # Create helper function to get map aspect of a world
    @staticmethod
    def getWorldMapAspect(world: World, aspectPropertyType: AspectPropertyType) -> Any:
        return getattr(world, "mapAspectMetadata").getMapAspect(aspectPropertyType)

    # Create helper function to set map appearance for a player
    @staticmethod
    async def setMapAppearance(player: Player, textureUrl: Optional[str]):
        # Check if player supports the EnvMapAspect Extension
        if not player.supports(CPEExtension("EnvMapAspect", 1)):
            raise CPEError(f"Player {player.name} Does Not Support EnvMapAspect Extension!")

        Logger.info(f"Setting map appearance to {textureUrl} for {player.username}", module="extmapaspect")
        await player.networkHandler.dispatcher.sendPacket(Packets.Response.SetMapEnvUrl, textureUrl)

    # Create helper function to set map appearance of a world
    @staticmethod
    async def setWorldMapAppearance(world: World, textureUrl: Optional[str], notifyPlayers: bool = True):
        # Set the map appearance
        Logger.info(f"Setting map appearance to {textureUrl} for {world.name}", module="extmapaspect")
        setattr(world, "mapAppearanceMetadata", textureUrl)

        # If notifyPlayers is True, notify players of the change
        if notifyPlayers:
            for player in world.playerManager.getPlayers():
                # Only send map aspect to players that support the extension
                if player.supports(CPEExtension("EnvMapAspect", 1)):
                    await EnvMapAspectModule.setMapAppearance(player, textureUrl)

    # Create helper function to get map appearance of a world
    @staticmethod
    def getWorldMapAppearance(world: World) -> Optional[str]:
        return getattr(world, "mapAppearanceMetadata").getTexturePack()

    # Create alias for setMapAppearance
    @staticmethod
    def setTexturePack(player: Player, textureUrl: Optional[str]):
        return EnvMapAspectModule.setMapAppearance(player, textureUrl)

    # Create alias for setWorldMapAppearance
    @staticmethod
    def setWorldTexturePack(world: World, textureUrl: Optional[str], notifyPlayers: bool = True):
        return EnvMapAspectModule.setWorldMapAppearance(world, textureUrl, notifyPlayers)

    # Create alias for getWorldMapAppearance
    @staticmethod
    def getTexturePack(world: World) -> Optional[str]:
        return EnvMapAspectModule.getWorldMapAppearance(world)

    # Packet to send to clients to change map aspect
    @ResponsePacket(
        "SetMapAspect",
        description="Changes Player Map Aspect",
    )
    class SetMapAspectPacket(AbstractResponsePacket["EnvMapAspectModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x29,
                FORMAT="!BBi",
                CRITICAL=False
            )

        async def serialize(self, aspectPropertyType: AspectPropertyType, value: Any):
            # <Set Map Aspect Packet>
            # (Byte) Packet ID
            # (Byte) Property Type
            # (Int) Value

            # If value is a block, get the block ID
            if isinstance(value, AbstractBlock):
                value = value.ID

            # If property type is of type speed, convert to int and times 256
            if "speed" in aspectPropertyType.name.lower():
                value = int(value * 256)

            # If property type is of type fade, convert to int and times 128
            if "fade" in aspectPropertyType.name.lower():
                value = int(value * 128)

            msg = struct.pack(self.FORMAT, self.ID, aspectPropertyType.value, value)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # Packet to send to clients to change texturepacks
    @ResponsePacket(
        "SetMapEnvUrl",
        description="Changes Map Environment (texture) URL",
    )
    class SetMapEnvUrlPacket(AbstractResponsePacket["EnvMapAspectModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x28,
                FORMAT="!B64s",
                CRITICAL=False
            )

        async def serialize(self, textureUrl: str):
            # <Set Map Environment/TexturePack Url>
            # (Byte) Packet ID
            # (64String) Texture Pack URL

            # If no texturepack, set as empty string
            textureUrl = textureUrl or ""

            msg = struct.pack(self.FORMAT, self.ID, packageString(textureUrl))
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # List all types of world map aspects
    @Command(
        "ListEnvMapAspects",
        description="Lists all types of world map aspects",
        version="v1.0.0"
    )
    class ListEnvMapAspectsCommand(AbstractCommand["EnvMapAspectModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["aspects", "listaspects"])

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            await ctx.sendMessage(f"&dCurrent Map Aspects for {world.name}:")
            for aspectPropertyType in AspectPropertyType:
                await ctx.sendMessage(f"&a{aspectPropertyType.name}: &b{EnvMapAspectModule.getWorldMapAspect(world, aspectPropertyType)}")

    # Command to get and set the world map aspect
    @Command(
        "WorldEnvMapAspect",
        description="Gets and sets the world environment map aspect",
        version="v1.0.0"
    )
    class WorldEnvMapAspectCommand(AbstractCommand["EnvMapAspectModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["aspect", "setaspect"],
                OP=True
            )

        async def execute(self, ctx: Player, aspectPropertyType: AspectPropertyType, value: Any = None, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Check if value is specified. If not, then simply print the property value
            if value is None:
                try:
                    return await ctx.sendMessage(f"&aMap Aspect {aspectPropertyType.name} for {world.name} is {getattr(world, 'mapAspectMetadata').getMapAspect(aspectPropertyType)}")
                except ValueError:
                    raise CommandError(f"&cMap Aspect {aspectPropertyType.name} is not set for {world.name}")

            # Convert value to its correct type
            # try:
            valueType = _AspectPropertyAttributeMap[aspectPropertyType][1]
            if hasattr(valueType, "_convertArgument"):
                value = valueType._convertArgument(ctx, value)
            else:
                value = valueType(value)
            # except (ConverterError, ValueError, TypeError):
            #     raise CommandError(f"&cInvalid value for {aspectPropertyType.name}. Expected: {valueType}")

            # Set map aspect
            await EnvMapAspectModule.setWorldMapAspect(world, aspectPropertyType, value, notifyPlayers=True)

            # Notify Sender
            await ctx.sendMessage(f"&aSet Map Aspect {aspectPropertyType.name} for world {world.name} to {value}")

    # Command to reset
    @Command(
        "ResetWorldEnvMapAspect",
        description="Resets the world environment map aspect",
        version="v1.0.0"
    )
    class ResetWorldEnvMapAspectCommand(AbstractCommand["EnvMapAspectModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["resetaspect"],
                OP=True
            )

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Get default map aspect from config
            mapAspectConfig = cast(EnvMapAspectModule, Modules.EnvMapAspect).config
            defaultMapAspect = {
                AspectPropertyType.SIDE_BLOCK: Blocks.getBlockById(mapAspectConfig.defaultSideBlock),
                AspectPropertyType.EDGE_BLOCK: Blocks.getBlockById(mapAspectConfig.defaultEdgeBlock),
                AspectPropertyType.EDGE_HEIGHT: world.sizeY // 2 if mapAspectConfig.automaticallySetEdgeHeight else mapAspectConfig.defaultEdgeHeight,
                AspectPropertyType.CLOUD_HEIGHT: world.sizeY + 2 if mapAspectConfig.automaticallySetCloudHeight else mapAspectConfig.defaultCloudHeight,
                AspectPropertyType.MAX_FOG: mapAspectConfig.defaultMaxFog,
                AspectPropertyType.CLOUD_SPEED: mapAspectConfig.defaultCloudSpeed,
                AspectPropertyType.WEATHER_SPEED: mapAspectConfig.defaultWeatherSpeed,
                AspectPropertyType.WEATHER_FADE: mapAspectConfig.defaultWeatherFade,
                AspectPropertyType.EXPONENTIAL_FOG: mapAspectConfig.defaultExponentialFog,
                AspectPropertyType.MAP_EDGE_OFFSET: mapAspectConfig.defaultMapEdgeOffset,
                AspectPropertyType.SKYBOX_HORIZONTAL_SPEED: mapAspectConfig.defaultSkyboxHorizontalSpeed,
                AspectPropertyType.SKYBOX_VERTICAL_SPEED: mapAspectConfig.defaultSkyboxVerticalSpeed
            }

            # Set world map aspect
            for aspectPropertyType, value in defaultMapAspect.items():
                await EnvMapAspectModule.setWorldMapAspect(world, aspectPropertyType, value, notifyPlayers=True)

            # Notify Sender
            await ctx.sendMessage(f"&aReset map aspects for world {world.name}")

    # Command to get the current world texturepack
    @Command(
        "GetWorldTexturePack",
        description="Gets the current world texture pack",
        version="v1.0.0"
    )
    class GetWorldTexturePackCommand(AbstractCommand["EnvMapAspectModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["texturepack", "textures"],
                OP=True
            )

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Get texture pack
            texturePack = EnvMapAspectModule.getTexturePack(world)

            # Notify Sender
            await ctx.sendMessage(f"&aTexture Pack for world {world.name} is:")
            await ctx.sendMessage(texturePack or "N/A")

    # Command to set the world texturepack
    @Command(
        "SetWorldTexturePack",
        description="Sets the world texture pack",
        version="v1.0.0"
    )
    class SetWorldTexturePackCommand(AbstractCommand["EnvMapAspectModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["settexturepack", "settextures"],
                OP=True
            )

        async def execute(self, ctx: Player, textureUrl: Optional[str] = None, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Set texture pack
            await EnvMapAspectModule.setWorldTexturePack(world, textureUrl, notifyPlayers=True)

            # Notify Sender
            await ctx.sendMessage(f"&aSet Texture Pack for world {world.name} to {textureUrl}")

    # Command to set either self, or another player's textures
    @Command(
        "SetPlayerTexturePack",
        description="Sets the texture pack for a player",
        version="v1.0.0"
    )
    class SetPlayerTexturePackCommand(AbstractCommand["EnvMapAspectModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["setplayertexture"],
                OP=True
            )

        async def execute(self, ctx: Player, textureUrl: Optional[str] = None, player: Optional[Player] = None):
            # If no player is passed, use the sender
            if player is None:
                player = ctx

            # Set texture pack
            await EnvMapAspectModule.setTexturePack(player, textureUrl)

            # Notify Sender
            await ctx.sendMessage(f"&aSet Texture Pack for {player.username} to {textureUrl}")

    # World Metadata for map aspects
    class EnvMapAspectMetadata(WorldMetadata):
        def __init__(self):
            self.sideBlock: AbstractBlock = Blocks.BEDROCK
            self.edgeBlock: AbstractBlock = Blocks.STATIONARYWATER
            self.edgeHeight: int = 0
            self.cloudHeight: int = 0
            self.maxFog: int = 0
            self.cloudSpeed: float = 1.0
            self.weatherSpeed: float = 1.0
            self.weatherFade: float = 1.0
            self.exponentialFog: int = 0
            self.mapEdgeOffset: int = -2
            self.skyboxHorizontalSpeed: float = 0.0
            self.skyboxVerticalSpeed: float = 0.0

        def setMapAspect(self, aspectType: AspectPropertyType, value):
            # Get attribute name and type from map
            attrName, attrType = _AspectPropertyAttributeMap[aspectType]

            # Check if value is of the correct type
            if not isinstance(value, attrType):
                raise TypeError(f"Value {value} for {aspectType.name} is not of type {attrType}")

            # Set attribute
            setattr(self, attrName, value)

        def getMapAspect(self, aspectType: AspectPropertyType):
            # Get attribute name from map
            attrName, _ = _AspectPropertyAttributeMap[aspectType]

            # Get attribute
            return getattr(self, attrName)

        def setBulkMapAspect(
            self,
            sideBlock: AbstractBlock,
            edgeBlock: AbstractBlock,
            edgeHeight: int,
            cloudHeight: int,
            maxFog: int,
            cloudSpeed: float,
            weatherSpeed: float,
            weatherFade: float,
            exponentialFog: int,
            mapEdgeOffset: int,
            skyboxHorizontalSpeed: float,
            skyboxVerticalSpeed: float
        ):
            self.sideBlock = sideBlock
            self.edgeBlock = edgeBlock
            self.edgeHeight = edgeHeight
            self.cloudHeight = cloudHeight
            self.maxFog = maxFog
            self.cloudSpeed = cloudSpeed
            self.weatherSpeed = weatherSpeed
            self.weatherFade = weatherFade
            self.exponentialFog = exponentialFog
            self.mapEdgeOffset = mapEdgeOffset
            self.skyboxHorizontalSpeed = skyboxHorizontalSpeed
            self.skyboxVerticalSpeed = skyboxVerticalSpeed

        def getBulkMapAspect(self) -> tuple[
            AbstractBlock,
            AbstractBlock,
            int,
            int,
            int,
            float,
            float,
            float,
            int,
            int,
            float,
            float
        ]:
            return (
                self.sideBlock,
                self.edgeBlock,
                self.edgeHeight,
                self.cloudHeight,
                self.maxFog,
                self.cloudSpeed,
                self.weatherSpeed,
                self.weatherFade,
                self.exponentialFog,
                self.mapEdgeOffset,
                self.skyboxHorizontalSpeed,
                self.skyboxVerticalSpeed
            )

    # World Metadata for World Appearance
    class EnvMapAppearanceMetadata(WorldMetadata):
        def __init__(self):
            self.texturePack: Optional[str] = None

        def setTexturePack(self, texturePack: Optional[str]):
            self.texturePack = texturePack

        def getTexturePack(self):
            return self.texturePack

    # Config for default map aspects
    @dataclass
    class EnvMapAspectConfig(AbstractConfig):
        defaultSideBlock: int = 7
        defaultEdgeBlock: int = 8
        automaticallySetEdgeHeight: bool = True
        defaultEdgeHeight: int = 128
        automaticallySetCloudHeight: bool = True
        defaultCloudHeight: Optional[int] = 258
        defaultMaxFog: int = 0
        defaultCloudSpeed: float = 1.0
        defaultWeatherSpeed: float = 1.0
        defaultWeatherFade: float = 1.0
        defaultExponentialFog: int = 0
        defaultMapEdgeOffset: int = -2
        defaultSkyboxHorizontalSpeed: float = 0.0
        defaultSkyboxVerticalSpeed: float = 0.0
        defaultTexturePack: Optional[str] = None
