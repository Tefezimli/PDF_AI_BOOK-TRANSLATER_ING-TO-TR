import re
import os
import importlib.util
from typing import Tuple, Dict, List, Optional
import pymupdf as fitz

SUPERSCRIPT_MAP = str.maketrans(
    "0123456789+-=()nxyzrabcikm",
    "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207a\u207b\u207c\u207d\u207e\u207f\u02e3\u02b8\u1dbb\u02b3\u1d43\u1d47\u1d9c\u2071\u1d4f\u1d50"
)

SUBSCRIPT_MAP = str.maketrans(
    "0123456789+-=()nxyzr",
    "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089\u208a\u208b\u208c\u208d\u208e\u2099\u2093\u1d67\u2082\u1d63"
)

GLYPH_FALLBACK_MAP: Dict[str, str] = {
    "\ufd3e": "(",
    "\ufd3f": ")",
    "\u27e6": "(",
    "\u27e7": ")",
    "\u2260": "!=",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2248": "~=",
    "\u2261": "==",
    "\u00b1": "+/-",
    "\u00d7": "x",
    "\u00f7": "/",
    "\u221e": "inf",
    "\u2192": "->",
    "\u2190": "<-",
    "\u2194": "<->",
    "\u21d2": "=>",
    "\u2295": "(+)",
    "\u2022": "\u2022",
    "\u2776": "(1)", "\u2777": "(2)", "\u2778": "(3)", "\u2779": "(4)", "\u277a": "(5)",
    "\u277b": "(6)", "\u277c": "(7)", "\u277d": "(8)", "\u277e": "(9)", "\u277f": "(10)",
    "\u2780": "(1)", "\u2781": "(2)", "\u2782": "(3)", "\u2783": "(4)", "\u2784": "(5)",
    "\u2785": "(6)", "\u2786": "(7)", "\u2787": "(8)", "\u2788": "(9)", "\u2789": "(10)",
    "\u278a": "(1)", "\u278b": "(2)", "\u278c": "(3)", "\u278d": "(4)", "\u278e": "(5)",
    "\u278f": "(6)", "\u2790": "(7)", "\u2791": "(8)", "\u2792": "(9)", "\u2793": "(10)",
    "\u2460": "(1)", "\u2461": "(2)", "\u2462": "(3)", "\u2463": "(4)", "\u2464": "(5)",
    "\u2465": "(6)", "\u2466": "(7)", "\u2467": "(8)", "\u2468": "(9)", "\u2469": "(10)",
}


def replace_corrupted_brackets(text: str) -> str:
    """Arapça süslü parantezler (﴾ ﴿) ve maske köşeli parantezlerini (⟦ ⟧)
    standart ASCII ( ve ) karakterlerine çevirir."""
    return (
        text.replace("\ufd3e", "(")   # ﴾
        .replace("\ufd3f", ")")       # ﴿
        .replace("\u27e6", "(")       # ⟦
        .replace("\u27e7", ")")       # ⟧
    )


class DeterministicArtifactPurger:
    """
    Metin akışındaki tüm Arapça süslü parantezleri (\ufd3e ﴾, \ufd3f ﴿),
    PUA gliflerini ve kontrol karakterlerini sıfır toleransla standart ASCII'ye dönüştürür.
    """
    ARTIFACT_TRANSLATION_TABLE = str.maketrans({
        "\ufd3e": "(",
        "\ufd3f": ")",
        "\u27e6": "(",
        "\u27e7": ")",
        "\u3008": "<",
        "\u3009": ">",
        "\u00ab": '"',
        "\u00bb": '"',
        "\u2212": "-",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u00a0": " ",
        "\ufffd": "",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\u200e": "",
        "\u200f": "",
        "\ufeff": "",
    })
    PUA_AND_CONTROL_RE = re.compile(
        r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ue000-\uf8ff\U000f0000-\U0010ffff]'
    )
    ORNATE_BRACKET_RE = re.compile(r'[\ufd3e\ufd3f\u27e6\u27e7]')

    @classmethod
    def build_forbidden_token_ids(cls, tokenizer) -> List[List[int]]:
        bad_ids: List[List[int]] = []
        vocab = tokenizer.get_vocab()
        forbidden_chars = set("\ufd3e\ufd3f\u27e6\u27e7\ufffd")
        for token_str, token_id in vocab.items():
            if any(c in token_str for c in forbidden_chars):
                bad_ids.append([token_id])
            elif re.search(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]', token_str):
                bad_ids.append([token_id])
        return bad_ids

    @classmethod
    def sanitize_stream(cls, text: str) -> str:
        if not text:
            return ""
        t = replace_corrupted_brackets(text)
        t = cls.PUA_AND_CONTROL_RE.sub("", t)
        t = t.translate(cls.ARTIFACT_TRANSLATION_TABLE)
        t = re.sub(r'\(\s+', '(', t)
        t = re.sub(r'\s+\)', ')', t)
        return re.sub(r'\s+', ' ', t).strip()


