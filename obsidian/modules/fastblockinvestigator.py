import time
import sqlite3
from pathlib import Path
from typing import Callable, cast, Optional
from dataclasses import dataclass, field
from threading import Thread
from datetime import datetime

from obsidian.constants import SERVER_PATH
from obsidian.module import Module, AbstractModule, Dependency
from obsidian.commands import Command, AbstractCommand
from obsidian.player import Player
from obsidian.mixins import Inject, InjectionPoint, Override
from obsidian.config import AbstractConfig
from obsidian.world import World, WorldManager
from obsidian.log import Logger
from obsidian.blocks import AbstractBlock, BlockManager
from obsidian.errors import CommandError


@Module(
    "FastBlockInvestigator",
    description="Block Change Audit Logging",
    author="RandomBK",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class FastBlockInvestigatorModule(AbstractModule):
    TABLE_NAME = "block_changes_v1"

    def __init__(self, *args):
        super().__init__(*args)
        self.config = self.initConfig(self.FastBlockInvestigatorConfig)

        #
        # Storage Design
        #
        # All audit data is stored in a per-world SQLite database. To keep things in sync with the world file, commits to
        # this database are only done when the world is saved. All reads and writes to the audit database is done in
        # the context of this single transaction, and is thus limited to a single database connection. Attempting to
        # create multiple connections will result in a hang or SQLITE_BUSY error.
        #
        # In service to this design, the coding style of this module is always assume a given sqlite database connection
        # object is in the middle of a eagerly-created write transaction. The only exceptions are in the methods to load
        # and save the database.
        #
        self.auditDBs = {}

    def postInit(self, **kwargs):
        # Check if the module is enabled
        if not self.config.enabled:
            Logger.info("The Fast Block Investigator is disabled! Not starting module.", module="fastblockinvestigator")
            return

        # Put into local closure
        auditDBs = self.auditDBs

        #
        # Hook into world loading & unloading
        #
        # World creation only looks to be called from loadWorld so our hook into loadWorld should be sufficient
        #
        @Inject(target=WorldManager.loadWorlds, at=InjectionPoint.AFTER, abstract=True)
        def loadWorlds(self, reload: bool = False):
            self = cast(World, self)

            for world in self.worlds.values():
                Logger.info(f"Loading FBI database for world {world.name}", module="fastblockinvestigator")
                worldPath = Path(SERVER_PATH, self.server.config.worldSaveLocation, f"{world.name}.fbi.db")
                auditDBs[world.name] = FastBlockInvestigatorModule._loadDB(worldPath)

        @Inject(target=WorldManager.closeWorlds, at=InjectionPoint.AFTER, abstract=True)
        def closeWorlds(self):
            self = cast(World, self)
            Logger.info(f"Closing all FBI databases", module="fastblockinvestigator")

            # Discard unsaved changes
            for conn in auditDBs.values():
                conn.rollback()
                conn.close()
            auditDBs.clear()

        #
        # Log block placements
        #
        @Override(target=World.setBlock, passSuper=True)
        async def setBlock(self, blockX: int, blockY: int, blockZ: int, block: AbstractBlock, player: Optional[Player] = None,
                           sendPacket: bool = True, updateSelf: bool = False, super: Callable = None) -> bool:
            # Since we are injecting, set type of self to World
            self = cast(World, self)

            blockIdx = 0
            if not (blockX >= self.sizeX or blockY >= self.sizeY or blockZ >= self.sizeZ):
                blockIdx = blockX + self.sizeX * (blockZ + self.sizeZ * blockY)

            # Record the old value
            oldBlock = self.mapArray[blockIdx]

            # Set the actual block
            # Stupid pylance
            result = await cast(Callable, super)(self, blockX, blockY, blockZ=blockZ, block=block,
                                 player=player, sendPacket=sendPacket, updateSelf=updateSelf)

            conn = auditDBs.get(self.name)
            if result and conn is not None:
                # Record the new value
                newBlock = self.mapArray[blockIdx]
                FastBlockInvestigatorModule._logBlock(conn, blockIdx, oldBlock, newBlock, player)

            return result

        #
        # Commit the audit database when the world is saved
        #
        @Override(target=World.saveMap, passSuper=True) # I *should* be able to just use @Inject, but the API is too limited
        def saveMap(self, super: Callable = None):
            # Since we are injecting, set type of self to World
            self = cast(World, self)
            result = super(self)

            if result:
                conn = auditDBs.get(self.name)
                if conn is not None:
                    Logger.info(f"Saving FBI logs for world {self.name}", module="fastblockinvestigator")
                    FastBlockInvestigatorModule._saveDB(conn)

    # Lookup by block
    @Command(
        "FBI Check Player",
        description="Prints the history of a given player",
        version="v1.0.0"
    )
    class FBICommand(AbstractCommand["FastBlockInvestigatorModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["fbi"], OP=True)

        async def execute(self, ctx: Player, mode: str = "help", param1: Optional[str] = None):
            if ctx.worldPlayerManager is not None:
                world = ctx.worldPlayerManager.world
            else:
                raise CommandError("You are not in a world!")

            # Fetch Connection
            conn = self.module.auditDBs.get(world.name)
            if conn is None:
                raise CommandError("FastBlockInvestigator is not enabled on this world!")

            if mode == "help":
                await self.handleHelp(ctx)
            elif mode == "investigate":
                await self.handleByBlock(world, conn, ctx)
            elif mode == "lookup":
                await self.handleByPlayer(world, conn, ctx, param1 or ctx.username)
            else:
                await self.handleInvalidSubcommand(ctx, mode)

        async def handleHelp(self, ctx: Player):
            await ctx.sendMessage([
                "&eFast Block Investigator - Audit Block Placement Activity",
                "&a    /fbi investigate &f- &bPrints block history",
                "&a    /fbi lookup <player> &f- &bPrints player history",
            ])

        async def handleInvalidSubcommand(self, ctx: Player, subcommand: str):
            await ctx.sendMessage(f"&cInvalid subcommand: {subcommand}")

        async def handleByBlock(self, world: World, conn: sqlite3.Connection, ctx: Player):
            # Get coordinates
            await ctx.sendMessage("&aPlease select the block")
            x, y, z, _ = await ctx.getNextBlockUpdate()

            # Fetch history
            await ctx.sendMessage(f"&aLooking up history of location ({x}, {y}, {z})...")
            history = self.fetchByBlock(conn, world, x, y, z)

            if len(history) == 0:
                await ctx.sendMessage(f"&aNo history found for ({x}, {y}, {z})")
                return
            else:
                history.reverse()

                items = [
                    f"{self.formatDatetime(timestamp)} {self.formatPlayerName(name)} {self.formatBlockID(old_block)} &f-> {self.formatBlockID(new_block)}"
                    for (timestamp, name, old_block, new_block) in history
                ]

                # Send final message to player
                await ctx.sendMessage(f"&aBlock History for ({x}, {y}, {z}):")
                await ctx.sendMessage(items)

        async def handleByPlayer(self, world: World, conn: sqlite3.Connection, ctx: Player, target: str):
            # Fetch history
            await ctx.sendMessage(f"&aLooking up history of player {self.formatPlayerName(target)}...")
            history = self.fetchByPlayer(conn, target)

            if len(history) == 0:
                await ctx.sendMessage(f"&aNo history found for player {self.formatPlayerName(target)}")
                return
            else:
                history.reverse()

                items = [
                    f"{self.formatDatetime(timestamp)} {self.formatLocationIdx(world, idx)} {self.formatBlockID(old_block)} &f-> {self.formatBlockID(new_block)}"
                    for (timestamp, idx, old_block, new_block) in history
                ]

                # Send final message to player
                await ctx.sendMessage(f"&aBlock History for {self.formatPlayerName(target)}:")
                await ctx.sendMessage(items)

        def fetchByBlock(self, conn: sqlite3.Connection, world: World, x: int, y: int, z: int) -> any:
            return list(conn.execute(f"""
                SELECT timestamp, player_name, old_block, new_block
                FROM {FastBlockInvestigatorModule.TABLE_NAME}
                WHERE block_idx = ?
                ORDER BY timestamp DESC, action_id DESC
                LIMIT 20;
            """, (x + world.sizeX * (z + world.sizeZ * y),)))

        def fetchByPlayer(self, conn: sqlite3.Connection, target: str) -> any:
            return list(conn.execute(f"""
                SELECT timestamp, block_idx, old_block, new_block
                FROM {FastBlockInvestigatorModule.TABLE_NAME}
                WHERE player_name = ?
                ORDER BY timestamp DESC, action_id DESC
                LIMIT 20;
            """, (target,)))

        def formatLocationIdx(self, world: World, location: int) -> str:
            x = location % world.sizeX
            y = location // (world.sizeX * world.sizeY)
            z = (location // world.sizeX) % world.sizeY

            return f"&f({x}, {y}, {z})"

        def formatDatetime(self, timestamp: int) -> str:
            return f"&a{datetime.utcfromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')}"

        def formatPlayerName(self, name: int) -> str:
            return f"&d{name}"

        def formatBlockID(self, blockID: int) -> str:
            try:
                block = BlockManager.getBlockById(blockID)
                return f"&e{block.NAME} &e(&e{block.ID}&e)"
            except:
                return f"&e<unknown block> &e(&e{blockID}&e)"

    @staticmethod
    def _loadDB(dbPath) -> sqlite3.Connection:
        conn = sqlite3.connect(
            database=dbPath,

            # 7 days - if there hasn't been a world write for this long then it's the server operator's fault
            timeout=7*24*60*60,

            # We want control over when the database is committed so disable autocommit
            isolation_level=None,
        )

        # TODO: Decide on journal vs WAL - https://www.sqlite.org/wal.html
        # conn.execute("PRAGMA journal_mode=WAL;")        # Use WAL to keep the on-disk database unmodified until we commit
        conn.execute("PRAGMA locking_mode=EXCLUSIVE;")  # Exclusive locking mode
        conn.execute("PRAGMA synchronous=NORMAL;")      # Normal synchronous mode

        # Begin the write transaction that everything will live in
        conn.execute("BEGIN TRANSACTION;")

        # Create the table if it doesn't exist
        # Avoid executescript as the docs reference an implicit COMMIT
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {FastBlockInvestigatorModule.TABLE_NAME} (
                -- Aliased to rowid - see https://www.sqlite.org/lang_createtable.html#rowid
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                block_idx INTEGER NOT NULL,
                old_block INTEGER NOT NULL,
                new_block INTEGER NOT NULL
            );
        """)
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_player ON {FastBlockInvestigatorModule.TABLE_NAME}(player_name);")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_block ON {FastBlockInvestigatorModule.TABLE_NAME}(block_idx);")

        return conn

    @staticmethod
    def _logBlock(conn: sqlite3.Connection, blockIdx: int, oldBlock: int, newBlock: int, player: Optional[Player]):
        playerName = player.name if player is not None else "<null>"
        Logger.debug(f"Logging block change at {blockIdx} from {oldBlock} to {newBlock} by {playerName}", module="fastblockinvestigator")
        conn.execute(f"""
            INSERT INTO {FastBlockInvestigatorModule.TABLE_NAME}(timestamp, player_name, block_idx, old_block, new_block)
            VALUES(?, ?, ?, ?, ?);
        """, (int(time.time() * 1000), playerName, blockIdx, oldBlock, newBlock))

    @staticmethod
    def _saveDB(conn: sqlite3.Connection):
        conn.commit()
        conn.execute("BEGIN TRANSACTION;")

    @dataclass
    class FastBlockInvestigatorConfig(AbstractConfig):
        # Determine if the module is enabled
        enabled: bool = True
