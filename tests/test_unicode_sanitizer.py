"""core/unicode_sanitizer.py birim testleri."""
from core.unicode_sanitizer import (
    DeterministicArtifactPurger,
    format_sub_sup_for_render,
    normalize_unicode_text,
    replace_corrupted_brackets,
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
