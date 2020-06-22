from obsidian.module import Module, AbstractModule


@Module("ErrorTest")
class ErrorTestModule(AbstractModule):
    def __init__(self):
        raise Exception("Test Exception")
