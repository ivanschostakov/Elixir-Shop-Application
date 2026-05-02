from __future__ import annotations

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


def normalize_search_text(value: str | None, *, strip_punctuation: bool = True) -> str:
    if not value:
        return ""
    normalized = value.casefold().strip()
    if strip_punctuation:
        normalized = _EXTRA_PUNCTUATION_RE.sub(" ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized[:MAX_QUERY_LENGTH]


def transliterate_latin_to_cyrillic(value: str) -> str:
    text = normalize_search_text(value)
    if not text:
        return ""
    i = 0
    out: list[str] = []
    while i < len(text):
        chunk = text[i:]
        if chunk[0] == " ":
            out.append(" ")
            i += 1
            continue
        matched = False
        for token in ("shch", "sch", "yo", "jo", "zh", "kh", "ts", "ch", "sh", "yu", "ju", "ya", "ja"):
            if chunk.startswith(token):
                out.append(LATIN_TO_CYR_TOKENS[token])
                i += len(token)
                matched = True
                break
        if matched:
            continue
        out.append(LATIN_TO_CYR_CHARS.get(text[i], text[i]))
        i += 1
    return normalize_search_text("".join(out), strip_punctuation=False)


def transliterate_cyrillic_to_latin(value: str) -> str:
    text = normalize_search_text(value, strip_punctuation=False)
    if not text:
        return ""
    out = "".join(CYR_TO_LATIN_CHARS.get(ch, ch) for ch in text)
    return normalize_search_text(out)


def convert_keyboard_layout_en_to_ru(value: str) -> str:
    text = normalize_search_text(value, strip_punctuation=False)
    return normalize_search_text(text.translate(EN_TO_RU_LAYOUT_MAP), strip_punctuation=False)


def convert_keyboard_layout_ru_to_en(value: str) -> str:
    text = normalize_search_text(value, strip_punctuation=False)
    return normalize_search_text(text.translate(RU_TO_EN_LAYOUT_MAP), strip_punctuation=False)


def _contains_cyrillic(value: str) -> bool:
    return bool(_CYRILLIC_RE.search(value))


def _contains_latin(value: str) -> bool:
    return bool(_LATIN_RE.search(value))


def _fuzzy_variants(value: str) -> list[str]:
    if len(value) < MIN_FUZZY_LENGTH:
        return []

    variants: list[str] = []
    collapsed = _REPEATED_CHAR_RE.sub(r"\1", value)
    if collapsed != value:
        variants.append(collapsed)

    # One adjacent swap.
    for idx in range(len(value) - 1):
        if value[idx] == " " or value[idx + 1] == " ":
            continue
        swapped_chars = list(value)
        swapped_chars[idx], swapped_chars[idx + 1] = swapped_chars[idx + 1], swapped_chars[idx]
        variants.append("".join(swapped_chars))
        break

    # One deletion per position (bounded by MAX_VARIANTS in caller).
    for idx in range(len(value)):
        if value[idx] == " ":
            continue
        candidate = value[:idx] + value[idx + 1 :]
        if len(candidate) >= MIN_FUZZY_LENGTH - 1:
            variants.append(candidate)
    return variants


def build_search_query_variants(query: str) -> list[str]:
    base = normalize_search_text(query)
    if not base:
        return []

    variants: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        normalized = normalize_search_text(candidate)
        if not normalized:
            return
        if normalized in seen:
            return
        seen.add(normalized)
        variants.append(normalized)

    add(base)
    if _contains_latin(base):
        add(transliterate_latin_to_cyrillic(base))
        add(convert_keyboard_layout_en_to_ru(base))
    if _contains_cyrillic(base):
        add(transliterate_cyrillic_to_latin(base))
        add(convert_keyboard_layout_ru_to_en(base))

    for fuzzy in _fuzzy_variants(base):
        add(fuzzy)
        if len(variants) >= MAX_VARIANTS:
            break

    return variants[:MAX_VARIANTS]