def normalize_unicode_text(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\ufd3e", "(").replace("\ufd3f", ")")
    for dash in ["\u2212", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\uf02d"]:
        t = t.replace(dash, "-")
    for quote in ["\u2018", "\u2019", "\u201b", "\u2032", "\u0060", "\u00b4"]:
        t = t.replace(quote, "'")
    for dquote in ["\u201c", "\u201d", "\u2033"]:
        t = t.replace(dquote, '"')
    for bullet in ["\uf0b7", "\u2022", "\u25cf", "\u25aa", "\u25fe", "\u2219"]:
        t = t.replace(bullet, "\u2022 ")
    t = re.sub(r'[\uf000-\uf8ff]', '', t)
    t = (
        t.replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\ufb00", "ff")
        .replace("\ufb03", "ffi")
        .replace("\ufb04", "ffl")
        .replace("\u00a0", " ")
        .replace("\ufffd", "")
    )
    t = re.sub(r'[\u2e80-\u9fff\uf900-\ufaff]+', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def format_sub_sup_for_render(text: str, font_obj: Optional[fitz.Font] = None) -> str:
    if not text:
        return ""

    def repl_sup(m):
        val = m.group(1).strip()
        conv = val.translate(SUPERSCRIPT_MAP)
        if font_obj and not all(font_obj.has_glyph(ord(c)) for c in conv):
            return f"^{val}"
        return conv

    def repl_sub(m):
        val = m.group(1).strip()
        conv = val.translate(SUBSCRIPT_MAP)
        if font_obj and not all(font_obj.has_glyph(ord(c)) for c in conv):
            return f"_{val}"
        return conv

    res = re.sub(r'<sup:([^>]+)>', repl_sup, text)
    res = re.sub(r'<sub:([^>]+)>', repl_sub, res)
    res = re.sub(r'\u27e6INLCODE:(.*?)\u27e7', lambda m: m.group(1), res)
    res = DeterministicArtifactPurger.sanitize_stream(res)

    if font_obj:
        safe_chars = []
        for ch in res:
            if ch in "\ufd3e\u27e6":   # ﴾ ⟦
                safe_chars.append('(')
            elif ch in "\ufd3f\u27e7":  # ﴿ ⟧
                safe_chars.append(')')
            elif ch in "\r\n\t " or font_obj.has_glyph(ord(ch)):
                safe_chars.append(ch)
            elif ch in GLYPH_FALLBACK_MAP:
                safe_chars.append(GLYPH_FALLBACK_MAP[ch])
            else:
                safe_chars.append("")
        res = "".join(safe_chars)

    return DeterministicArtifactPurger.sanitize_stream(replace_corrupted_brackets(res))

# Türkçe gliflerini (ç ğ ı ö ş ü İ Ş Ğ) kapsadığı bilinen, platform bağımsız
# font adayları; Türkçe glif doğrulamasından geçen ilk çift kullanılır.
FONT_CANDIDATES: List[Tuple[str, str]] = [
    # Windows
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf"),
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    # Linux (Debian/Fedora/Arch dizin düzenleri)
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    # macOS
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]


def _bundled_font_candidates() -> List[Tuple[str, str]]:
    """pip ortamlarında matplotlib ile gelen DejaVu fontlarını yedek aday olarak ekler."""
    extra: List[Tuple[str, str]] = []
    spec = importlib.util.find_spec("matplotlib")
    if spec and spec.submodule_search_locations:
        for parent in spec.submodule_search_locations:
            base = os.path.join(str(parent), "mpl-data", "fonts", "ttf")
            extra.append((os.path.join(base, "DejaVuSans.ttf"), os.path.join(base, "DejaVuSans-Bold.ttf")))
    return extra


def select_best_unicode_fonts() -> Tuple[str, str, Optional[fitz.Font]]:
    turkish_codepoints = [ord(c) for c in "çğşıöüİŞĞ"]

    # Kullanıcı isteğe bağlı olarak kendi fontunu zorlayabilir (PDF_AI_FONT_REGULAR/BOLD).
    env_reg = os.environ.get("PDF_AI_FONT_REGULAR")
    if env_reg and os.path.exists(env_reg):
        env_bold = os.environ.get("PDF_AI_FONT_BOLD") or env_reg
        try:
            f_env = fitz.Font(fontfile=env_reg)
            if all(f_env.has_glyph(cp) for cp in turkish_codepoints):
                return env_reg, env_bold, f_env
        except Exception:
            pass

    for reg, bold in FONT_CANDIDATES + _bundled_font_candidates():
        if not os.path.exists(reg):
            continue
        try:
            f_test = fitz.Font(fontfile=reg)
            if all(f_test.has_glyph(cp) for cp in turkish_codepoints):
                return reg, (bold if os.path.exists(bold) else reg), f_test
        except Exception:
            continue

    # Hiçbir font bulunamazsa renderer dahili 'helv' fontuna düşer.
    return "", "", None
