"""Bu oturumun inceleme düzeltmeleri: katı roma rakamı ve @/e-posta koruması."""
from extractors.toc_recognizer import SpatialTOCRecognizer
from translators.domain_registry import DynamicAcademicRegistry


# --- TOC PAGE_NUM_RE: katı roma rakamı ---
def test_real_roman_numerals_still_match():
    for ok in ["iv", "viii", "xiii", "xviii", "xxi", "IV", "XIII", "123", "12-34"]:
        assert SpatialTOCRecognizer.PAGE_NUM_RE.match(ok), f"sayfa no sayilmali: {ok!r}"


def test_english_words_are_not_roman_page_numbers():
    for bad in ["civil", "mild", "dim", "mid", "idli", "villain"]:
        assert not SpatialTOCRecognizer.PAGE_NUM_RE.match(bad), f"sayfa no SANILMAMALI: {bad!r}"


# --- POST_TRANSLATION_FIXES: e-posta koruması ---
def test_email_addresses_survive_post_fixes():
    text = "Bize user@example.com adresinden ulasabilirsiniz."
    assert DynamicAcademicRegistry.apply_post_fixes(text) == text


def test_spaced_at_artifact_cleaned():
    out = DynamicAcademicRegistry.apply_post_fixes("kalinti @ isareti ve a @ b kaliplari")
    assert "@" not in out
    assert "a-b" in out
