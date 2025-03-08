import struct

from obsidian.module import Module, AbstractModule, Dependency
from obsidian.packet import ResponsePacket, AbstractResponsePacket, packageString
from obsidian.cpe import CPE


@Module(
    "SelectionCuboid",
    description="Allows the server to highlight parts of a world.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="SelectionCuboid",
    extVersion=1,
    cpeOnly=True
)
class SelectionCuboidModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    # Packet to send to clients to create a new selection box
    @ResponsePacket(
        "MakeSelection",
        description="Creates a selection box for the client.",
    )
    class MakeSelectionPacket(AbstractResponsePacket["SelectionCuboidModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x1A,
                FORMAT="!BB64shhhhhhhhhh",
                CRITICAL=False
            )

        async def serialize(
            self,
            selectionId: int,
            label: str,
            startX: int,
            startY: int,
            startZ: int,
            endX: int,
            endY: int,
            endZ: int,
            red: int = 255,
            green: int = 255,
            blue: int = 255,
            opacity: int = 255
        ):
            # <Make Selection Packet>
            # (Byte) Packet ID
            # (Byte) Selection ID
            # (64String) Label
            # (Short) Start X
            # (Short) Start Y
            # (Short) Start Z
            # (Short) End X
            # (Short) End Y
            # (Short) End Z
            # (Short) Red
            # (Short) Green
            # (Short) Blue
            # (Short) Opacity
            msg = struct.pack(
                self.FORMAT,
                self.ID,
                selectionId,
                bytes(packageString(label)),
                startX,
                startY,
                startZ,
                endX,
                endY,
                endZ,
                red,
                green,
                blue,
                opacity
            )
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)

    # Packet to send to clients to delete a selection box
    @ResponsePacket(
        "RemoveSelection",
        description="Deletes a selection box from the client.",
    )
    class RemoveSelectionPacket(AbstractResponsePacket["SelectionCuboidModule"]):
        def __init__(self, *args):
            super().__init__(
                *args,
                ID=0x1B,
                FORMAT="!BB",
                CRITICAL=False
            )

        async def serialize(self, selectionId: int):
            # <Remove Selection Packet>
            # (Byte) Packet ID
            # (Byte) Selection ID
            msg = struct.pack(self.FORMAT, self.ID, selectionId)
            return msg

        def onError(self, *args, **kwargs):
            return super().onError(*args, **kwargs)
