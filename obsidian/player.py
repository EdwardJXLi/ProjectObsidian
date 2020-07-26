from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server
    from obsidian.world import World
    from obsidian.network import NetworkHandler

from typing import List, Optional, Type, Union

from obsidian.packet import AbstractResponsePacket, Packets
from obsidian.log import Logger
from obsidian.constants import (
    Colour,
    CRITICAL_RESPONSE_ERRORS,
    ServerError,
    WorldError,
    ClientError
)


# The Overall Server Player Manager
class PlayerManager:
    def __init__(self, server: Server, maxSize: int = 1024):
        self.server = server
        self.players = []  # List of players (no order)
        self.maxSize = maxSize

    async def createPlayer(self, network: NetworkHandler, username: str, verificationKey: str):
        Logger.debug(f"Creating Player For Ip {network.ip}", module="player")
        # Creating Player Class
        player = Player(self, network, username, verificationKey)
        # Checking if server is full
        if len(self.players) >= self.maxSize:
            raise ClientError("Server Is Full!")
        # Adding Player Class
        self.players.append(player)
        return player

    async def deletePlayer(self, player: Player):
        Logger.debug(f"Removing Player {player.name}", module="player")
        # Remove Player From World If Necessary
        if player.worldPlayerManager is not None and player.playerId is not None:
            Logger.debug("User Leaving World", module="player")
            await player.worldPlayerManager.removePlayer(player)

        # Remove Player From PlayerManager
        for playerIndex, playerObj in enumerate(self.players):
            if(playerObj.networkHandler.ip == player.networkHandler.ip):
                del self.players[playerIndex]

        Logger.debug(f"Successfully Removed Player {player.name}", module="player")

    async def sendGlobalPacket(self, packet: AbstractResponsePacket, *args, ignoreList: List[Player] = [], **kwargs):
        # Send packet to ALL members connected to server (all worlds)
        Logger.debug(f"Sending Packet {packet.NAME} To All Connected Players", module="player-network")
        # Loop Through All Players
        for player in self.players:
            # Checking if player is not in ignoreList
            if player not in ignoreList:
                try:
                    # Sending Packet To Player
                    await player.networkHandler.dispacher.sendPacket(packet, *args, **kwargs)
                except Exception as e:
                    if e not in CRITICAL_RESPONSE_ERRORS:
                        # Something Broke!
                        Logger.error(f"An Error Occurred While Sending Global Packet {packet.NAME} To {player.networkHandler.ip} - {type(e).__name__}: {e}")
                    else:
                        # Bad Timing with Connection Closure. Ignoring
                        Logger.verbose(f"Ignoring Error While Sending Global Packet {packet.NAME} To {player.networkHandler.ip}")

    async def sendGlobalMessage(
        self,
        message,
        author: Union[None, str, Player] = None,  # Information on the message author
        globalTag: bool = False,  # Flag dictating if the [world] header should be added
        ignoreList: List[Player] = []  # List of players to not send the message not
    ):
        # Format Message To Be Sent
        # Add Author Tag
        if isinstance(author, str):
            message = f"<&e{author}&f> {message}"
        elif isinstance(author, Player):
            # Special Formatting For OPs
            if author.opStatus:
                message = f"<&c{author.name}&f> {message}"
            else:
                message = f"<&b{author.name}&f> {message}"

        # Add Global Tag (If Requested)
        if globalTag:
            message = f"[&7GLOBAL&f] {message}"

        # Finally, send formatted message
        Logger.log(
            message,
            tags=[Logger._getTimestamp(), "chat", "global"],
            colour=Colour.GREEN,
            textColour=Colour.WHITE
        )
        await self.sendGlobalPacket(Packets.Response.SendMessage, message, ignoreList=ignoreList)


