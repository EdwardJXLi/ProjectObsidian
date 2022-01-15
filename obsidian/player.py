from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from obsidian.server import Server
    from obsidian.world import World
    from obsidian.network import NetworkHandler
    from obsidian.blocks import AbstractBlock

from typing import Optional, Type

from obsidian.packet import AbstractResponsePacket, Packets
from obsidian.log import Logger
from obsidian.commands import Commands, _parseArgs
from obsidian.constants import Colour, CRITICAL_RESPONSE_ERRORS
from obsidian.types import UsernameType, _formatUsername
from obsidian.errors import (
    ServerError,
    WorldError,
    ClientError,
    CommandError
)


# The Overall Server Player Manager
class PlayerManager:
    def __init__(self, server: Server, maxSize: int = 1024):
        self.server: Server = server
        self.players: dict[UsernameType, Player] = {}  # Dict of Players with Usernames as Keys
        self.maxSize: int = maxSize

    async def createPlayer(self, network: NetworkHandler, displayName: str, verificationKey: str):
        Logger.debug(f"Creating Player For Ip {network.conninfo}", module="player-manager")
        # Check if name is alphanumeric
        if not displayName.isalnum():
            raise ClientError("Username Must Be Alphanumeric Only!")

        # Format Username
        username = _formatUsername(displayName)

        # Check if user is banned!
        if username in self.server.config.bannedPlayers:
            raise ClientError("You are banned.")

        # Checking if server is full
        if len(self.players) >= self.maxSize:
            raise ClientError("Server Is Full!")

        # Check if username is taken
        if username in self.players:
            raise ClientError("This Username Is Taken!")

        # Creating Player Class
        player = Player(self, network, username, displayName, verificationKey)

        # Check if user is an operator and set their status
        await player.updateOperatorStatus(sendMessage=False)

        # Adding Player Class
        self.players[username] = player
        return player

    def getPlayersByIp(self, ip: str):
        Logger.verbose(f"Getting Players With Ip {ip}", module="player-manager")
        # Loop through all players and find those who need to be kicked
        toKick: list[Player] = []
        for player in self.players.values():
            if player.networkHandler.ip == ip:
                toKick.append(player)
        Logger.verbose(f"Found Players: {toKick}", module="player-manager")
        return toKick

    async def deletePlayer(self, player: Player):
        Logger.debug(f"Removing Player {player.name}", module="player-manager")
        # Remove Player From World If Necessary
        if player.worldPlayerManager is not None and player.playerId is not None:
            Logger.debug("User Leaving World", module="player-manager")
            await player.worldPlayerManager.removePlayer(player)

        # Remove Player From PlayerManager
        for playerName, playerObj in self.players.items():
            if player is playerObj:
                del self.players[playerName]
                break

        Logger.debug(f"Successfully Removed Player {player.name}", module="player-manager")

    async def kickPlayer(self, username: UsernameType, reason: str = "Kicked By Server"):
        Logger.info(f"Kicking Player {username}", module="player-manager")
        # Check if username matches a player
        if username in self.players:
            # Get Player Object
            player = self.players[username]
            # Kick Player
            await player.networkHandler.closeConnection(reason, notifyPlayer=True)
            Logger.debug(f"Successfully Kicked Player {username}", module="player")
            return True
        else:
            Logger.warn(f"Player {username} Does Not Exist", module="player-manager")
            return False

    async def kickPlayerByIp(self, ip: str, reason: str = "Kicked By Server"):
        Logger.info(f"Kicking Player(s) by Ip {ip}", module="player-manager")
        # Get players with ip
        toKick = self.getPlayersByIp(ip)

        # Check if anyone is getting kicked
        if not toKick:
            Logger.warn(f"No players found with Ip {ip}. Not kicking anyone", module="player-manager")
            return False

        # Kick Players
        Logger.info(f"Kicking {len(toKick)} Player(s) by Ip {ip}", module="player-manager")
        for player in toKick:
            Logger.debug(f"Player {player.name} is being kicked", module="player-manager")
            await player.networkHandler.closeConnection(reason, notifyPlayer=True)

    async def sendGlobalPacket(self, packet: Type[AbstractResponsePacket], *args, ignoreList: list[Player] = [], **kwargs):
        # Send packet to ALL members connected to server (all worlds)
        Logger.verbose(f"Sending Packet {packet.NAME} To All Connected Players", module="global-packet-dispatcher")
        # Loop Through All Players
        for player in self.players.values():
            # Checking if player is not in ignoreList
            if player not in ignoreList:
                try:
                    # Sending Packet To Player
                    await player.networkHandler.dispacher.sendPacket(packet, *args, **kwargs)
                except Exception as e:
                    if e not in CRITICAL_RESPONSE_ERRORS:
                        # Something Broke!
                        Logger.error(f"An Error Occurred While Sending Global Packet {packet.NAME} To {player.networkHandler.conninfo} - {type(e).__name__}: {e}", module="global-packet-dispatcher")
                    else:
                        # Bad Timing with Connection Closure. Ignoring
                        Logger.verbose(f"Ignoring Error While Sending Global Packet {packet.NAME} To {player.networkHandler.conninfo}", module="global-packet-dispatcher")

    async def sendGlobalMessage(
        self,
        message: str | list,
        author: None | str | Player = None,  # Information on the message author
        globalTag: bool = False,  # Flag dictating if the [world] header should be added
        ignoreList: list[Player] = []  # List of players to not send the message not
    ):
        # If Message Is A List, Recursively Send All Messages Within
        if isinstance(message, list):
            Logger.debug("Sending List Of Messages!", module="global-message")
            for msg in message:
                await self.sendGlobalMessage(msg, author=author, globalTag=globalTag, ignoreList=ignoreList)
            return None  # Break Out of Function

        # Format Message To Be Sent
        # Add Author Tag
        if isinstance(author, str):
            message = f"<&e{author}&f> {message}"
        elif isinstance(author, Player):
            # Special Formatting For OPs
            if author.opStatus:
                message = f"<&c{author.name}&f> {message}"
            else:
                message = f"<&a{author.name}&f> {message}"

        # Add Global Tag (If Requested)
        if globalTag:
            message = f"[&7GLOBAL&f] {message}"

        # Finally, send formatted message
        Logger.log(
            str(message),
            tags=(Logger._getTimestamp(), "chat", "global"),
            colour=Colour.GREEN,
            textColour=Colour.WHITE
        )
        await self.sendGlobalPacket(Packets.Response.SendMessage, message, ignoreList=ignoreList)


