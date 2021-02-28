from obsidian.module import Module, AbstractModule


@Module("Test1", version="1.2.3")
class TestOneModule(AbstractModule):
    def __init__(self):
        super().__init__()
        print("\n\n\n\nHI\n\n\n\n")


@Module("Test1X", version="N/A")
class TestOneAltModule(AbstractModule):
    def __init__(self):
        super().__init__()
