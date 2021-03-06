from obsidian.module import Module, AbstractModule, Dependency
from obsidian.blocks import Block, AbstractBlock
from obsidian.modules.test1 import TestOneModule


@Module("Test2", dependencies=[Dependency("test1")])
class TestTwoModule(AbstractModule):
    def __init__(self):
        super().__init__()
        # asd()

    @Block("TestBlock", override=True)
    class BetterBlock(TestOneModule.TestBlock):
        def __init__(self):
            super().__init__()

    @Block("WarnTest", override=True)
    class WarnTest(AbstractBlock):
        def __init__(self):
            super().__init__(ID=100)
