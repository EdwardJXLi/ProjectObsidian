from obsidian.module import Module, AbstractModule, Dependency
from obsidian.cpe import CPE


@Module(
    "InstantMOTD",
    description="Indicates a client supports receiving Server Identification packets at any time, not just before a map is sent.",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
@CPE(
    extName="InstantMOTD",
    extVersion=1,
    cpeOnly=True
)
class InstantMOTDModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
