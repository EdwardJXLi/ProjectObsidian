from dataclasses import dataclass

from obsidian.packet import PacketManager


class _ModuleManagerImplementation():
    def __init__(self):
        self._module_list = {}

    def register(self, name, module):
        obj = module()
        obj.NAME = name
        for _, method in module.__dict__.items():
            if hasattr(method, "obsidian_packet"):
                packet = method.obsidian_packet
                PacketManager.register(packet["name"], packet["direction"], packet["packet"], obj)
        self._module_list[name] = obj

    def __getitem__(self, module):
        return self._module_list[module]

    def __getattr__(self, module):
        return self._module_list[module]


ModuleManager = _ModuleManagerImplementation()
Modules = ModuleManager


@dataclass
class AbstractModule():
    def __init__(self):
        pass


def Module(name):
    def internal(cls):
        ModuleManager.register(name, cls)
    return internal
