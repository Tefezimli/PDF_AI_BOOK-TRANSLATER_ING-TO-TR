"""translators/marian_backend.py saf metin yardımcıları testleri.

Model yüklemeden, yalnızca statik/soyut metin fonksiyonlarını sınar.
"""
import types

from core.models import BoundingBox, ParagraphBlock
from translators.domain_registry import DynamicAcademicRegistry
from translators.marian_backend import UniversalTranslationEngine


def test_split_sentences_respects_abbreviations():
    text = "A switch works. Dr. Smith said so. It amplifies!"
    parts = UniversalTranslationEngine._split_into_sentences(text)
    assert parts == ["A switch works.", "Dr. Smith said so.", "It amplifies!"]


def test_split_sentences_drops_empty_parts():
    assert UniversalTranslationEngine._split_into_sentences("Tek cümle.") == ["Tek cümle."]
    assert UniversalTranslationEngine._split_into_sentences("   ") == []


# --- motor-etiketli cache anahtarı (llm|... / opus|...) ---

class _RecordingCache:
    """get/put anahtarlarını kaydeden hafif önbellek sahtesi"""

    def __init__(self, store=None):
        self.store = dict(store or {})
        self.get_keys = []
        self.put_items = []

    def get(self, key):
        self.get_keys.append(key)
        return self.store.get(key)

    def put(self, key, value):
        self.put_items.append((key, value))
        self.store[key] = value


def _make_engine(lmstudio_available: bool, llm_output="llm cevirisi", store=None):
    """translate_block'u model yüklemeden çalıştırmak için sahte motor gövdesi.

    _split_into_sentences boş döner: Opus yolu boş cümle listesinde erken
    döner, tokenizer/model hiç dokunulmaz.
    """
    return types.SimpleNamespace(
        cache=_RecordingCache(store),
        registry=DynamicAcademicRegistry(),
        lmstudio=types.SimpleNamespace(
            available=lmstudio_available,
            translate_masked_text=lambda masked: llm_output,
        ),
        _split_into_sentences=lambda text: [],
    )


def _make_block(text="The flip-flop stores one bit of data."):
    return ParagraphBlock(id=0, page_num=1, box=BoundingBox(0, 0, 10, 10), text=text)


def test_llm_engine_reads_and_writes_llm_tagged_keys():
    engine = _make_engine(lmstudio_available=True)
    result = UniversalTranslationEngine.translate_block(engine, _make_block())
    assert result == "llm cevirisi"
    expected_key = "llm|The flip-flop stores one bit of data."
    assert engine.cache.get_keys == [expected_key]
    assert engine.cache.put_items and engine.cache.put_items[0][0] == expected_key


def test_opus_engine_does_not_serve_llm_cached_translation():
    # LM Studio kapalıyken üretilmiş "llm|" kaydı, Opus-MT koşusunda ISABET etmemeli
    llm_key = "llm|The flip-flop stores one bit of data."
    engine = _make_engine(lmstudio_available=False, store={llm_key: "eski llm cevirisi"})
    UniversalTranslationEngine.translate_block(engine, _make_block())
    assert engine.cache.get_keys == ["opus|The flip-flop stores one bit of data."]


def test_llm_engine_does_not_serve_opus_cached_translation():
    # tersi: Opus ile yapılmış çeviri, LM Studio açılınca cache'ten gelmemeli
    opus_key = "opus|The flip-flop stores one bit of data."
    engine = _make_engine(lmstudio_available=True, llm_output="taze llm cevirisi", store={opus_key: "opus cevirisi"})
    result = UniversalTranslationEngine.translate_block(engine, _make_block())
    assert result == "taze llm cevirisi"
    assert engine.cache.get_keys == ["llm|The flip-flop stores one bit of data."]
