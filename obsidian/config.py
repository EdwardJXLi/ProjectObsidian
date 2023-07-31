from __future__ import annotations

from dataclasses import dataclass, field, asdict, InitVar
from typing import Optional
from pathlib import Path
import io
import json
import copy

from obsidian.constants import SERVER_PATH
from obsidian.types import UsernameType, IpType
from obsidian.log import Logger


@dataclass
class AbstractConfig:
    name: str  # Name of the config (for debugging)
    configPath: Path = Path()  # Path Location Of Config File (Used for reloads)
    saveAfterConfigLoad: bool = True  # Override Flag To Enable/Disable Config Saving After Load
    configOverrides: list[str] = field(default_factory=list)  # List of configs to ignore while loading and writing configs
    # autoSave: bool = True  # Not Implemented
    # Init Vars (Temporary and will not be duplicated)
    rootPath: InitVar[Path] = Path("configs")
    ignoreValues: InitVar[list] = list()
    autoInit: InitVar[bool] = False
    hideWarning: InitVar[bool] = False

    def __post_init__(
        self,
        rootPath: Path,
        ignoreValues: list[str],
        autoInit: bool,
        hideWarning: bool
    ):
        Logger.debug(f"Setting Up Config With Name: {self.name}, Root Path: {rootPath}", module="Config")

        if ".json" not in self.name:
            # Generate Filename and Paths
            fileName: str = self.name + ".json"
        else:
            fileName: str = self.name

        # Generate Config Paths
        self.configPath: Path = Path(SERVER_PATH, rootPath, fileName)
        Logger.debug(f"Config {self.name} has save path {self.configPath}", module="Config")

        # Load Other Variables
        self.configOverrides: list[str] = [
            "name",
            "configPath",
            "saveAfterConfigLoad",
            "configOverrides"
        ] + list(ignoreValues)

        if not hideWarning:
            Logger.warn(f"Config {self.name} Is Being Loaded Manually. Please Use self.initConfig To Load Config.", "config")
            Logger.warn("If you know what you are doing, set hideWarning to hide this warning.", "config")

        if autoInit:
            Logger.debug("Auto Initializing Config", module="Config")
            self.init()

        return self

    # Server-Boot Init of Config
    def init(self):
        self.reload(attemptRecovery=True)

    # Reload; Reset Information From File
    def reload(self, attemptRecovery: bool = False):
        Logger.debug(f"Reloading Config {self.name}", "config")
        # Make sure folder path exists
        self.configPath.parent.mkdir(parents=True, exist_ok=True)
        # Load File If File
        if self.configPath.is_file():
            Logger.debug("Config File Exists! Loading Config.", "config")
            try:
                with open(self.configPath, "r") as configFile:
                    self._load(configFile)
                # Save Config After Load (To Update And Fix Any Issues)
                if self.saveAfterConfigLoad:
                    with open(self.configPath, "w") as configFile:
                        self._save(configFile)
                else:
                    Logger.info("Skipping Save After Config Load", "config")
            except json.decoder.JSONDecodeError as e:
                if attemptRecovery:
                    Logger.error(f"Failed To Load Json File! - {type(e).__name__}: {e}", "config")
                    Logger.askConfirmation(message="Override Old Config With Default Values?")
                    with open(self.configPath, "w") as configFile:
                        self._save(configFile)
                else:
                    raise e
        else:
            Logger.debug("Config File Does Not Exist! Creating Config File.", "config")
            with open(self.configPath, "w") as configFile:
                self._save(configFile)

    # Save Config To File
    def save(self):
        Logger.debug(f"Saving Config {self.name}", "config")
        # Make sure folder path exists
        self.configPath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.configPath, "w") as configFile:
            self._save(configFile)

    def _load(self, fileIO: io.TextIOWrapper):
        Logger.debug(f"Loading Config With FileIO {fileIO}", "config-load")
        # Set Internal Attributes If It Exists
        configData = json.load(fileIO)
        Logger.verbose(f"Config data Is {configData}", "config-load")
        for configKey, configValue in configData.items():
            Logger.verbose(f"Checking Config Attribute {configKey}", "config-load")
            # Checking If Key Exists In Config AND If Its Not Part Of The Overrides
            if hasattr(self, configKey) and configKey not in self.configOverrides:
                Logger.verbose(f"Setting Config Attribute {configKey} to {configValue}", "config-load")
                setattr(self, configKey, configValue)
            else:
                Logger.warn(f"Ignoring Unknown Config Attribute {configKey}", "config-load")
        Logger.verbose(f"Config Loaded With: {self.to_dict()}", "config-load")

    def _save(self, fileIO: io.TextIOWrapper):
        Logger.debug(f"Saving Config With FileIO {fileIO}", "config-save")
        # Write Config Values To File (Except ConfigOverrides)
        # Create A Shallow Copy Dict Version Of Dataclass
        configData = copy.copy(asdict(self))

        # Remove All configOverrides Values
        Logger.debug("Applying Config Overrides", "config-save")
        configOverrides = copy.copy(configData["configOverrides"])
        for overrideKey in configOverrides:
            Logger.debug(f"Applying Config Override {overrideKey}", "config-save")
            if overrideKey in configData.keys():
                del configData[overrideKey]
            else:
                Logger.warn(f"Trying To Apply Non-Existent Config Override Key {overrideKey}", "config-save")

        # Writing Dict (as JSON) To File
        Logger.debug("Writing Formatted Config To File", "config-save")
        Logger.verbose(f"Formatted Config Is {configData}", "config-save")
        json.dump(configData, fileIO, indent=4)
        Logger.verbose(f"Config Saved With: {self.to_dict()}", "config-load")

    def to_dict(self) -> dict:
        # Converts the config to a dict.
        return asdict(self)


