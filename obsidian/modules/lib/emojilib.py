from obsidian.module import Module, AbstractModule, Dependency


@Module(
    "EmojiLib",
    description="Helper library for emojis",
    author="Obsidian",
    version="1.0.0",
    dependencies=[Dependency("core")]
)
class EmoteFixModule(AbstractModule):
    def __init__(self, *args):
        super().__init__(*args)
        print(Emojis.SMILE)


# Helper conversion functions between CP437 and Unicode
def unpackCP437String(data: bytearray, encoding: str = "N/A") -> str:
    try:
        return "".join([CP437_BYTE_TO_UNICODE[byte] for byte in data]).strip()
    except KeyError:
        raise ValueError("Unknown CP437 Byte In Byte Array!")


# Helper conversion functions between CP437 and Unicode
def packageCP437String(data: str, maxSize: int = 64, encoding: str = "N/A") -> bytearray:
    try:
        return bytearray([UNICODE_TO_CP437_BYTE[char] for char in data[:maxSize].ljust(maxSize)])
    except KeyError:
        raise ValueError("Unknown Unicode Character In String!")


# Helper function to replace non-ascii characters in CP437 string to a fallback character
def replaceNonAsciiCharacters(data: str, fallback: str = "?") -> str:
    return "".join([char if char.isascii() else fallback for char in data])


