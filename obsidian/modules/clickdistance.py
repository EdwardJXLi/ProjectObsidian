from obsidian.module import Module, AbstractModule, Dependency, Modules
from obsidian.cpe import CPE, CPEExtension
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player, WorldPlayerManager
from obsidian.packet import ResponsePacket, AbstractResponsePacket, Packets
from obsidian.world import World, WorldMetadata
from obsidian.worldformat import WorldFormatManager, WorldFormats
from obsidian.config import AbstractConfig
from obsidian.mixins import Inject, InjectionPoint, InjectMethod
from obsidian.errors import CPEError, CommandError
from obsidian.log import Logger

from dataclasses import dataclass
from typing import Optional, Any, cast
import struct


@Module(
    "ClickDistance",
    description="Extend or restrict the distance at which client may click blocks",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="ClickDistance",
    extVersion=1,
    cpeOnly=True
)
class ClickDistanceModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.ClickDistanceConfig)

    def postInit(self):
        super().postInit()

        # Create readers and writers for ObsidianWorld
        def readClickDistance(data: dict):
            clickDistanceMetadata = ClickDistanceModule.ClickDistanceMetadata()

            # Read click distance
            clickDistanceMetadata.distance = data["distance"]

            return clickDistanceMetadata

        def writeClickDistance(distanceMetadata: ClickDistanceModule.ClickDistanceMetadata):
            return {"distance": distanceMetadata.distance}

        # Register readers and writers
        WorldFormatManager.registerMetadataReader(WorldFormats.ObsidianWorld, "CPE", "clickDistance", readClickDistance)
        WorldFormatManager.registerMetadataWriter(WorldFormats.ObsidianWorld, "CPE", "clickDistance", writeClickDistance)

        # If ClassicWorld is installed, create readers and writers for ClassicWorld
        if "ClassicWorld" in WorldFormats:
            from obsidian.modules.nbtlib import NBTLib

            # Create readers and writers for ClassicWorld
            def cwReadClickDistance(data: NBTLib.TAG_Compound):
                clickDistanceMetadata = ClickDistanceModule.ClickDistanceMetadata()

                # Check if ExtensionVersion is supported
                # Some software (cough classicube) has this missing, so check if it exists first
                if "ExtensionVersion" in data and data["ExtensionVersion"].value != 1:
                    raise CPEError(f"ClassicWorld ClickDistance ExtensionVersion {data['ExtensionVersion'].value} is not supported!")

                # Read click distance
                clickDistanceMetadata.distance = data["Distance"].value

                return clickDistanceMetadata

            def cwWriteClickDistance(distanceMetadata: ClickDistanceModule.ClickDistanceMetadata):
                metadataNbt = NBTLib.TAG_Compound(name="ClickDistance")

                # Write version info
                metadataNbt.tags.append(NBTLib.TAG_Short(name="ExtensionVersion", value=1))

                # Write click distance
                metadataNbt.tags.append(NBTLib.TAG_Short(name="Distance", value=distanceMetadata.distance))

                return metadataNbt

            # Register readers and writers
            WorldFormatManager.registerMetadataReader(WorldFormats.ClassicWorld, "CPE", "clickDistance", cwReadClickDistance)
            WorldFormatManager.registerMetadataWriter(WorldFormats.ClassicWorld, "CPE", "clickDistance", cwWriteClickDistance)

        # Create helper function to set click distance of a player
        @InjectMethod(target=Player)
        async def setClickDistance(self, distance: int):
            # Since we are injecting, set type of self to Player
            self = cast(Player, self)

            # Check if player supports the ClickDistance Extension
            if not self.supports(CPEExtension("ClickDistance", 1)):
                raise CPEError(f"Player {self.name} Does Not Support ClickDistance Extension!")

            Logger.info(f"Setting click distance to {distance} for {self.username}", module="clickdistance")
            await self.networkHandler.dispatcher.sendPacket(Packets.Response.SetClickDistance, distance)

        # Create helper function to set click distance of a world
        @InjectMethod(target=World)
        async def setWorldClickDistance(self, distance: int, notifyPlayers: bool = True):
            # Since we are injecting, set type of self to Player
            self = cast(World, self)

            # Get the click distance metadata
            # Using cast to ignore type of world, as clickDistance is injected
            clickDistanceMetadata: ClickDistanceModule.ClickDistanceMetadata = cast(Any, self).clickDistance

            # Set click distance
            clickDistanceMetadata.distance = distance

            # If notifyPlayers is True, notify players of the change
            if notifyPlayers:
                for player in self.playerManager.getPlayers():
                    # Only send click distance to players that support the ClickDistance Extension
                    if player.supports(CPEExtension("ClickDistance", 1)):
                        # Using cast to ignore type of player, as setClickDistance is injected
                        await cast(Any, player).setClickDistance(distance)

        # Send player click distance on join
        @Inject(target=WorldPlayerManager.joinPlayer, at=InjectionPoint.AFTER)
        async def sendClickDistance(self, player: Player):
            # Since we are injecting, set type of self to WorldPlayerManager
            self = cast(WorldPlayerManager, self)

            # Check if player supports the ClickDistance Extension
            if player.supports(CPEExtension("ClickDistance", 1)):
                # Send click distance packet to player
                # Using cast to ignore type of player, as setClickDistance is injected
                # Using cast to ignore type of self.world, as clickDistance is injected
                await cast(Any, player).setClickDistance(cast(Any, self.world).clickDistance.distance)

        # Load click distance during world load
        @Inject(target=World.__init__, at=InjectionPoint.AFTER)
        def loadWorldClickDistance(self, *args, **kwargs):
            # Since we are injecting, set type of self to World
            self = cast(World, self)

            # Get default click distance from config
            defaultClickDistance = cast(ClickDistanceModule, Modules.ClickDistance).config.defaultClickDistance

            # If "clickDistance" metadata is not present, create it
            if self.additionalMetadata.get(("CPE", "clickDistance")) is None:
                clickDistanceMetadata = ClickDistanceModule.ClickDistanceMetadata()
                clickDistanceMetadata.setClickDistance(defaultClickDistance)
                self.additionalMetadata[("CPE", "clickDistance")] = clickDistanceMetadata

            # Set click distance
            # Using cast to ignore type of self, as clickDistance is injected
            cast(Any, self).clickDistance = self.additionalMetadata[("CPE", "clickDistance")]

    # Packet to send to clients to change click distance
    @ResponsePacket(
        "SetClickDistance",
        description="Changes player click distance. Set to 0 to disable clicking.",
    )
    class SetClickDistancePacket(AbstractResponsePacket["ClickDistanceModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x12,
                FORMAT="!Bh",
                CRITICAL=False
            )

        async def serialize(self, distance: int):
            # <Set Click Distance Packet>
            # (Byte) Packet ID
            # (Short) Click Distance
            msg = struct.pack(self.FORMAT, self.ID, distance)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # Command to get and set an individual player's click distance.
    @Command(
        "ClickDistance",
        description="Gets or sets the click distance for a player",
        version="v1.0.0"
    )
    class ClickDistanceCommand(AbstractCommand["ClickDistanceModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["clickdistance", "setclickdistance", "cd"],
                OP=True
            )

        async def execute(self, ctx: Player, player: Optional[Player] = None, distance: Optional[int] = None):
            # If no player is specified, set the distance for the sender
            if player is None:
                player = ctx

            # Check if player supports the ClickDistance Extension
            if not player.supports(CPEExtension("ClickDistance", 1)):
                raise CommandError(f"Player {player.name} Does Not Support ClickDistance Extension!")

            # Check if distance is specified. If not, then simply print the click distance
            if distance is None:
                return await ctx.sendMessage("&eTo get the click distance of a world, use &d/worldclickdistance")

            # Send click distance to player
            # Using cast to ignore type of player, as setClickDistance is injected
            await cast(Any, player).setClickDistance(distance)

            # Notify Sender
            await ctx.sendMessage(f"&aSet click distance for {player.username} to {distance}")
            await ctx.sendMessage("&3NOTE: This is not permanent and will reset on log out.")
            await ctx.sendMessage("&3To make this change permanent, use &e/worldclickdistance")

    # Command to reset a player's click distance to the default
    @Command(
        "ResetClickDistance",
        description="Resets the click distance for a player to the default",
        version="v1.0.0"
    )
    class ResetClickDistanceCommand(AbstractCommand["ClickDistanceModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["resetclickdistance"],
                OP=True
            )

        async def execute(self, ctx: Player, player: Optional[Player] = None):
            # If no player is specified, set the distance for the sender
            if player is None:
                player = ctx

            # Check if player supports the ClickDistance Extension
            if not player.supports(CPEExtension("ClickDistance", 1)):
                raise CommandError(f"Player {player.name} Does Not Support ClickDistance Extension!")

            # Get the default click distance
            defaultClickDistance = self.module.config.defaultClickDistance

            # Send click distance to player
            # Using cast to ignore type of player, as setClickDistance is injected
            await cast(Any, player).setClickDistance(defaultClickDistance)

            # Notify Sender
            await ctx.sendMessage(f"&aReset click distance for {player.username} to {defaultClickDistance}")

    # Command to get and set the world click distance
    @Command(
        "WorldClickDistance",
        description="Gets and sets the click distance for the world",
        version="v1.0.0"
    )
    class WorldClickDistanceCommand(AbstractCommand["ClickDistanceModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["worldclickdistance", "setworldclickdistance", "wcd"],
                OP=True
            )

        async def execute(self, ctx: Player, world: Optional[World] = None, distance: Optional[int] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Check if distance is specified. If not, then simply print the click distance
            if distance is None:
                # Using cast to ignore type of world, as clickDistance is injected
                return await ctx.sendMessage(f"&aClick distance for world {world.name} is {cast(Any, world).clickDistance.distance}")

            # Set world click distance
            # Using cast to ignore type of world, as setWorldClickDistance is injected
            await cast(Any, world).setWorldClickDistance(distance, notifyPlayers=True)

            # Notify Sender
            await ctx.sendMessage(f"&aSet click distance for world {world.name} to {distance}")

    # Command to reset world click distance
    @Command(
        "ResetWorldClickDistance",
        description="Resets the click distance for the world to the default",
        version="v1.0.0"
    )
    class ResetWorldClickDistanceCommand(AbstractCommand["ClickDistanceModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ACTIVATORS=["resetworldclickdistance"],
                OP=True
            )

        async def execute(self, ctx: Player, world: Optional[World] = None):
            # If no world is passed, use players current world
            if world is None:
                if ctx.worldPlayerManager is not None:
                    world = ctx.worldPlayerManager.world
                else:
                    raise CommandError("You are not in a world!")

            # Get the default click distance
            defaultClickDistance = self.module.config.defaultClickDistance

            # Set world click distance
            # Using cast to ignore type of world, as setWorldClickDistance is injected
            await cast(Any, world).setWorldClickDistance(defaultClickDistance, notifyPlayers=True)

            # Notify Sender
            await ctx.sendMessage(f"&aReset click distance for world {world.name} to {defaultClickDistance}")

    # World Metadata for click distance
    class ClickDistanceMetadata(WorldMetadata):
        def __init__(self):
            self.distance: int = 160

        def setClickDistance(self, distance: int):
            self.distance = distance

        def getClickDistance(self):
            return self.distance

    # Config for default click distance
    @dataclass
    class ClickDistanceConfig(AbstractConfig):
        defaultClickDistance: int = 160
