from obsidian.module import Module, AbstractModule, Dependency
from obsidian.mixins import Inject, InjectionPoint, Extend
from obsidian.server import Server
from obsidian.network import NetworkDispatcher
from obsidian.packet import _DirectionalPacketManager, AbstractPacket
from obsidian.log import Logger

from threading import Thread
import asyncio
import time
import math


@Module(
    "NetInfo",
    description="Provides Live Network Information About The Server.",
    author="RadioactiveHydra",
    version="1.0.0",
    dependencies=[Dependency("core"), Dependency("messagetypes")]
)
class NetInfoModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        Logger.warn("This is a debug module used for testing.", module="netinfo")
        Logger.warn("Please do not use this module in production.", module="netinfo")
        self.txPackets = 0
        self.txBytes = 0
        self.rxPackets = 0
        self.rxBytes = 0

    def postInit(self, **kwargs):
        # Start Logging Packets
        @Extend(target=_DirectionalPacketManager.getPacketById)
        def logRxPacket(packet: AbstractPacket):
            self.rxPackets += 1
            self.rxBytes += packet.SIZE
            return packet

        @Inject(target=NetworkDispatcher.sendPacket)
        async def logTxPacket(_, packet: AbstractPacket, *args, **kwargs):
            self.txPackets += 1
            self.txBytes += packet.SIZE

        @Inject(target=Server.run, at=InjectionPoint.BEFORE)
        async def startNetInfoThread(server_self, *args, **kwargs):
            server_self.netInfoThread = Thread(target=NetInfoModule.netInfoThread, args=(server_self, self))
            server_self.netInfoThread.setName("NetInfoThread")
            server_self.netInfoThread.setDaemon(True)
            Logger.debug(f"Starting net info thread {server_self.netInfoThread}", module="netinfo")
            server_self.netInfoThread.start()

        @Inject(target=Server.run, at=InjectionPoint.BEFORE)
        async def startHealthcheckThread(server_self, *args, **kwargs):
            server_self.healthcheckThread = Thread(target=NetInfoModule.healthcheckThread, args=(server_self, self))
            server_self.healthcheckThread.setName("HealthcheckThread")
            server_self.healthcheckThread.setDaemon(True)
            Logger.debug(f"Starting net info thread {server_self.healthcheckThread}", module="netinfo")
            server_self.healthcheckThread.start()

    @staticmethod
    def netInfoThread(server: Server, module: "NetInfoModule"):
        from obsidian.modules.messagetypes import MessageTypesModule, MessageType

        # Create an event loop to run async tasks in
        eventLoop = asyncio.new_event_loop()

        # Last Status
        lastStatus = time.time()

        # Start hot-loop for heartbeat
        while True:
            try:
                time.sleep(1)

                async def sendNetInfo():
                    nonlocal lastStatus

                    lastHealthcheck = getattr(server, "lastHealthcheck")
                    threadloopDelta = getattr(server, "threadloopDelta")

                    if (time.time() - lastHealthcheck) > 5:
                        frozen = True
                    else:
                        frozen = False

                    if threadloopDelta > 1000:  # 1 second
                        healthy = False
                    else:
                        healthy = True

                    txPackets = module.txPackets
                    txBytes = module.txBytes
                    rxPackets = module.rxPackets
                    rxBytes = module.rxBytes

                    timeDelta = (time.time() - lastStatus)

                    lastStatus = time.time()

                    txPacketsRate = math.ceil(txPackets / timeDelta)
                    txBytesRate = math.ceil(txBytes / timeDelta)
                    rxPacketsRate = math.ceil(rxPackets / timeDelta)
                    rxBytesRate = math.ceil(rxBytes / timeDelta)

                    await MessageTypesModule.sendGlobalMessage(
                        server.playerManager,
                        f"&cTx: &f{txPacketsRate} packets/s &4[{txBytesRate} bytes/s]&f  | ",
                        messageType=MessageType.BOTTOM_RIGHT_1
                    )

                    await MessageTypesModule.sendGlobalMessage(
                        server.playerManager,
                        f"&aRx: &f{rxPacketsRate} packets/s &2[{rxBytesRate} bytes/s]&f  | ",
                        messageType=MessageType.BOTTOM_RIGHT_2
                    )

                    if healthy and not frozen:
                        eventloopStatus = f"&a{math.ceil(threadloopDelta)}ms &a[HEALTHY]"
                    elif not healthy and not frozen:
                        eventloopStatus = f"&e{math.ceil(threadloopDelta)}ms &e[UNHEALTHY]"
                    else:
                        eventloopStatus = "&c???ms &4[FROZEN/HUNG]"

                    await MessageTypesModule.sendGlobalMessage(
                        server.playerManager,
                        f"&dProject&5Obsidian&f | &eEventLoop: {eventloopStatus}",
                        messageType=MessageType.BOTTOM_RIGHT_3
                    )

                    module.rxPackets = 0
                    module.rxBytes = 0
                    module.txPackets = 0
                    module.txBytes = 0

                    if frozen:
                        Logger.warn(f"SERVER FROZEN! Last response was {time.time() - lastHealthcheck} seconds ago.", module="netinfo")
                        await server.playerManager.sendGlobalMessage(f"&cSERVER FROZEN! Last response was {(time.time() - lastHealthcheck):.2f} seconds ago.")

                eventLoop.run_until_complete(sendNetInfo())
            except Exception as e:
                Logger.error(f"Unhandled exception in net info thread - {type(e).__name__}: {e}", module="netinfo", printTb=True)
                time.sleep(1)

    @staticmethod
    def healthcheckThread(server: Server, module: "NetInfoModule"):
        while True:
            try:
                start = time.time()

                async def doStuff(server):
                    setattr(server, "lastHealthcheck", time.time())
                    # print("hello!")

                future = asyncio.run_coroutine_threadsafe(doStuff(server), server._server.get_loop())  # type: ignore
                future.result()

                setattr(server, "threadloopDelta", (time.time() - start) * 1000)
                print(time.time() - start)

                time.sleep(1)
            except Exception as e:
                Logger.error(f"Unhandled exception in net info thread - {type(e).__name__}: {e}", module="netinfo", printTb=True)
                time.sleep(1)
