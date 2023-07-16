from obsidian.module import Module, AbstractModule, Dependency
from obsidian.commands import AbstractCommand, Command
from obsidian.player import Player


@Module(
    "ColourPicker",
    description="Preview colors in chat!",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class ColourPickerModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @Command(
        "Colour",
        description="Prints out all the colors",
        version="v1.0.0"
    )
    class ColourCommand(AbstractCommand["ColourPickerModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["colours", "colors", "c"])

        async def execute(self, ctx: Player, *, msg: str = "TEST"):
            for c in "0123456789abcdef":
                await ctx.sendMessage(f"&{c}#{msg}")
