from obsidian.module import Module, AbstractModule


@Module("Test1")
class TestOneModule(AbstractModule):
    def __init__(self):
        super().__init__()
