import re
import string

LATIN_TO_CYR_TOKENS = {
    "shch": "щ",
    "sch": "щ",
    "yo": "ё",
    "jo": "ё",
    "zh": "ж",
    "kh": "х",
    "ts": "ц",
    "ch": "ч",
    "sh": "ш",
    "yu": "ю",
    "ju": "ю",
    "ya": "я",
    "ja": "я",
}

LATIN_TO_CYR_CHARS = {
    "a": "а",
    "b": "б",
    "c": "ц",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "ы",
    "z": "з",
}

CYR_TO_LATIN_CHARS = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

EN_LAYOUT = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./"
RU_LAYOUT = "ёйцукенгшщзхъфывапролджэячсмитьбю."

EN_TO_RU_LAYOUT_MAP = str.maketrans({src: dst for src, dst in zip(EN_LAYOUT, RU_LAYOUT)})
RU_TO_EN_LAYOUT_MAP = str.maketrans({src: dst for src, dst in zip(RU_LAYOUT, EN_LAYOUT)})

MAX_VARIANTS = 24
MAX_QUERY_LENGTH = 100
MIN_FUZZY_LENGTH = 4

_WHITESPACE_RE = re.compile(r"\s+")
_EXTRA_PUNCTUATION_RE = re.compile(f"[{re.escape(string.punctuation)}]+")
_REPEATED_CHAR_RE = re.compile(r"(.)\1+")
_CYRILLIC_RE = re.compile(r"[а-яё]")
_LATIN_RE = re.compile(r"[a-z]")