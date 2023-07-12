from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE


@Module(
    "EmoteFix",
    description="Indicates that the client can render emotes in chat properly",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="EmoteFix",
    extVersion=1,
    cpeOnly=True
)
class EmoteFixModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
