from obsidian.module import Module, AbstractModule


# General Runtime Module Loading Error Test
@Module("ErrorTest")
class ErrorTestModule(AbstractModule):
    def __init__(self):
        raise Exception("Test Exception")
