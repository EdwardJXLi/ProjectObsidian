# Custom Errors
class InitRegisterError(Exception):
    pass


class ModuleError(Exception):
    pass


class DependencyError(Exception):
    pass


class InitError(Exception):
    pass


class PostInitError(Exception):
    pass


class PacketError(Exception):
    pass


class CommandError(Exception):
    pass


class BlockError(Exception):
    pass


class MapGenerationError(Exception):
    pass


class ServerError(Exception):
    pass


class WorldError(Exception):
    pass


class WorldFormatError(Exception):
    pass


class WorldSaveError(Exception):
    pass


class NetworkError(Exception):
    pass


class ClientError(Exception):
    pass


class FatalError(Exception):
    pass