@dataclass
class ServerConfig(AbstractConfig):
    # Module Configuration
    moduleIgnoreList: list[str] = field(default_factory=list)  # Module Init Ignore List
    # Server Configuration
    operatorsList: list[UsernameType] = field(default_factory=list)  # List Of Operators
    bannedIps: list[IpType] = field(default_factory=list)  # List Of Ips that are banned (Reject Connection)
    bannedPlayers: list[UsernameType] = field(default_factory=list)  # List Of Usernames that are banned (Reject Connection)
    disabledCommands: list[str] = field(default_factory=list)  # List Of Disabled Commands
    verifyLogin: bool = True  # Flag to determine whether to verify player login with Mojang or Classicube
    # CPE (Classic Protocol Extension) Configuration
    enableCPE: bool = True  # Enable CPE (Classic Protocol Extension)
    # Chat Configuration
    playerChatColor: str = "&a"  # Color Of Player Chat
    operatorChatColor: str = "&4"  # Color Of Operator Chat
    worldChatColor: str = "&9"  # Color Of World Chat Prefix
    globalChatMessages: bool = False  # Send Chat Messages To All Players Across Worlds
    allowPlayerColor: bool = False  # Allow Players To Use Color In Chat
    repeatCommands: bool = False  # Repeat Commands In Chat
    # Block Configuration
    disallowedBlocks: list[int] = field(default_factory=list)  # List Of Disallowed Blocks
    allowLiquidPlacement: bool = False  # Allow Players To Place Liquids
    asynchronousBlockUpdates: bool = True  # Allow Block Updates To Be Asynchronous
    blockUpdatesBeforeReload: int = 8192  # Number of block updates to warrant a reload of the map. -1 to disable
    # World Configuration
    worldSaveLocation: Optional[str] = "worlds"  # Location of Save Folder
    worldIgnoreList: list[str] = field(default_factory=list)  # Worlds to ignore
    newWorldWarning: bool = True  # Whether to warn the user when a new world is created
    persistentWorlds: bool = True  # Override flag to turn off world persistance
    automaticallyDetermineSpawn: bool = False  # Reset Spawn Location for Every Player
    defaultWorld: str = "default"  # Name Of Default World
    serverMaxPlayers: Optional[int] = None  # Number Of Players Max Allowed On The Entire Server
    worldMaxPlayers: Optional[int] = None  # Number Of Players Max Allowed In One World
    defaultGenerator: str = "Flat"  # Name Of Default Map/World Generator
    defaultSaveFormat: str = "ObsidianWorld"  # Name Of Default World Save Format
    backupBeforeSave: bool = True  # Whether to backup the map before saving
    verifyMapAfterSave: bool = True  # Whether to try loading and verifying the map after saving.
    checkValidSpawn: bool = True  # Check if the world spawn is valid. If not, generate new one!
    gzipCompressionLevel: int = 9  # Int Containing Level Of Gzip Compression
    defaultMOTD: list[str] = field(default_factory=lambda: ["&aServer Powered By Obsidian"])  # Default MOTD
    # Logger Configuration
    logBuffer: int = 1  # Number of Log Messages to be buffered before flushed to file
    # Default World Generation Config
    worldSizeX: int = 256  # Default Size X
    worldSizeY: int = 256  # Default Size Y
    worldSizeZ: int = 256  # Default Size Z
    worldSeed: Optional[int] = None
