from src.database.search.catalog import (
    build_search_query_variants,
    convert_keyboard_layout_en_to_ru,
    convert_keyboard_layout_ru_to_en,
    normalize_search_text,
    transliterate_cyrillic_to_latin,
    transliterate_latin_to_cyrillic,
)


def test_normalize_search_text_case_spacing_and_punctuation():
    assert normalize_search_text("  ReTa -- peptide!!!  ") == "reta peptide"
    assert normalize_search_text("   ") == ""


def test_transliteration_between_latin_and_cyrillic():
    assert transliterate_latin_to_cyrillic("reta") == "рета"
    assert transliterate_cyrillic_to_latin("рета") == "reta"


def test_keyboard_layout_conversion_between_en_and_ru():
    assert convert_keyboard_layout_en_to_ru("htnf") == "рета"
    assert convert_keyboard_layout_ru_to_en("куеф") == "reta"


def test_build_search_query_variants_contains_translit_layout_and_fuzzy():
    variants = build_search_query_variants("ReTaa")
    assert "retaa" in variants
    assert "ретаа" in variants
    assert "куефф" in variants
    assert "reta" in variants  # repeated-char collapse fuzzy
    assert len(variants) <= 24
