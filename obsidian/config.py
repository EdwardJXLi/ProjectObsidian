from __future__ import annotations

from dataclasses import dataclass, field, asdict, InitVar
from typing import List, Optional, Tuple
from pathlib import Path
import io
import json
import copy

from obsidian.constants import SERVERPATH
from obsidian.log import Logger


@dataclass
class AbstractConfig:
    name: str  # Name of the config (for debugging)
    configPath: Path = Path()  # Path Location Of Config File (Used for reloads)
    saveAfterConfigLoad: bool = True  # Override Flag To Enable/Disable Config Saving After Load
    configOverrides: List[str] = field(default_factory=list)  # List of configs to ignore while loading and writing configs
    autoSave: bool = True
    # Init Vars (Temporary and will not be duplicated)
    rootPath: InitVar[Path] = Path("configs")
    ignoreValues: InitVar[tuple] = tuple()
    autoInit: InitVar[bool] = False
    hideWarning: InitVar[bool] = False

    def __post_init__(
        self,
        rootPath: Path,
        ignoreValues: Tuple[str],
        autoInit: bool,
        hideWarning: bool
    ):
        Logger.debug(f"Setting Up Config With Name: {self.name}, Root Path: {rootPath}", module="Config")

        # Generate Filename and Paths
        fileName: str = self.name + ".json"

        # Generate Config Paths
        self.configPath: Path = Path(SERVERPATH, rootPath, fileName)
        Logger.debug(f"Config {self.name} has save path {self.configPath}", module="Config")

        # Load Other Variables
        self.configOverrides: List[str] = [
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
        self.reload()

    # Reload; Reset Information From File
    def reload(self):
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
                Logger.error(f"Failed To Load Json File! - {type(e).__name__}: {e}", "config")
                Logger.askConfirmation(message="Override Old Config With Default Values?")
                with open(self.configPath, "w") as configFile:
                    self._save(configFile)
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
                Logger.warn(f"Trying To Apply Non-Existant Config Override Key {overrideKey}", "config-save")

        # Writing Dict (as JSON) To File
        Logger.debug("Writing Formatted Config To File", "config-save")
        Logger.verbose(f"Formatted Config Is {configData}", "config-save")
        json.dump(configData, fileIO, indent=4)

    def to_dict(self):
        # Converts the config to a dict.
        return asdict(self)

    def to_json(self):
        # Converts the config to a json string.
        return json.dumps(self.to_dict())

    def to_file(self, filename: Path):
        # Writes the config to a file.
        with open(filename, "w") as f:
            f.write(self.to_json())


@dataclass
class ServerConfig(AbstractConfig):
    # Module Configuration
    moduleBlacklist: List[str] = field(default_factory=list)  # Module Init Blacklist
    # Network Configuration
    ipBlacklist: List[str] = field(default_factory=list)  # List Of Ips To Block Connection
    # Chat Configuration
    playerChatColor: str = "&a"
    operatorChatColor: str = "&4"
    # World Configuration
    operatorsList: List[str] = field(default_factory=list)  # List Of Operators
    worldSaveLocation: Optional[str] = "worlds"  # Location of Save Folder
    defaultWorld: str = "default"  # Name Of Default World
    serverMaxPlayers: int = 128  # Number Of Players Max Allowed On The Entire Server
    worldMaxPlayers: int = 128  # Number Of Players Max Allowed In One World
    defaultGenerator: str = "Flat"  # Name Of Default Map/World Generator
    defaultWorldSizeX: int = 256  # Default Size X
    defaultWorldSizeY: int = 256  # Default Size Y
    defaultWorldSizeZ: int = 256  # Default Size Z
    defaultSaveFormat: str = "raw"  # Name Of Default World Save Format
    checkValidSpawn: bool = True  # Check if the world spawn is valid. If not, generate new one!
    gzipCompressionLevel: int = 9  # Int Containing Level Of Gzip Compression
    worldBlacklist: List[str] = field(default_factory=list)  # World Init Blacklist
    defaultMOTD: List[str] = field(default_factory=lambda: ["&aServer Powered By Obsidian"])  # Default MOTD
