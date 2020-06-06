from dataclasses import dataclass
from obsidian.constants import UndefinedModule

from obsidian.packet import PacketManager


# Module Skeleton
@dataclass
class AbstractModule():
    pass


# Internal Module Manager Singleton
class _ModuleManager():
    def __init__(self):
        # Creates List Of Modules That Has The Module Name As Keys
        self._module_list = {}

    # Registration. Called by Module Decorator
    def register(self, name, module):
        obj = module()  # Create Object
        obj.NAME = name  # Attach Name As Attribute
        for _, item in module.__dict__.items():  # Loop Through All Items In Class
            if hasattr(item, "obsidian_packet"):  # Check If Item Has "obsidian_packet" Flag
                packet = item.obsidian_packet
                # Register Packet Using information Provided By "obsidian_packet"
                PacketManager.register(packet["direction"], packet["name"], packet["packet"], obj)
        self._module_list[name] = obj

    # Handles _ModuleManager["item"]
    def __getitem__(self, module):
        return self._module_list[module]

    # Handles _ModuleManager.item
    def __getattr__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)


# Module Registration Decorator
def Module(name):
    def internal(cls):
        ModuleManager.register(name, cls)
    return internal


# Creates ModuleManager As Singleton
ModuleManager = _ModuleManager()
# Adds Alias To ModuleManager
Modules = ModuleManager