# The Specific Player Manager Per World
class WorldPlayerManager:
    def __init__(self, world: World):
        self.world: World = world
        self.player_slots: list[Optional[Player]] = [None] * world.maxPlayers

    async def joinPlayer(self, player: Player):
        # Trying To Allocate Id
        # Fails If All Slots Are Taken
        try:
            playerId = self.allocateId()
        except WorldError:
            raise ClientError(f"World {self.world.name} Is Full")

        # Adding Player To Players List Using Id
        Logger.debug(f"Player {player.networkHandler.conninfo} Username {player.name} Id {playerId} Is Joining World {self.world.name}", module="world-player")
        player.playerId = playerId
        self.player_slots[playerId] = player

        # If automaticallyDetermineSpawn is enabled, determine new spawn point
        if self.world.worldManager.server.config.automaticallyDetermineSpawn:
            self.world.generateSpawnCoords(forceSpawnX=True, forceSpawnZ=True, forceSpawnY=True, forceSpawnYaw=True, forceSpawnPitch=True)

        # Solve rare edge case where Spawn coords may not be set!
        if (
            self.world.spawnX is not None and
            self.world.spawnY is not None and
            self.world.spawnZ is not None and
            self.world.spawnYaw is not None and
            self.world.spawnPitch is not None
        ):
            # Set Player Location
            # TODO saving player location
            await player.setLocation(
                self.world.spawnX,
                self.world.spawnY,
                self.world.spawnZ,
                self.world.spawnYaw,
                self.world.spawnPitch,
                notifyPlayers=False
            )
        else:
            raise ServerError("Attempted To Spawn Player to a Location That Is Not Set!")

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

        # Sending Warning If World Is Non-Persistant
        if not self.world.persistant:
            await player.sendMessage("&cWARNING: This world is Non-Persistant!&f")
            await player.sendMessage("&cAny changes WILL NOT be saved!!&f")

    async def spawnCurrentPlayers(self, playerSelf: Player):  # Update Joining Players of The Currently In-Game Players
        # Loop Through All Players
        for player in self.player_slots:
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
                    Logger.error(f"An Error Occurred While Sending World Packet {Packets.Response.SpawnPlayer.NAME} To {player.networkHandler.conninfo} - {type(e).__name__}: {e}", module="world-packet-dispatcher")
                else:
                    # Bad Timing with Connection Closure. Ignoring
                    Logger.verbose(f"Ignoring Error While Sending World Packet {Packets.Response.SpawnPlayer.NAME} To {player.networkHandler.conninfo}", module="world-packet-dispatcher")

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

        Logger.debug(f"Removed Player {player.networkHandler.conninfo} Username {player.name} Id {player.playerId} Joined World {self.world.name}", module="world-player")

        # Sending Leave Chat Message
        await self.sendWorldMessage(f"&e{player.name} Left The World &9(ID {player.playerId})&f")

    def allocateId(self):
        # Loop Through All Ids, Return Id That Is Not Free
        Logger.debug("Trying To Allocate Id", module="id-allocator")
        for idIndex, playerObj in enumerate(self.player_slots):
            if playerObj is None:
                # Return Free ID
                return idIndex

        raise WorldError("Id Allocator Failed To Allocate Open Id")

    def deallocateId(self, playerId: int):
        # Check If Id Is Already Deallocated
        if self.player_slots[playerId] is None:
            Logger.error(f"Trying To Deallocate Non Allocated Id {playerId}", module="id-allocator", printTb=False)
        self.player_slots[playerId] = None

        Logger.debug(f"Deallocated Id {playerId}", module="id-allocator")

    def getPlayers(self):
        # Loop through all players
        players_list = []
        for player in self.player_slots:
            if player is not None:
                # If its not none, its a player!
                players_list.append(player)
        return players_list

    async def sendWorldPacket(self, packet: Type[AbstractResponsePacket], *args, ignoreList: list[Player] = [], **kwargs):
        # Send packet to all members in world
        Logger.verbose(f"Sending Packet {packet.NAME} To All Players On {self.world.name}", module="world-packet-dispatcher")
        # Loop Through All Players
        for player in self.player_slots:
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
                    Logger.error(f"An Error Occurred While Sending World Packet {packet.NAME} To {player.networkHandler.conninfo} - {type(e).__name__}: {e}", module="world-packet-dispatcher")
                else:
                    # Bad Timing with Connection Closure. Ignoring
                    Logger.verbose(f"Ignoring Error While Sending World Packet {packet.NAME} To {player.networkHandler.conninfo}", module="world-packet-dispatcher")

    async def sendWorldMessage(
        self,
        message: str | list,
        author: None | str | Player = None,  # Information on the message author
        worldTag: bool = False,  # Flag dictating if the [world] header should be added
        ignoreList: list[Player] = []  # List of players to not send the message not
    ):
        # If Message Is A List, Recursively Send All Messages Within
        if isinstance(message, list):
            Logger.debug("Sending List Of Messages!", module="world-message")
            for msg in message:
                await self.sendWorldMessage(msg, author=author, worldTag=worldTag, ignoreList=ignoreList)
            return None  # Break Out of Function

        # Hacky Way To Get World Type
        # Format Message To Be Sent
        # Add Author Tag
        if isinstance(author, str):
            message = f"<&e{author}&f> {message}"
        elif isinstance(author, Player):
            # Special Formatting For OPs
            if author.opStatus:
                message = f"<{self.world.worldManager.server.config.operatorChatColor}{author.name}&f> {message}"
            else:
                message = f"<{self.world.worldManager.server.config.playerChatColor}{author.name}&f> {message}"

        # Add World Tag (If Requested)
        if worldTag:
            message = f"[&7{self.world.name}&f] {message}"

        # Finally, send formatted message
        Logger.log(
            str(message),
            tags=(Logger._getTimestamp(), "chat", "world", self.world.name),
            colour=Colour.GREEN,
            textColour=Colour.WHITE
        )
        await self.sendWorldPacket(Packets.Response.SendMessage, message, ignoreList=ignoreList)


