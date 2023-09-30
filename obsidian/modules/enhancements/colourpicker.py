from obsidian.module import Module, AbstractModule, Dependency
from obsidian.commands import AbstractCommand, Command
from obsidian.player import Player


@Module(
    "ColorPicker",
    description="Preview colors in chat!",
    author="RadioactiveHydra",
    version="1.0.0",
    dependencies=[Dependency("core")],
    soft_dependencies=[Dependency("essentials")]
)
class ColorPickerModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)

    @Command(
        "Color",
        description="Prints out all the colors",
        version="v1.0.0"
    )
    class ColorCommand(AbstractCommand["ColorPickerModule"]):
        def __init__(self, *args):
            super().__init__(*args, ACTIVATORS=["colors", "c"])

        async def execute(self, ctx: Player, *, msg: str = "TEST"):
            for c in "0123456789abcdef":
                await ctx.sendMessage(f"&{c}{c}: {msg}")