# The Specific Player Manager Per World
class WorldPlayerManager:
    def __init__(self, world: World):
        self.world = world
        self.players: List[Optional[Player]] = [None] * world.maxPlayers  # type: ignore

    async def joinPlayer(self, player: Player):
        # Trying To Allocate Id
        # Fails If All Slots Are Taken
        try:
            playerId = self.allocateId()
        except WorldError:
            raise ClientError(f"World {self.world.name} Is Full")

        # Adding Player To Players List Using Id
        Logger.debug(f"Player {player.networkHandler.ip} Username {player.name} Id {playerId} Is Joining World {self.world.name}", module="world-player")
        player.playerId = playerId
        self.players[playerId] = player

        # Set Player Location
        # TODO saving player location
        player.posX = self.world.spawnX
        player.posY = self.world.spawnY
        player.posZ = self.world.spawnZ
        player.posYaw = self.world.spawnYaw
        player.posPitch = self.world.spawnPitch

        # Send Player Join Packet To All Players (Except Joining User)
        await self.sendWorldPacket(
            Packets.Response.SpawnPlayer,
            player.playerId,
            player.name,
            player.posX,
            player.posY,
            player.posZ,
            player.posYaw,
            player.posPitch,
            ignoreList=[player]  # Don't send packet to self!
        )

        # Update User On Currently Connected Players
        await self.spawnCurrentPlayers(player)

        Logger.debug(f"Finished Handling Player Join For {player.name} Id {player.playerId} Joined World {self.world.name}", module="world-player")

        # Sending Join Chat Message
        await self.sendWorldMessage(f"&e{player.name} Joined The World &9(ID {player.playerId})&f")

    async def spawnCurrentPlayers(self, playerSelf: Player):  # Update Joining Players of The Currently In-Game Players
        # Loop Through All Players
        for player in self.players:
            # Checking if Player Exists
            if player is None:
                continue

            # Checking if player is not self
            if player is playerSelf:
                continue

            # Attempting to Send Packet
            try:
                await playerSelf.networkHandler.dispacher.sendPacket(
                    Packets.Response.SpawnPlayer,
                    player.playerId,
                    player.name,
                    player.posX,
                    player.posY,
                    player.posZ,
                    player.posYaw,
                    player.posPitch,
                )
            except Exception as e:
                if e not in CRITICAL_RESPONSE_ERRORS:
                    # Something Broke!
                    Logger.error(f"An Error Occurred While Sending World Packet {Packets.Response.SpawnPlayer.NAME} To {player.networkHandler.ip} - {type(e).__name__}: {e}")
                else:
                    # Bad Timing with Connection Closure. Ignoring
                    Logger.verbose(f"Ignoring Error While Sending World Packet {Packets.Response.SpawnPlayer.NAME} To {player.networkHandler.ip}")

    async def removePlayer(self, player: Player):
        Logger.debug(f"Removing Player {player.name} From World {self.world.name}", module="world-player")
        # Delete User From Player List + Deallocate ID
        if player.playerId is not None:
            self.deallocateId(player.playerId)
        else:
            raise ServerError(f"Trying to Remove Player {player.name} With No Player Id")

        # Send Player Disconnect Packet To All Players (Except Joining User)
        await self.sendWorldPacket(
            Packets.Response.DespawnPlayer,
            player.playerId,
            ignoreList=[player]  # Don't send packet to self!
        )

        Logger.debug(f"Removed Player {player.networkHandler.ip} Username {player.name} Id {player.playerId} Joined World {self.world.name}", module="world-player")

        # Sending Leave Chat Message
        await self.sendWorldMessage(f"&e{player.name} Left The World &9(ID {player.playerId})&f")

    def allocateId(self):
        # Loop Through All Ids, Return Id That Is Not Free
        Logger.debug("Trying To Allocate Id", module="id-allocator")
        for idIndex, playerObj in enumerate(self.players):
            if playerObj is None:
                # Return Free ID
                return idIndex

        raise WorldError("Id Allocator Failed To Allocate Open Id")

    def deallocateId(self, playerId: int):
        # Check If Id Is Already Deallocated
        if self.players[playerId] is None:
            Logger.error(f"Trying To Deallocate Non Allocated Id {playerId}", "id-allocator", printTb=False)
        self.players[playerId] = None

        Logger.debug(f"Deallocated Id {playerId}", "id-allocator")

    async def sendWorldPacket(self, packet: Type[AbstractResponsePacket], *args, ignoreList: List[Player] = [], **kwargs):
        # Send packet to all members in world
        Logger.debug(f"Sending Packet {packet.NAME} To All Players On {self.world.name}", module="player-network")
        # Loop Through All Players
        for player in self.players:
            # Checking if Player Exists
            if player is None:
                continue

            # Checking if player is not in ignoreList
            if player in ignoreList:
                continue

            # Attempting to Send Packet
            try:
                await player.networkHandler.dispacher.sendPacket(packet, *args, **kwargs)
            except Exception as e:
                if e not in CRITICAL_RESPONSE_ERRORS:
                    # Something Broke!
                    Logger.error(f"An Error Occurred While Sending World Packet {packet.NAME} To {player.networkHandler.ip} - {type(e).__name__}: {e}")
                else:
                    # Bad Timing with Connection Closure. Ignoring
                    Logger.verbose(f"Ignoring Error While Sending World Packet {packet.NAME} To {player.networkHandler.ip}")

    async def sendWorldMessage(
        self,
        message,
        author: Union[None, str, Player] = None,  # Information on the message author
        worldTag: bool = False,  # Flag dictating if the [world] header should be added
        ignoreList: List[Player] = []  # List of players to not send the message not
    ):
        # Hacky Way To Get isintance World
        # Format Message To Be Sent
        # Add Author Tag
        if isinstance(author, str):
            message = f"<&e{author}&f> {message}"
        elif isinstance(author, Player):
            # Special Formatting For OPs
            if author.opStatus:
                message = f"<&c{author.name}&f> {message}"
            else:
                message = f"<&b{author.name}&f> {message}"

        # Add World Tag (If Requested)
        if worldTag:
            message = f"[&7{self.world.name}&f] {message}"

        # Finally, send formatted message
        Logger.log(
            message,
            tags=[Logger._getTimestamp(), "chat", "world", self.world.name],
            colour=Colour.GREEN,
            textColour=Colour.WHITE
        )
        await self.sendWorldPacket(Packets.Response.SendMessage, message, ignoreList=ignoreList)