# String to Emoji Definitions
class Emojis:
    SMILE = WHITE_SMILE = "☺"
    BLACK_SMILE = "☻"
    HEART = HEART_SUIT = "♥"
    DIAMOND = DIAMOND_SUIT = "♦"
    CLUB = CLUB_SUIT = "♣"
    SPADE = SPADE_SUIT = "♠"
    BULLET = "•"
    INVERSE_BULLET = "◘"
    CIRCLE = "○"
    INVERSE_CIRCLE = "◙"
    MALE = MALE_GENDER = "♂"
    FEMALE = FEMALE_GENDER = "♀"
    EIGHTH_NOTE = "♪"
    BEAMED_EIGHTH_NOTES = "♫"
    SUN = "☼"
    RIGHT_TRIANGLE = BLACK_RIGHT_ARROW = BLACK_RIGHTWARDS_ARROW = "►"
    LEFT_TRIANGLE = BLACK_LEFT_ARROW = BLACK_LEFTWARDS_ARROW = "◄"
    UP_DOWN_ARROW = "↕"
    DOUBLE_EXCLAMATION_MARK = "‼"
    PILCROW = PARAGRAPH = "¶"
    SELECTION = SECTION_SIGN = "§"
    BLACK_RECTANGLE = "▬"
    UP_DOWN_ARROW_WITH_BASE = "↨"
    UP_ARROW = UPWARDS_ARROW = "↑"
    DOWN_ARROW = DOWNWARDS_ARROW = "↓"
    RIGHT_ARROW = RIGHTWARDS_ARROW = "→"
    LEFT_ARROW = LEFTWARDS_ARROW = "←"
    RIGHT_ANGLE = "∟"
    LEFT_RIGHT_ARROW = "↔"
    UP_TRIANGLE = BLACK_UP_ARROW = UPWARDS_ARROW = "▲"
    DOWN_TRIANGLE = BLACK_DOWN_ARROW = BLACK_UPWARDS_ARROW = "▼"
    HOUSE = DELTA = "⌂"
    CAPITAL_C_CEDILLA = "Ç"
    U_DIAERESIS = "ü"
    E_ACUTE = "é"
    A_CIRCUMFLEX = "â"
    A_DIAERESIS = "ä"
    A_GRAVE = "à"
    A_RING_ABOVE = "å"
    C_CEDILLA = "ç"
    E_CIRCUMFLEX = "ê"
    E_DIAERESIS = "ë"
    E_GRAVE = "è"
    I_DIAERESIS = "ï"
    I_CIRCUMFLEX = "î"
    I_GRAVE = "ì"
    A_DIAERESIS_CAPITAL = "Ä"
    A_RING_ABOVE_CAPITAL = "Å"
    E_ACUTE_CAPITAL = "É"
    AE = AE_LIGATURE = "æ"
    AE_CAPITAL = AE_LIGATURE_CAPITAL = "Æ"
    O_CIRCUMFLEX = "ô"
    O_DIAERESIS = "ö"
    O_GRAVE = "ò"
    U_CIRCUMFLEX = "û"
    U_GRAVE = "ù"
    Y_DIAERESIS = "ÿ"
    O_DIAERESIS_CAPITAL = "Ö"
    U_DIAERESIS_CAPITAL = "Ü"
    CENT = CENT_SIGN = "¢"
    POUND = POUND_SIGN = "£"
    YEN = YUAN = YEN_SIGN = YUAN_SIGN = "¥"
    PESETA = PESETA_SIGN = "₧"
    F_HOOK = "ƒ"
    A_ACUTE = "á"
    I_ACUTE = "í"
    O_ACUTE = "ó"
    U_ACUTE = "ú"
    N_TILDE = "ñ"
    N_TILDE_CAPITAL = "Ñ"
    ORDINAL_FEMININE = "ª"
    ORDINAL_MASCULINE = "º"
    QUESTION_INVERSE = "¿"
    REVERSED_NOT_SIGN = "⌐"
    NOT_SIGN = "¬"
    ONE_HALF = "½"
    ONE_FOURTH = "¼"
    INVERTED_EXCLAMATION_MARK = "¡"
    LEFT_GUILLEMET = LEFT_POINTING_DOUBLE_ANGLE_QUOTATION_MARK = "«"
    RIGHT_GUILLEMET = RIGHT_POINTING_DOUBLE_ANGLE_QUOTATION_MARK = "»"
    LIGHT_SHADE = "░"
    MEDIUM_SHADE = "▒"
    DARK_SHADE = "▓"
    BOX_DRAWINGS_LIGHT_VERTICAL = "│"
    BOX_DRAWINGS_LIGHT_VERTICAL_AND_LEFT = "┤"
    BOX_DRAWINGS_VERTICAL_SINGLE_AND_LEFT_DOUBLE = "╡"
    BOX_DRAWINGS_VERTICAL_DOUBLE_AND_LEFT_SINGLE = "╢"
    BOX_DRAWINGS_DOWN_DOUBLE_AND_LEFT_SINGLE = "╖"
    BOX_DRAWINGS_DOWN_SINGLE_AND_LEFT_DOUBLE = "╕"
    BOX_DRAWINGS_DOUBLE_VERTICAL_AND_LEFT = "╣"
    BOX_DRAWINGS_DOUBLE_VERTICAL = "║"
    BOX_DRAWINGS_DOUBLE_DOWN_AND_LEFT = "╗"
    BOX_DRAWINGS_DOUBLE_UP_AND_LEFT = "╝"
    BOX_DRAWINGS_UP_DOUBLE_AND_LEFT_SINGLE = "╜"
    BOX_DRAWINGS_UP_SINGLE_AND_LEFT_DOUBLE = "╛"
    BOX_DRAWINGS_LIGHT_DOWN_AND_LEFT = "┐"
    BOX_DRAWINGS_LIGHT_UP_AND_RIGHT = "└"
    BOX_DRAWINGS_LIGHT_UP_AND_HORIZONTAL = "┴"
    BOX_DRAWINGS_LIGHT_DOWN_AND_HORIZONTAL = "┬"
    BOX_DRAWINGS_LIGHT_VERTICAL_AND_RIGHT = "├"
    BOX_DRAWINGS_LIGHT_HORIZONTAL = "─"
    BOX_DRAWINGS_LIGHT_VERTICAL_AND_HORIZONTAL = "┼"
    BOX_DRAWINGS_VERTICAL_SINGLE_AND_RIGHT_DOUBLE = "╞"
    BOX_DRAWINGS_VERTICAL_DOUBLE_AND_RIGHT_SINGLE = "╟"
    BOX_DRAWINGS_DOUBLE_UP_AND_RIGHT = "╚"
    BOX_DRAWINGS_DOUBLE_DOWN_AND_RIGHT = "╔"
    BOX_DRAWINGS_DOUBLE_UP_AND_HORIZONTAL = "╩"
    BOX_DRAWINGS_DOUBLE_DOWN_AND_HORIZONTAL = "╦"
    BOX_DRAWINGS_DOUBLE_VERTICAL_AND_RIGHT = "╠"
    BOX_DRAWINGS_DOUBLE_HORIZONTAL = "═"
    BOX_DRAWINGS_DOUBLE_VERTICAL_AND_HORIZONTAL = "╬"
    BOX_DRAWINGS_UP_SINGLE_AND_HORIZONTAL_DOUBLE = "╧"
    BOX_DRAWINGS_UP_DOUBLE_AND_HORIZONTAL_SINGLE = "╨"
    BOX_DRAWINGS_DOWN_SINGLE_AND_HORIZONTAL_DOUBLE = "╤"
    BOX_DRAWINGS_DOWN_DOUBLE_AND_HORIZONTAL_SINGLE = "╥"
    BOX_DRAWINGS_UP_DOUBLE_AND_RIGHT_SINGLE = "╙"
    BOX_DRAWINGS_UP_SINGLE_AND_RIGHT_DOUBLE = "╘"
    BOX_DRAWINGS_DOWN_SINGLE_AND_RIGHT_DOUBLE = "╒"
    BOX_DRAWINGS_DOWN_DOUBLE_AND_RIGHT_SINGLE = "╓"
    BOX_DRAWINGS_VERTICAL_DOUBLE_AND_HORIZONTAL_SINGLE = "╫"
    BOX_DRAWINGS_VERTICAL_SINGLE_AND_HORIZONTAL_DOUBLE = "╪"
    BOX_DRAWINGS_LIGHT_UP_AND_LEFT = "┘"
    BOX_DRAWINGS_LIGHT_DOWN_AND_RIGHT = "┌"
    FULL_BLOCK = "█"
    LOWER_HALF_BLOCK = "▄"
    LEFT_HALF_BLOCK = "▌"
    RIGHT_HALF_BLOCK = "▐"
    UPPER_HALF_BLOCK = "▀"
    ALPHA = GREEK_SMALL_LETTER_ALPHA = "α"
    SHARP_S = LATIN_SMALL_LETTER_SHARP_S = BETA = GREEK_SMALL_LETTER_BETA = "ß"
    CAPITAL_GAMMA = GREEK_CAPITAL_LETTER_GAMMA = "Γ"
    PI = GREEK_SMALL_LETTER_PI = "π"
    CAPITAL_SIGMA = GREEK_CAPITAL_LETTER_SIGMA = "Σ"
    SIGMA = GREEK_SMALL_LETTER_SIGMA = "σ"
    MICRO = MICRO_SIGN = "µ"
    TAU = GREEK_SMALL_LETTER_TAU = "τ"
    CAPITAL_PHI = GREEK_CAPITAL_LETTER_PHI = "Φ"
    CAPITAL_THETA = GREEK_CAPITAL_LETTER_THETA = "Θ"
    CAPITAL_OMEGA = GREEK_CAPITAL_LETTER_OMEGA = "Ω"
    DELTA = GREEK_SMALL_LETTER_DELTA = "δ"
    INFINITY = "∞"
    PHI = GREEK_SMALL_LETTER_PHI = "φ"
    EPSILON = GREEK_SMALL_LETTER_EPSILON = "ε"
    INTERSECTION = "∩"
    IDENTICAL_TO = "≡"
    PLUS_MINUS = "±"
    GREATER_THAN_OR_EQUAL_TO = "≥"
    LESS_THAN_OR_EQUAL_TO = "≤"
    TOP_HALF_INTEGRAL = "⌠"
    BOTTOM_HALF_INTEGRAL = "⌡"
    DIVISION_SIGN = "÷"
    ALMOST_EQUAL_TO = "≈"
    DEGREE_SIGN = "°"
    BULLET_OPERATOR = "∙"
    MIDDLE_DOT = "·"
    SQUARE_ROOT = "√"
    SUPERSCRIPT_N = SUPERSCRIPT_LATIN_SMALL_LETTER_N = "ⁿ"
    SUPERSCRIPT_TWO = "²"
    BLACK_SQUARE = "■"


