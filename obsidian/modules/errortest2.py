from obsidian.module import Module, AbstractModule


# Repetitive Module Error Test
@Module("ErrorTestTwo")
class ErrorTestTwoModule(AbstractModule):
    def __init__(self):
        super().__init__()


@Module("ErrorTestTwo")
class ErrorTestTwoModuleTwo(AbstractModule):
    def __init__(self):
        super().__init__()
