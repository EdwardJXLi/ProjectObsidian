from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ServerConfig:
    # Meta Tags
    configPath: Optional[str] = None  # Path Location Of Config File (Used for reloads)
    # Module Configuration
    moduleBlacklist: List[str] = field(default_factory=list)  # Module Init Blacklist
    # Network Configuration
    ipBlacklist: List[str] = field(default_factory=list)  # List Of Ips To Block Connection
    # World Configuration
    worldSaveLocation: Optional[str] = "worlds"  # Location of Save Folder
    defaultWorld: str = "raw"  # Name Of Default World
    defaultGenerator: str = "Flat"  # Name Of Default Map/World Generator
    defaultSaveFormat: str = "basic"  # Name Of Default World Save Format
    gzipCompressionLevel: int = 9  # Int Containing Level Of Gzip Compression
    worldBlacklist: List[str] = field(default_factory=list)  # World Init Blacklist

    # Provide Alias For First Time Reload (Init)
    def init(self):
        self.reload()

    # Reload; Reset Information From File
    def reload(self):
        # TODO
        raise NotImplementedError("Server Config Loading Is Not Implemented")