# CP437 Byte to Unicode Conversion
CP437_BYTE_TO_UNICODE = {
    0x00: "\0",  # Null Character
    0x01: Emojis.SMILE,
    0x02: Emojis.BLACK_SMILE,
    0x03: Emojis.HEART,
    0x04: Emojis.DIAMOND,
    0x05: Emojis.CLUB,
    0x06: Emojis.SPADE,
    0x07: Emojis.BULLET,
    0x08: Emojis.INVERSE_BULLET,
    0x09: Emojis.CIRCLE,
    0x0a: Emojis.INVERSE_CIRCLE,
    0x0b: Emojis.MALE,
    0x0c: Emojis.FEMALE,
    0x0d: Emojis.EIGHTH_NOTE,
    0x0e: Emojis.BEAMED_EIGHTH_NOTES,
    0x0f: Emojis.SUN,
    0x10: Emojis.RIGHT_TRIANGLE,
    0x11: Emojis.LEFT_TRIANGLE,
    0x12: Emojis.UP_DOWN_ARROW,
    0x13: Emojis.DOUBLE_EXCLAMATION_MARK,
    0x14: Emojis.PILCROW,
    0x15: Emojis.SELECTION,
    0x16: Emojis.BLACK_RECTANGLE,
    0x17: Emojis.UP_DOWN_ARROW_WITH_BASE,
    0x18: Emojis.UP_ARROW,
    0x19: Emojis.DOWN_ARROW,
    0x1a: Emojis.RIGHT_ARROW,
    0x1b: Emojis.LEFT_ARROW,
    0x1c: Emojis.RIGHT_ANGLE,
    0x1d: Emojis.LEFT_RIGHT_ARROW,
    0x1e: Emojis.UP_TRIANGLE,
    0x1f: Emojis.DOWN_TRIANGLE,
    **{i: chr(i) for i in range(0x20, 0x7f)},  # Add all printable ascii characters, except for DEL
    0x7f: Emojis.HOUSE,
    **{i: chr(i) for i in range(0x80, 0xFF)},  # Add all printable extended ascii characters, except for the last one
    0xFF: ""  # Invalid Character, substitute with nothing
}

# Unicode to CP437 Byte Conversion
UNICODE_TO_CP437_BYTE = {v: k for k, v in CP437_BYTE_TO_UNICODE.items()}
