from obsidian.module import Module, AbstractModule, Dependency
from obsidian.commands import AbstractCommand, Command
from obsidian.player import Player


@Module(
    "CommandTest",
    description="Some Test Commands to Test Out Features of the Command System",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class CommandTestModule(AbstractModule):
    def __init__(self):
        super().__init__()

    @Command(
        "Test",
        description="Test Command"
    )
    class TestCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testcmd"]
            )

        async def execute(self, ctx: Player):
            # Handle Player Message
            await ctx.sendMessage("Test Command Received")

            return None  # Nothing should be returned

    @Command(
        "TestArg",
        description="Test Command With Mandatory Argument"
    )
    class TestArgCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testarg", "ta"]
            )

        async def execute(self, ctx: Player, arg):
            # Handle Player Message
            await ctx.sendMessage(f"Test Command Received With Argument {arg}")

    @Command(
        "TestArgTyped",
        description="Test Command With Mandatory Argument And Typing"
    )
    class TestArgTypedCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testargtyped", "tat"]
            )

        async def execute(self, ctx: Player, arg: int):
            # Handle Player Message
            await ctx.sendMessage(f"Test Command Received With Number {arg}")

    @Command(
        "TestArgOptional",
        description="Test Command With Optional Argument"
    )
    class TestArgOptionalCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testargoptional", "tao"]
            )

        async def execute(self, ctx: Player, arg1="optional1", arg2="optional2"):
            # Handle Player Message
            await ctx.sendMessage(f"Test Command Received With Optional Argument {arg1}, {arg2}")

    @Command(
        "TestArgTypedOptional",
        description="Test Command With Optional Typed Argument"
    )
    class TestArgTypedOptionalCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testargtypedoptional", "tato"]
            )

        async def execute(self, ctx: Player, arg: int = 256):
            # Handle Player Message
            await ctx.sendMessage(f"Test Command Received With Optional Number {arg}")

    @Command(
        "TestListArgs",
        description="Test Command To List Passed Arguments"
    )
    class TestListArgsCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testlistargs", "tla"]
            )

        async def execute(self, ctx: Player, *args):
            # Handle Player Message
            await ctx.sendMessage(f"Test Command Args {args}")

    @Command(
        "TestFirst",
        description="Test Command To Print First Word"
    )
    class TestFirstCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testfirst", "tf"]
            )

        async def execute(self, ctx: Player, first, *rest):
            # Handle Player Message
            await ctx.sendMessage(f"Test Command Arg First Word {first} Rest {rest}")

    @Command(
        "TestOptionalFirst",
        description="Test Command To Print Optional First Word"
    )
    class TestOptionalFirstCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testoptionalfirst", "tof"]
            )

        async def execute(self, ctx: Player, first="oPtIoNaL", *rest):
            # Handle Player Message
            await ctx.sendMessage(f"Test Command Arg First Word {first} Rest {rest}")

    @Command(
        "TestSay",
        description="Test Command To Repeat"
    )
    class TestSayCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testsay", "ts", "say"]
            )

        async def execute(self, ctx: Player, *, arg):
            # Handle Player Message
            await ctx.sendMessage(f"Say: {arg}")

    @Command(
        "TestOptionalSay",
        description="Test Command To Optionally Repeat"
    )
    class TestOptionalSayCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testoptionalsay", "tos"]
            )

        async def execute(self, ctx: Player, *, arg=None):
            # Handle Player Message
            if arg is not None:
                await ctx.sendMessage(f"Say: {arg}")
            else:
                await ctx.sendMessage("Say Nothing")

    @Command(
        "TestSayWithFirstWord",
        description="Test Command To Repeat While Also Saying First Word"
    )
    class TestSayWithFirstWordCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testsayfirst", "tsf"]
            )

        async def execute(self, ctx: Player, first, *, arg):
            # Handle Player Message
            await ctx.sendMessage(f"First: {first}, Rest: {arg}")

    @Command(
        "TestOptionalSayWithFirstWord",
        description="Test Command To Optionally Repeat With Optional First Word"
    )
    class TestOptionalSayWithFirstWordCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testoptionalsayfirst", "tosf"]
            )

        async def execute(self, ctx: Player, first="yolo", *, arg=None):
            # Handle Player Message
            if arg is not None:
                await ctx.sendMessage(f"First: {first}, Say: {arg}")
            else:
                await ctx.sendMessage(f"First: {first}, Say Nothing")

    # Error Testers -> These will ALWAYS result in an error!

    @Command(
        "ErrorTest",
        description="Error Test Command"
    )
    class ErrorCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["error"]
            )

        async def execute(self, ctx: Player):
            raise Exception("Test Error")

    @Command(
        "ErrorDoubleKW",
        description="Error Test Command To test Double Keyword Arguments"
    )
    class ErrorDoubleKWCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["errordoublekw", "edkw"]
            )

        async def execute(self, ctx: Player, *, arg1, arg2):
            # Handle Player Message
            await ctx.sendMessage(f"First: {arg1}, Second: {arg2}")

    @Command(
        "ErrorTypeRest",
        description="Error Test Command To test Typed KW Args"
    )
    class ErrorTypeRestCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["errortyperest", "etr"]
            )

        async def execute(self, ctx: Player, *, arg: int):
            # Handle Player Message
            await ctx.sendMessage(f"Say: {arg}")

    @Command(
        "ErrorOptionalFirstKWRest",
        description="Error Test Command To Test Optional First Vars But Mandatory KW"
    )
    class ErrorOptionalFirstKWRestsCommand(AbstractCommand):
        def __init__(self):
            super().__init__(
                ACTIVATORS=["testoptionalfirstkwrest", "tfkwr"]
            )

        async def execute(self, ctx: Player, first="yolo", *, arg):
            # Handle Player Message
            if arg is not None:
                await ctx.sendMessage(f"First: {first}, Say: {arg}")
            else:
                await ctx.sendMessage(f"First: {first}, Say Nothing")
