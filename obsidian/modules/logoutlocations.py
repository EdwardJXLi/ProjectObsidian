from obsidian.module import Module, AbstractModule, Dependency
from obsidian.player import Player, WorldPlayerManager
from obsidian.world import World, WorldMetadata
from obsidian.worldformat import WorldFormatManager, WorldFormats
from obsidian.mixins import Inject, InjectionPoint, Override
from obsidian.log import Logger

from typing import Callable, Awaitable, Optional, cast


@Module(
    "LogoutLocations",
    description="Respawns players at the last location they logged out at.",
    author="RadioactiveHydra",
    version="1.0.0",
    dependencies=[Dependency("core")],
    soft_dependencies=[Dependency("classicworld")]
)
class LogoutLocationsModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    def initMetadata(self):
        # Create readers and writers for ObsidianWorld
        def readLogoutLocation(data: dict):
            logoutLocations = LogoutLocationMetadata()

            # Loop through all players and load logout location
            Logger.debug("Loading Logout Locations", module="logout-location")
            for player, coords in data.items():
                logX = coords["X"]
                logY = coords["Y"]
                logZ = coords["Z"]
                logYaw = coords["Yaw"]
                logPitch = coords["Pitch"]
                logoutLocations.setLogoutLocation(player, logX, logY, logZ, logYaw, logPitch)
                Logger.debug(f"Loaded Logout Location x:{logX}, y:{logY}, z:{logZ}, yaw:{logYaw}, pitch:{logPitch} for player {player}", module="logout-location")

            return logoutLocations

        def writeLogoutLocation(logoutLocations: LogoutLocationMetadata):
            data: dict = {}

            # Loop through all logout locations and save them
            Logger.debug("Saving Logout Locations", module="logout-location")
            for player, coords in logoutLocations.getAllLogoutLocations().items():
                logX, logY, logZ, logYaw, logPitch = coords
                data[player] = {
                    "X": logX,
                    "Y": logY,
                    "Z": logZ,
                    "Yaw": logYaw,
                    "Pitch": logPitch
                }
                Logger.debug(f"Saved Logout Location x:{logX}, y:{logY}, z:{logZ}, yaw:{logYaw}, pitch:{logPitch} for player {player}", module="logout-location")

            return data

        # Register readers and writers
        WorldFormatManager.registerMetadataReader(WorldFormats.ObsidianWorld, "obsidian", "logoutLocations", readLogoutLocation)
        WorldFormatManager.registerMetadataWriter(WorldFormats.ObsidianWorld, "obsidian", "logoutLocations", writeLogoutLocation)

        # If ClassicWorld is installed, create readers and writers for ClassicWorld
        if "ClassicWorld" in WorldFormats:
            from obsidian.modules.nbtlib import NBTLib

            # Create readers and writers for LogoutLocation
            def readLogoutLocationCW(data: NBTLib.TAG_Compound):
                logoutLocations = LogoutLocationMetadata()

                # Loop through all players and load logout location
                Logger.debug("Loading Logout Locations", module="logout-location")
                for player, coords in data.items():
                    logX = coords["X"].value
                    logY = coords["Y"].value
                    logZ = coords["Z"].value
                    logYaw = coords["H"].value
                    logPitch = coords["P"].value
                    logoutLocations.setLogoutLocation(player, logX, logY, logZ, logYaw, logPitch)
                    Logger.debug(f"Loaded Logout Location x:{logX}, y:{logY}, z:{logZ}, yaw:{logYaw}, pitch:{logPitch} for player {player}", module="logout-location")

                return logoutLocations

            def writeLogoutLocationCW(logoutLocations: LogoutLocationMetadata):
                data: NBTLib.TAG_Compound = NBTLib.TAG_Compound(name="logoutLocations")

                # Loop through all logout locations and save them
                Logger.debug("Saving Logout Locations", module="logout-location")
                for player, coords in logoutLocations.getAllLogoutLocations().items():
                    logX, logY, logZ, logYaw, logPitch = coords
                    playerData = NBTLib.TAG_Compound(name=player)
                    playerData.tags.append(NBTLib.TAG_Short(name="X", value=logX))
                    playerData.tags.append(NBTLib.TAG_Short(name="Y", value=logY))
                    playerData.tags.append(NBTLib.TAG_Short(name="Z", value=logZ))
                    playerData.tags.append(NBTLib.TAG_Short(name="H", value=logYaw))
                    playerData.tags.append(NBTLib.TAG_Short(name="P", value=logPitch))
                    data.tags.append(playerData)
                    Logger.debug(f"Saved Logout Location x:{logX}, y:{logY}, z:{logZ}, yaw:{logYaw}, pitch:{logPitch} for player {player}", module="logout-location")

                return data

            # Register readers and writers
            WorldFormatManager.registerMetadataReader(WorldFormats.ClassicWorld, "obsidian", "logoutLocations", readLogoutLocationCW)
            WorldFormatManager.registerMetadataWriter(WorldFormats.ClassicWorld, "obsidian", "logoutLocations", writeLogoutLocationCW)

    def initMixins(self):
        # Send player logout location on join
        @Override(target=WorldPlayerManager.joinPlayer, passSuper=True)
        async def sendLastLogout(
            self,
            player: Player,
            spawn: Optional[tuple[int, int, int, int, int]] = None,
            *,  # Get additional contexts
            _super: Callable[..., Awaitable]
        ):
            # Since we are injecting, set type of self to WorldPlayerManager
            self = cast(WorldPlayerManager, self)

            # If spawn is set, ignore logout location
            if spawn:
                return await _super(self, player, spawn=spawn)
            else:
                # Get the logoutLocation metadata
                logoutLocation: LogoutLocationMetadata = getattr(self.world, "logoutLocations")

                # Get the player's logout location -> Can either return tuple of (x, y, z, yaw, pitch) or None
                playerLogoutLocation = logoutLocation.getLogoutLocation(player.name)

                # Continue with normal joinPlayer
                return await _super(self, player, spawn=playerLogoutLocation)

        # Save player logout location on leave
        @Inject(target=WorldPlayerManager.removePlayer, at=InjectionPoint.BEFORE)
        async def saveLastLogout(self, player: Player, *args, **kwargs):
            # Since we are injecting, set type of self to WorldPlayerManager
            self = cast(WorldPlayerManager, self)

            # Get the logoutLocation metadata
            logoutLocation: LogoutLocationMetadata = getattr(self.world, "logoutLocations")

            # Write last logout location for player
            logoutLocation.setLogoutLocation(player.name, player.posX, player.posY, player.posZ, player.posYaw, player.posPitch)
            Logger.debug(f"Saved Player {player.name} Last Logout Location {player.posX}, {player.posY}, {player.posZ}, {player.posYaw}, {player.posPitch}", module="logoutlocation")

        # Load player logout during world load
        @Inject(target=World.__init__, at=InjectionPoint.AFTER)
        def loadWorldLastLogout(self, *args, **kwargs):
            # Since we are injecting, set type of self to World
            self = cast(World, self)

            # Check if last logout location metadata exists. If not, create it
            if ("obsidian", "logoutLocations") not in self.additionalMetadata:
                Logger.debug("Creating Last Logout Location Metadata", module="world-init")
                self.additionalMetadata[("obsidian", "logoutLocations")] = LogoutLocationMetadata()

            # Create a quick reference to the last logout location metadata
            logoutLocations = cast(LogoutLocationMetadata, self.additionalMetadata[("obsidian", "logoutLocations")])
            Logger.debug(f"Loaded Last Logout Positions. {logoutLocations.getAllLogoutLocations()}", module="world-init")

            # Inject logout location metadata into WorldPlayerManager
            setattr(self, "logoutLocations", logoutLocations)

    def postInit(self):
        super().postInit()

        # Set up metadata handlers
        self.initMetadata()

        # Set up mixins
        self.initMixins()


class LogoutLocationMetadata(WorldMetadata):
    def __init__(self):
        self.logoutLocations: dict[str, tuple[int, int, int, int, int]] = dict()

    def setLogoutLocation(self, name: str, x: int, y: int, z: int, yaw: int, pitch: int):
        self.logoutLocations[name] = (x, y, z, yaw, pitch)

    def getLogoutLocation(self, name: str):
        if name in self.logoutLocations:
            return self.logoutLocations[name]
        else:
            return None

    def getAllLogoutLocations(self):
        return self.logoutLocations

    def __getitem__(self, name: str):
        return self.getLogoutLocation(name)

    def __contains__(self, name: str):
        return name in self.logoutLocations
