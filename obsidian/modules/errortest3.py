from obsidian.module import Module, AbstractModule
from obsidian.packet import (
    Packet,
    AbstractRequestPacket,
    AbstractResponsePacket,
    PacketDirections
)


# Invalid Packet Name And Id Test
@Module("ErrorTestThree")
class ErrorTestThreeModule(AbstractModule):
    def __init__(self):
        super().__init__()

    @Packet(
        "Ping",
        PacketDirections.RESPONSE,
        description="Test Broken Packet"
    )
    class PingPacket(AbstractResponsePacket):
        def __init__(self):
            super().__init__(
                ID=0xff,
                FORMAT="B",
                CRITICAL=False
            )

    @Packet(
        "NotPlayerIdentification",
        PacketDirections.REQUEST,
        description="Handle First Packet Sent By Player"
    )
    class NotPlayerIdentificationPacket(AbstractRequestPacket):
        def __init__(self):
            super().__init__(
                ID=0x00,
                FORMAT="",
                CRITICAL=True,
                PLAYERLOOP=False
            )
