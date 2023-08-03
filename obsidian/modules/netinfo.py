from obsidian.module import Module, AbstractModule, Dependency
from obsidian.mixins import Inject, InjectionPoint, Extend
from obsidian.server import Server
from obsidian.network import NetworkDispatcher
from obsidian.packet import _DirectionalPacketManager, AbstractPacket
from obsidian.log import Logger

from threading import Thread
import asyncio
import time


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

    @staticmethod
    def netInfoThread(server: Server, module: "NetInfoModule"):
        from obsidian.modules.messagetypes import MessageTypesModule, MessageType

        # Create an event loop to run async tasks in
        eventLoop = asyncio.new_event_loop()

        # Start hot-loop for heartbeat
        while True:
            try:
                async def sendNetInfo():
                    await MessageTypesModule.sendGlobalMessage(
                        server.playerManager,
                        f"&cTx: &f{module.txPackets} packets/s &4[{module.txBytes} bytes/s]&f  | ",
                        messageType=MessageType.BOTTOM_RIGHT_1
                    )

                    await MessageTypesModule.sendGlobalMessage(
                        server.playerManager,
                        f"&aRx: &f{module.rxPackets} packets/s &2[{module.rxBytes} bytes/s]&f  | ",
                        messageType=MessageType.BOTTOM_RIGHT_2
                    )

                    await MessageTypesModule.sendGlobalMessage(
                        server.playerManager,
                        "&dProject&5Obsidian &fNetcode Status",
                        messageType=MessageType.BOTTOM_RIGHT_3
                    )

                    module.rxPackets = 0
                    module.rxBytes = 0
                    module.txPackets = 0
                    module.txBytes = 0

                eventLoop.run_until_complete(sendNetInfo())

                time.sleep(1)
            except Exception as e:
                Logger.error(f"Unhandled exception in net info thread - {type(e).__name__}: {e}", module="netinfo", printTb=True)
                time.sleep(60)
