from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import os
import io
import json
import copy

from obsidian.constants import SERVERPATH
from obsidian.log import Logger


@dataclass
class ServerConfig:
    # Meta Tags
    configPath: str = "configs/server.json"  # Path Location Of Config File (Used for reloads)
    configOverrides: List[str] = field(default_factory=lambda: ["configPath", "configOverrides"])  # List of configs to ignore while loading and writing configs
    # Module Configuration
    moduleBlacklist: List[str] = field(default_factory=list)  # Module Init Blacklist
    # Config Configuration
    saveAfterConfigLoad: bool = True  # Override Flag To Enable/Disable Config Saving After Load
    # Network Configuration
    ipBlacklist: List[str] = field(default_factory=list)  # List Of Ips To Block Connection
    # World Configuration
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
    defaultMOTD: List[str] = field(default_factory=lambda: ["&aObsidian Server"])  # Default MOTD

    # Server-Boot Init of Config
    def init(self):
        self.reload()

    # Reload; Reset Information From File
    def reload(self):
        Logger.debug("Reloading Config", "config")
        # Check If File Exists
        configPath = os.path.join(SERVERPATH, self.configPath)
        # Load File If File
        if os.path.isfile(configPath):
            Logger.debug("Config File Exists! Loading Config.", "config")
            try:
                with open(configPath, "r") as configFile:
                    self._load(configFile)
                # Save Config After Load (To Update And Fix Any Issues)
                if self.saveAfterConfigLoad:
                    with open(configPath, "w") as configFile:
                        self._save(configFile)
                else:
                    Logger.warn("Skipping Save After Config Load", "config")
            except json.decoder.JSONDecodeError as e:
                Logger.error(f"Failed To Load Json File! - {type(e).__name__}: {e}", "config")
                Logger.askConfirmation(message="Override Old Config With Default Values?")
                with open(configPath, "w") as configFile:
                    self._save(configFile)
        else:
            Logger.debug("Config File Does Not Exist! Creating Config File.", "config")
            with open(configPath, "w") as configFile:
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
