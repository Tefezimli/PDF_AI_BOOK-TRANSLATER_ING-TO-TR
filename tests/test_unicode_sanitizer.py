"""core/unicode_sanitizer.py birim testleri."""
import os

import pytest

from core.unicode_sanitizer import (
    DeterministicArtifactPurger,
    FONT_CANDIDATES,
    format_sub_sup_for_render,
    normalize_unicode_text,
    replace_corrupted_brackets,
    select_best_unicode_fonts,
)


class FakeFont:
    """² ve ³ glifleri olmayan sahte font (fallback yollarını tetikler)."""

    _missing = {0xB2, 0xB3}

    def has_glyph(self, ch):
        cp = ord(ch) if isinstance(ch, str) else ch
        return cp not in self._missing


def test_replace_corrupted_brackets_all_variants():
    assert replace_corrupted_brackets("a﴾b﴿c⟦d⟧e") == "a(b)c(d)e"
    assert replace_corrupted_brackets("\ufd3e\ufd3f\u27e6\u27e7") == "()()"


def test_sanitize_stream_orphan_brackets():
    assert DeterministicArtifactPurger.sanitize_stream("Hello ﴾world﴿ brackets") == "Hello (world) brackets"


def test_sanitize_stream_mask_residue_becomes_parentheses():
    assert DeterministicArtifactPurger.sanitize_stream("⟦CODE_0⟧") == "(CODE_0)"


def test_sanitize_stream_strips_control_and_pua():
    assert DeterministicArtifactPurger.sanitize_stream("a\x07b\ue000c") == "abc"


def test_sanitize_stream_collapses_whitespace():
    assert DeterministicArtifactPurger.sanitize_stream("  a\n\n b   c ") == "a b c"


def test_sanitize_stream_empty():
    assert DeterministicArtifactPurger.sanitize_stream("") == ""


def test_normalize_unicode_ligatures_dashes_bullets():
    assert normalize_unicode_text("\ufb01ne") == "fine"
    assert normalize_unicode_text("a\u2013b\u2014c") == "a-b-c"
    assert normalize_unicode_text("x\uf0b7y") == "x• y"


def test_format_sub_sup_without_font_uses_unicode():
    assert format_sub_sup_for_render("x<sup:2> and y<sub:n>", None) == "x² and yₙ"


def test_format_sub_sup_font_fallback_to_caret():
    assert format_sub_sup_for_render("x<sup:2>", FakeFont()) == "x^2"


def test_format_sub_sup_unwraps_inline_code_marker():
    assert format_sub_sup_for_render("⟦INLCODE:clk⟧ sinyali", None) == "clk sinyali"


def _system_font_pair():
    """Türkçe glifleri bilinen gerçek bir sistem font çifti bulur (yoksa None)."""
    for reg, bold in FONT_CANDIDATES:
        if os.path.exists(reg) and os.path.exists(bold):
            return reg, bold
    return None


def test_select_fonts_env_bold_nonexistent_falls_back_to_regular(monkeypatch, capsys, tmp_path):
    pair = _system_font_pair()
    if pair is None:
        pytest.skip("Gercek sistem fontu bulunamadi; PDF_AI_FONT_BOLD dogrulama testi atlandi.")
    reg, _bold = pair
    monkeypatch.setenv("PDF_AI_FONT_REGULAR", reg)
    monkeypatch.setenv("PDF_AI_FONT_BOLD", str(tmp_path / "boyle_bir_font_yok.ttf"))
    reg_out, bold_out, _font = select_best_unicode_fonts()
    assert reg_out == reg
    assert bold_out == reg_out
    # Uyarı tam olarak bir kez basılmalı (çift uyarı olmamalı).
    assert capsys.readouterr().out.count("PDF_AI_FONT_BOLD gecersiz") == 1


def test_select_fonts_without_env_unchanged(monkeypatch, capsys):
    monkeypatch.delenv("PDF_AI_FONT_REGULAR", raising=False)
    monkeypatch.delenv("PDF_AI_FONT_BOLD", raising=False)
    reg, bold, font_obj = select_best_unicode_fonts()
    assert bold == "" or bold == reg or os.path.exists(bold)
    if reg:
        assert font_obj is not None and font_obj.has_glyph(ord("ç"))
    assert "PDF_AI_FONT_BOLD" not in capsys.readouterr().out
