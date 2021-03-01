__test__ = 1

from obsidian.module import Dependency, Module, AbstractModule


@Module("Test3", dependencies=[Dependency("test1", version="1.2.3"), Dependency("TeSt4", version="123")])
class TestThreeModule(AbstractModule):
    def __init__(self):
        super().__init__()


@Module("Test4", version="123", dependencies=[])
class TestFourModule(AbstractModule):
    def __init__(self):
        super().__init__()


@Module("Test5", dependencies=[Dependency("TeSt4")])
class TestFiveModule(AbstractModule):
    def __init__(self):
        super().__init__()


@Module("Test6", dependencies=[Dependency("TeSt4", version="000")])
class TestSixModule(AbstractModule):
    def __init__(self):
        super().__init__()


@Module("Test7", dependencies=[Dependency("Test8")])
class TestSevenModule(AbstractModule):
    def __init__(self):
        super().__init__()


@Module("Test8", dependencies=[Dependency("Test7")])
class TestEightModule(AbstractModule):
    def __init__(self):
        super().__init__()


@Module("Test9", dependencies=[Dependency("Test9")])
class TestNineModule(AbstractModule):
    def __init__(self):
        super().__init__()
