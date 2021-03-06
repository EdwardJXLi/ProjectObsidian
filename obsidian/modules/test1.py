from obsidian.module import Module, AbstractModule
from obsidian.blocks import Block, AbstractBlock
# import copy


@Module("Test1", version="1.2.3")
class TestOneModule(AbstractModule):
    def __init__(self):
        super().__init__()
        print("\n\n\n\nHI\n\n\n\n")

    @Block("TestBlock")
    class TestBlock(AbstractBlock):
        def __init__(self):
            super().__init__(ID=0)

    '''
    blockList = [
        "Air",
        "Stone",
        "Grass",
        "Dirt",
        "Cobblestone",
        "Planks",
        "Sapling",
        "Bedrock",
        "FlowingWater",
        "StationaryWater",
        "FlowingLava",
        "StationaryLava",
        "Sand",
        "Gravel",
        "GoldOre",
        "IronOre",
        "CoalOre",
        "Wood",
        "Leaves",
        "Sponge",
        "Glass",
        "RedCloth",
        "OrangeCloth",
        "YellowCloth",
        "ChartreuseCloth",
        "GreenCloth",
        "Spring GreenCloth",
        "CyanCloth",
        "CapriCloth",
        "UltramarineCloth",
        "VioletCloth",
        "PurpleCloth",
        "MagentaCloth",
        "RoseCloth",
        "DarkGrayCloth",
        "LightGrayCloth",
        "WhiteCloth",
        "Dandelion",
        "Rose",
        "BrownMushroom",
        "RedMushroom",
        "BlockGold",
        "BlockIron",
        "DoubleSlab",
        "Slab",
        "Bricks",
        "TNT",
        "Bookshelf",
        "MossyCobblestone",
        "Obsidian"
    ]

    # Loop Through All Blocks And Register Block
    for block in blockList:
        # Add Block To Local Scope
        # TODO: HACKY

        # Dynamically Create Class
        @Block(block)
        class CoreBlock(AbstractBlock):
            def __init__(self):
                super().__init__(ID=TestOneModule.blockList.index(self.NAME))

        # Deep Copy Object Into Local Scope With Custom Name
        locals()["CoreBlock" + block] = copy.deepcopy(CoreBlock)

        # Delete Existing CoreBlock To Prevent Redefinitions
        del CoreBlock
    '''


@Module("Test1X", version="N/A")
class TestOneAltModule(AbstractModule):
    def __init__(self):
        super().__init__()
