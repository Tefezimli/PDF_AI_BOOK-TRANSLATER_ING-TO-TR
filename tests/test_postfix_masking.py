"""Maskeli-faz / unmask sonrası kural ayrımı testleri.

POST_TRANSLATION_FIXES'ten çıkarılan "n > s" -> "n'e" ve "!=" -> "≠"
kuralları artık yalnızca maskeler (⟦CODE_n⟧/⟦MTH_n⟧) yerindeyken
(DynamicAcademicRegistry.apply_masked_phase_fixes) uygulanır. Böylece
unmask ile geri çözülen gerçek matematik değerleri ve cache'ten okunan
temiz değerler apply_post_fixes'te bozulmaz.
"""
from extractors.formalism import FormalismAnalyzer
from translators.domain_registry import DynamicAcademicRegistry
from translators.eval_harness import offline_transform


def test_post_fixes_leave_unmasked_math_alone():
    # Kurallar listeden çıktı: apply_post_fixes maskesiz metne dokunmaz.
    assert DynamicAcademicRegistry.apply_post_fixes("a != b") == "a != b"
    assert DynamicAcademicRegistry.apply_post_fixes("n > s") == "n > s"
    out = DynamicAcademicRegistry.apply_post_fixes("x != y and n > s")
    assert "\u2260" not in out and "n'e" not in out


def test_masked_phase_fixes_still_repair_artifacts():
    # Kurul davranışı yaşasın: maskesiz kalan kalıntılar masked-fazda onarılır.
    assert DynamicAcademicRegistry.apply_masked_phase_fixes("a != b") == "a \u2260 b"
    assert DynamicAcademicRegistry.apply_masked_phase_fixes("3 > s") == "3'e"


def test_masked_math_survives_roundtrip():
    # "n > s" MTH maskesine alınır; identity çeviri + masked-faz + unmask +
    # apply_post_fixes sonunda birebir korunmalı.
    text = "The condition n > s holds"
    masked, masks = FormalismAnalyzer.mask_inline_formal_tokens(text)
    assert "n > s" in masks.values()  # gerçekten maskelendi

    llm_out = DynamicAcademicRegistry.apply_masked_phase_fixes(masked)  # identity motor
    restored = FormalismAnalyzer.unmask_formal_tokens(llm_out, masks)
    restored = DynamicAcademicRegistry.apply_post_fixes(restored)
    assert "n > s" in restored
    assert "n'e" not in restored


def test_masked_phase_does_not_touch_mask_tokens():
    # Maskeli metin: gerçek matematik ⟦MTH_n⟧ içinde, çevrede kalmış "!"
    # kalıntısı onarılır ama maske anahtarları zarar görmez.
    masked, masks = FormalismAnalyzer.mask_inline_formal_tokens("if x != y then n > s")
    fixed = DynamicAcademicRegistry.apply_masked_phase_fixes(masked)
    for key in masks:
        assert key in fixed


def test_offline_transform_preserves_masked_math():
    # Deterministik zincir (offline eval) gerçek boru hattını yansıtır.
    out = offline_transform("The condition n > s holds.")
    assert "n > s" in out
    assert "n'e" not in out