class Player:
    def __init__(self, playerManager: PlayerManager, networkHandler: NetworkHandler, name, key, opStatus=False):
        self.name = name
        self.posX = 0,
        self.posY = 0,
        self.posZ = 0,
        self.posYaw = 0,
        self.posPitch = 0,
        self.verificationKey = key
        self.opStatus = opStatus
        self.playerManager = playerManager
        self.networkHandler = networkHandler
        self.worldPlayerManager = None
        self.playerId: Optional[int] = None

    async def joinWorld(self, world: World):
        Logger.debug(f"Player {self.name} Joining World {world.name}", module="player")
        # Setting Self World Player Manager
        self.worldPlayerManager = world.playerManager
        # Attaching Player Onto World Player Manager
        await self.worldPlayerManager.joinPlayer(self)

    async def sendMessage(self, message: str):
        Logger.debug(f"Sending Player {self.name} Message {message}", module="player")
        await self.networkHandler.dispacher.sendPacket(Packets.Response.SendMessage, str(message))

    async def handlePlayerMessage(self, message: str):
        # Format and deal with incoming player message requests.
        Logger.debug(f"Handling Player Message From Player {self.name}", module="player")

        # Check If Last Character Is '&' (Crashes All Clients)
        if message[-1:] == "&":
            message = message[:-1]  # Cut Last Character

        if len(message) > 32:  # Cut Message If Too Long
            # Cut Message In Half, then print each half
            await self.worldPlayerManager.sendWorldMessage(message[:32] + " - ", author=self)
            await self.worldPlayerManager.sendWorldMessage(" - " + message[32:], author=self)
            await self.sendMessage("&eWARN: Message Was Cut To Fit On Screen&f")
        else:
            await self.worldPlayerManager.sendWorldMessage(message, author=self)
