import re

_INLINE_WHITESPACE_RE = re.compile(r"[ \t\u00a0]+")
_PARAGRAPH_SPLIT_RE = re.compile(r"\n{2,}")
_LIST_ITEM_RE = re.compile(r"^(?:[-*•]\s+|\d+[.)]\s+)")
_WORD_FRAGMENT_RE = re.compile(r"([A-Za-zА-Яа-яЁё]+)$")
_NEXT_WORD_RE = re.compile(r"^([A-Za-zА-Яа-яЁё]+)")

_ATTACHED_PUNCTUATION = ",.;:!?%)]}"
_SENTENCE_ENDINGS = ".!?:;"


def normalize_product_text(value: str | None) -> str | None:
    if value is None: return None

    text = str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = _INLINE_WHITESPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text: return None

    paragraphs = [paragraph.strip() for paragraph in _PARAGRAPH_SPLIT_RE.split(text) if paragraph.strip()]
    normalized: list[str] = []

    for paragraph in paragraphs:
        cleaned = _normalize_paragraph(paragraph)
        if not cleaned: continue
        if normalized and _should_merge_paragraphs(normalized[-1], cleaned): normalized[-1] = _merge_chunks(normalized[-1], cleaned)
        else: normalized.append(cleaned)

    text = "\n\n".join(normalized)
    text = re.sub(r" +([,.;:!?%])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def _normalize_paragraph(paragraph: str) -> str:
    lines = [_INLINE_WHITESPACE_RE.sub(" ", line).strip() for line in paragraph.split("\n")]
    lines = [line for line in lines if line]
    if not lines: return ""

    parts = [lines[0]]
    for line in lines[1:]:
        if _should_keep_linebreak(parts[-1], line):
            parts.append(line)
            continue
        parts[-1] = _merge_chunks(parts[-1], line)

    return "\n".join(parts)


def _should_keep_linebreak(left: str, right: str) -> bool:
    if _looks_like_list_item(right): return True
    if _looks_like_list_item(left): return left.endswith(":")
    if left.endswith(":") and not right.startswith(("—", "–", "-", ",", ";", ":")): return True
    return False


def _should_merge_paragraphs(left: str, right: str) -> bool:
    right = right.lstrip()
    if not right or _looks_like_list_item(left) or _looks_like_list_item(right): return False
    if right[0] in _ATTACHED_PUNCTUATION or right[0] in "—–-([{":return True
    if right[0].islower(): return True
    if left.rstrip().endswith(("(", "[", "{", '"', "'", "—", "–", "/")): return True
    return not _ends_cleanly(left) and not _looks_like_heading(left) and not _looks_like_heading(right)


def _merge_chunks(left: str, right: str) -> str:
    left = left.rstrip()
    right = right.lstrip()
    if not left: return right
    if not right: return left

    if _should_join_without_space(left, right): separator = ""
    elif right[0] in _ATTACHED_PUNCTUATION: separator = ""
    else: separator = " "

    return f"{left}{separator}{right}"


def _should_join_without_space(left: str, right: str) -> bool:
    if left[-1].isdigit() and right[0].isdigit(): return True
    if left.endswith("-") and right[0].isalnum(): return True

    left_word = _WORD_FRAGMENT_RE.search(left)
    right_word = _NEXT_WORD_RE.match(right)
    if not left_word or not right_word: return False

    left_fragment = left_word.group(1)
    right_fragment = right_word.group(1)
    if len(right_fragment) == 1 and len(left_fragment) >= 4: return True
    return len(right_fragment) == 2 and len(left_fragment) >= 10


def _looks_like_heading(text: str) -> bool:
    if "\n" in text: return False
    compact = text.strip()
    if not compact or _looks_like_list_item(compact): return False
    if compact.endswith(":"): return True
    if any(mark in compact for mark in _SENTENCE_ENDINGS): return False

    words = compact.split()
    if len(words) > 6: return False
    first = words[0]
    return first[:1].isupper() or first[:1].isdigit()


def _looks_like_list_item(text: str) -> bool: return bool(_LIST_ITEM_RE.match(text.strip()))
def _ends_cleanly(text: str) -> bool: return text.rstrip().endswith(tuple(_SENTENCE_ENDINGS))
