"""translators/marian_backend.py saf metin yardımcıları testleri.

Model yüklemeden, yalnızca statik/soyut metin fonksiyonlarını sınar.
"""
from translators.marian_backend import UniversalTranslationEngine


def test_split_sentences_respects_abbreviations():
    text = "A switch works. Dr. Smith said so. It amplifies!"
    parts = UniversalTranslationEngine._split_into_sentences(text)
    assert parts == ["A switch works.", "Dr. Smith said so.", "It amplifies!"]


def test_split_sentences_drops_empty_parts():
    assert UniversalTranslationEngine._split_into_sentences("Tek cümle.") == ["Tek cümle."]
    assert UniversalTranslationEngine._split_into_sentences("   ") == []
