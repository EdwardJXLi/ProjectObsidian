from obsidian.module import Module, AbstractModule


@Module("Test2")
class TestTwoModule(AbstractModule):
    def __init__(self):
        super().__init__()
        # asd()
