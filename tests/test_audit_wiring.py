"""translate_block içine bağlanan adli denetim (maske kaybı koruması) testleri.

Motor __init__'i atlanır (torch/transformers gerekmez): sahte lmstudio + sahte
cache ile yalnız translate_block mantığı sınanır.
"""
from core.models import BoundingBox, ParagraphBlock
from translators.marian_backend import UniversalTranslationEngine


class FakeCache:
    def __init__(self):
        self.data = {}

    def get(self, k):
        return self.data.get(k)

    def put(self, k, v):
        self.data[k] = v


class MaskDroppingLLM:
    """LLM simulation: maskeleri bilerek siliyor (en sık kalite kazası)."""

    available = True
    model_id = "fake-7b"

    def __init__(self, reply):
        self.reply = reply

    def set_domain(self, label):
        pass

    def translate_masked_text(self, masked_text):
        return self.reply


def make_engine(llm):
    eng = UniversalTranslationEngine.__new__(UniversalTranslationEngine)
    eng.cache = FakeCache()
    eng.registry = __import__(
        "translators.domain_registry", fromlist=["DynamicAcademicRegistry"]
    ).DynamicAcademicRegistry()
    eng.lmstudio = llm
    return eng


def make_block(text):
    return ParagraphBlock(id=0, page_num=0, box=BoundingBox(0, 0, 10, 10), text=text)


def test_lost_mask_is_recovered_by_audit():
    # Girdi: "buffer" ve "std_logic_vector(7 downto 0)" maskelenecek.
    # Sahte LLM çeviride bunları hiç anmıyor → denetim " (std_logic_vector(7 downto 0))"
    # gibi eksik değerleri geri eklemeli.
    eng = make_engine(MaskDroppingLLM("Çoklayıcı sinyali seçer ve çıkışa aktarır."))
    result = eng.translate_block(make_block("The buffer uses std_logic_vector(7 downto 0) port."))
    assert "std_logic_vector(7 downto 0)" in result, "kaybedilen kod maskesi geri gelmeli"
    assert "CODE_" not in result and "MTH_" not in result


def test_severe_omission_falls_back_to_original():
    # LLM anlamsız kısa yanıt döndürürse denetim orijinal metne dönmeli.
    eng = make_engine(MaskDroppingLLM("ok"))
    original = "The sequential circuit stores the state information reliably across clock cycles."
    result = eng.translate_block(make_block(original))
    assert result == original


def test_healthy_translation_cached_with_engine_tag():
    eng = make_engine(MaskDroppingLLM("⟦CODE_0⟧ arabelleği ⟦CODE_1⟧ bağlantısında kullanılır."))
    eng.translate_block(make_block("The buffer uses std_logic_vector(7 downto 0) port."))
    assert any(k.startswith("llm|") for k in eng.cache.data), "cache anahtarı motor etiketi taşımalı"


def test_import_renderers_first_still_works():
    """Dairesel import koruması: renderers önce import edilirse translator yine yüklenmeli."""
    import importlib
    import renderers  # noqa: F401 — döngüyü tetikleyen sıra
    import translators.marian_backend as mb
    importlib.reload(mb)
