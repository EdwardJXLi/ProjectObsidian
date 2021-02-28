__test__ = 1

from obsidian.module import Module, AbstractModule


@Module("Test3", dependencies={"test1": "1.2.3", "test2": None})
class TestThreeModule(AbstractModule):
    def __init__(self):
        super().__init__()