class Player:
    def __init__(self, playerManager: PlayerManager, networkHandler: NetworkHandler, username: UsernameType, displayName: str, key: str):
        self.username: UsernameType = username
        self.name: str = displayName
        self.posX: int = 0
        self.posY: int = 0
        self.posZ: int = 0
        self.posYaw: int = 0
        self.posPitch: int = 0
        self.server: Server = playerManager.server
        self.verificationKey: str = key
        self.playerManager: PlayerManager = playerManager
        self.networkHandler: NetworkHandler = networkHandler
        self.worldPlayerManager: Optional[WorldPlayerManager] = None
        self.playerId: Optional[int] = None

    @property
    def opStatus(self):
        return self.username in self.playerManager.server.config.operatorsList

    async def updateOperatorStatus(self, sendMessage: bool = True):
        # Check if player is an operator
        if self.opStatus:
            # Send Packet To Player
            await self.networkHandler.dispacher.sendPacket(Packets.Response.UpdateUserType, True)
            # Send Message to Player (If Requested)
            if sendMessage:
                await self.sendMessage("You Are Now An Operator")
        elif not self.opStatus:
            # Send Packet To Player
            await self.networkHandler.dispacher.sendPacket(Packets.Response.UpdateUserType, False)
            # Send Message to Player (If Requested)
            if sendMessage:
                await self.sendMessage("You Are No Longer An Operator")

    async def joinWorld(self, world: World):
        Logger.info(f"Player {self.name} Joining World {world.name}", module="player")
        # Check if playser is already joined in a world
        if self.worldPlayerManager is not None:
            raise ServerError(f"Player {self.name} Already In World")
        # Setting Self World Player Manager
        self.worldPlayerManager = world.playerManager
        # Attaching Player Onto World Player Manager
        await self.worldPlayerManager.joinPlayer(self)

    async def changeWorld(self, world: World, updateServerInfo: bool = True, sendMessage: bool = True):
        Logger.info(f"Player {self.name} Changing World to {world.name}", module="change-world")
        # Check if player is in a world
        if self.worldPlayerManager is None:
            raise ServerError(f"Player {self.name} Not In World")
        # Send Joining Message
        if sendMessage:
            await self.sendMessage(f"&eSending You To World &b{world.name}&e...")
        # Handle the world change
        await self.networkHandler._processWorldChange(world, self.worldPlayerManager.world, updateServerInfo=updateServerInfo)

    async def setLocation(self, posX: int, posY: int, posZ: int, posYaw: int = 0, posPitch: int = 0, notifyPlayers: bool = True):
        Logger.debug(f"Setting New Player Location for Player {self.name} (X: {posX}, Y: {posY}, Z: {posZ}, Yaw: {posYaw}, Pitch: {posPitch})", module="player")

        # Checking If Player Is Joined To A World
        if self.worldPlayerManager is None:
            Logger.error(f"Player {self.name} Trying To setLocation When No World Is Joined", module="player")
            return None  # Skip Rest

        # Set the Player Location
        self.posX = posX
        self.posY = posY
        self.posZ = posZ
        self.posYaw = posYaw
        self.posPitch = posPitch

        # Send Location Update
        if notifyPlayers:
            # Sending Player Position Update Packet To All Players
            await self.worldPlayerManager.sendWorldPacket(
                Packets.Response.PlayerPositionUpdate,
                self.playerId,
                posX,
                posY,
                posZ,
                posYaw,
                posPitch
                # Not ignoring self as we WANT to update player
            )

    async def sendMessage(self, message: str | list):
        Logger.debug(f"Sending Player {self.name} Message {message}", module="player")
        # If Message Is A List, Recursively Send All Messages Within
        if isinstance(message, list):
            Logger.debug("Sending List Of Messages To Player!", "player-message")
            for msg in message:
                await self.sendMessage(msg)
            return None  # Break Out of Function

        # Send message packet to user
        await self.networkHandler.dispacher.sendPacket(Packets.Response.SendMessage, str(message))

    async def handleBlockUpdate(self, blockX: int, blockY: int, blockZ: int, blockType: AbstractBlock):
        # Format, Process, and Handle incoming block update requests.
        Logger.debug(f"Handling Block Placement From Player {self.name}", module="player")

        # Checking If Player Is Joined To A World
        if self.worldPlayerManager is None:
            Logger.error(f"Player {self.name} Trying To handleBlockUpdate When No World Is Joined", module="player")
            return None  # Skip Rest

        # Trying To Update Block On Player World
        try:
            await blockType.placeBlock(self, blockX, blockY, blockZ)
        except ClientError as e:
            # Setting Player-Attempted Block Back To Original
            originalBlock = self.worldPlayerManager.world.getBlock(blockX, blockY, blockZ)
            await self.networkHandler.dispacher.sendPacket(
                Packets.Response.SetBlock,
                blockX,
                blockY,
                blockZ,
                originalBlock.ID
            )

            # Send Error Message To
            await self.sendMessage(f"&c{e}&f")

    async def handlePlayerMovement(self, posX: int, posY: int, posZ: int, posYaw: int, posPitch: int):
        # Format, Process, and Handle incoming player movement requests.
        Logger.verbose(f"Handling Player Movement From Player {self.name}", module="player")

        # Checking If Player Is Joined To A World
        if self.worldPlayerManager is None:
            Logger.error(f"Player {self.name} Trying To handlePlayerMovement When No World Is Joined", module="player")
            return None  # Skip Rest

        # Updating Current Player Position
        self.posX = posX
        self.posY = posY
        self.posZ = posZ
        self.posYaw = posYaw
        self.posPitch = posPitch

        # Sending Player Position Update Packet To All Players
        await self.worldPlayerManager.sendWorldPacket(
            Packets.Response.PlayerPositionUpdate,
            self.playerId,
            posX,
            posY,
            posZ,
            posYaw,
            posPitch,
            ignoreList=[self]  # not sending to self as that may cause some de-sync issues
        )

    async def handlePlayerMessage(self, message: str):
        # Format, Process, and Handle incoming player message requests.
        Logger.debug(f"Handling Player Message From Player {self.name}", module="player")

        # Checking If Player Is Joined To A World
        if self.worldPlayerManager is None:
            Logger.debug(f"Player {self.name} Trying To handlePlayerMessage When No World Is Joined", module="player")
            return None  # Skip Rest

        # Checking If Message Is A Command
        if message[0] == "/":
            try:
                await self.handlePlayerCommand(message[1:])
            except CommandError as e:
                Logger.warn(f"Command From Player {self.name} Failed With {str(e)}", module="command")
                await self.sendMessage(f"&cInvalid Command: {str(e)}")
            return None  # Skip Rest

        # Check If Last Character Is '&' (Crashes Older Minecraft Clients)
        if len(message) > 0 and message[-1:] == "&":
            message = message[:-1]  # Cut Last Character

        if len(message) > 32:  # Cut Message If Too Long
            # Cut Message In Half, then print each half
            await self.worldPlayerManager.sendWorldMessage(message[:32] + " - ", author=self)
            await self.worldPlayerManager.sendWorldMessage(" - " + message[32:], author=self)
            await self.sendMessage("&eWARN: Message Was Cut To Fit On Screen&f")
        else:
            await self.worldPlayerManager.sendWorldMessage(message, author=self)

    async def handlePlayerCommand(self, cmdMessage: str):
        # Format, Process, and Handle incoming player commands.
        Logger.debug(f"Handling Command From Player {self.name}", module="command")

        # Splitting Command Data
        cmdName, *cmdArgs = cmdMessage.split(" ")
        # Format cmdName
        cmdName = cmdName.lower()
        Logger.info(f"Command {cmdName} Received From Player {self.name}", module="command")
        Logger.debug(f"Handling Command {cmdName} With Arguments {cmdArgs}", module="command")

        # Get Command Object
        command = Commands.getCommandFromName(cmdName)

        # Check if command is disabled
        if command.NAME in self.playerManager.server.config.disabledCommands:
            # If user is op, allow run but give warning
            # Else, disallow run
            if self.opStatus:
                await self.sendMessage("&4[WARNING] &fThis Command Is Disabled, But You Are an OP!")
            else:
                raise CommandError("This Command Is Disabled!")

        # Check if user is allowed to run this command
        if command.OP and not self.opStatus:
            raise CommandError("You Are Not An Operator!")

        # Parse Command Arguments
        parsedArguments, parsedKwArgs = _parseArgs(command, cmdArgs)

        # Run Command
        try:
            await command.execute(self, *parsedArguments, **parsedKwArgs)
        except CommandError as e:
            raise e  # Pass error down
        except Exception as e:
            Logger.error(f"Command {command.NAME} Raised Error {str(e)}", module="command")
            await self.sendMessage("&cAn Unknown Internal Server Error Has Occurred!")

    async def sendMOTD(self, motdMessage: Optional[list[str]] = None):
        # If motdMessage was not passed, use default one in config
        if motdMessage is None:
            motdMessage = self.playerManager.server.config.defaultMOTD

        # Send MOTD To Player
        Logger.debug(f"Sending MOTD to Player {self.name}", module="command")
        await self.sendMessage(motdMessage)
