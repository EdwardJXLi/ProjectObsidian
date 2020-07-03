from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server
    from obsidian.world import World
    from obsidian.network import NetworkHandler

# from typing import Dict

from obsidian.constants import ServerError, WorldError, ClientError
from obsidian.log import Logger


# The Overall Server Player Manager
class PlayerManager:
    def __init__(self, server: Server):
        self.server = server
        self.players = dict()  # Key: Asyncio Network Data

    async def createPlayer(self, network: NetworkHandler, username: str, verificationKey: str):
        Logger.debug(f"Creating Player For Ip {network.ip}", module="player")
        # Creating Player Class
        player = Player(self, network, username, verificationKey)
        # Adding Player Class
        if network.ip not in self.players.keys():
            self.players[network.ip] = player
            return player
        else:
            raise ServerError(f"Player {network.ip} is already registered! This should not happen!")

    async def deletePlayer(self):
        pass


# The Specific Player Manager Per World
class WorldPlayerManager:
    def __init__(self, world: World):
        self.world = world
        self.players = dict()  # Key: Player ID
        self.idAllocator = playerIdAllocator(maxIds=self.world.maxPlayers)

    def joinPlayer(self, player: Player):
        # Trying To Allocate Id
        # Fails If All Slots Are Taken
        try:
            playerId = self.idAllocator.allocateId()
        except WorldError:
            raise ClientError(f"World {self.world.name} Is Full")

        # Adding Player To Players List Using Id
        self.players[playerId] = player
        Logger.debug(f"Player {player.networkHandler.ip} Username {player.name} Id {playerId} Joined World {self.world.name}", module="world-player")


class Player:
    def __init__(self, playerManager: PlayerManager, networkHandler: NetworkHandler, name, key):
        self.name = name
        self.verificationKey = key
        self.playerManager = playerManager
        self.networkHandler = networkHandler
        self.worldPlayerManager = None

    def joinWorld(self, world: World):
        Logger.debug(f"Player {self.name} Joining World {world.name}", module="player")
        # Attaching Player Onto World Player Manager
        world.playerManager.joinPlayer(self)


class playerIdAllocator:
    def __init__(self, maxIds=255):
        self.maxIds = maxIds
        self.ids = [False] * self.maxIds  # Create Array Of `False` With Length maxIds

    def allocateId(self):
        # Loop Through All Ids, Return Id That Is Not Free
        Logger.debug("Trying To Allocate Id", module="player")
        for idIndex, allocatedStatus in enumerate(self.ids):
            if allocatedStatus is False:
                # Set Flag To True And Return Id
                self.ids[idIndex] = True
                return idIndex

        raise WorldError("Id Allocator Failed To Allocate Open Id")

    def deallocateId(self, id: int):
        # TODO
        self.ids[id] = False
