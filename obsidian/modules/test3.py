__test__ = 1

from obsidian.module import Module, AbstractModule


@Module("Test3")
class TestThreeModule(AbstractModule):
    def __init__(self):
        super().__init__()
