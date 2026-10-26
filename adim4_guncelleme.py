import os
import py_compile

FILES = {}

# ============================================================================
# 1. CORE/UNICODE_SANITIZER.PY -> 7.109 ADET ﴾ ﴿ (\ufd3e, \ufd3f) SIFIRLAMA
# ============================================================================
FILES["core/unicode_sanitizer.py"] = r'''import os
import re
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
        t = cls.PUA_AND_CONTROL_RE.sub("", text)
        t = t.translate(cls.ARTIFACT_TRANSLATION_TABLE)
        t = t.replace("\ufd3e", "(").replace("\ufd3f", ")")
        t = t.replace("\u27e6", "(").replace("\u27e7", ")")
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
    # Her türlü PDF ve TXT çıktısında ﴾ ﴿ (\ufd3e, \ufd3f) karakterlerini kesin olarak temizle
    res = DeterministicArtifactPurger.sanitize_stream(res)

    if font_obj:
        safe_chars = []
        for ch in res:
            if ch in GLYPH_FALLBACK_MAP and ch in ("\ufd3e", "\ufd3f", "\u27e6", "\u27e7"):
                safe_chars.append(GLYPH_FALLBACK_MAP[ch])
            elif ch in "\r\n\t " or font_obj.has_glyph(ord(ch)):
                safe_chars.append(ch)
            elif ch in GLYPH_FALLBACK_MAP:
                safe_chars.append(GLYPH_FALLBACK_MAP[ch])
            else:
                safe_chars.append("")
        res = "".join(safe_chars)
    return res


def select_best_unicode_fonts() -> Tuple[str, str, Optional[fitz.Font]]:
    turkish_test_chars = "\u00e7\u011f\u015f\u0131\u00f6\u00fc\u0130\u015e\u011e"
    turkish_codepoints = [ord(c) for c in turkish_test_chars]
    candidates = [
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
        (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg):
            try:
                f_test = fitz.Font(fontfile=reg)
                if all(f_test.has_glyph(cp) for cp in turkish_codepoints):
                    return reg, (bold if os.path.exists(bold) else reg), f_test
            except Exception:
                continue

    fallback_reg = r"C:\Windows\Fonts\arial.ttf"
    f_obj = fitz.Font(fontfile=fallback_reg) if os.path.exists(fallback_reg) else None
    return fallback_reg, r"C:\Windows\Fonts\arialbd.ttf", f_obj
'''

# ============================================================================
# 2. EXTRACTORS/FORMALISM.PY -> VHDL / VERILOG TAM KARANTİNA KALKANI
# ============================================================================
FILES["extractors/formalism.py"] = r'''import re
from typing import Tuple, Dict, List, Any
from core.models import BoundingBox
from core.unicode_sanitizer import normalize_unicode_text

MONOSPACE_FONT_KEYWORDS = (
    "mono", "courier", "consolas", "inconsolata", "menlo",
    "source", "typewriter", "code", "cmtt", "lucida console",
    "dejavusansmono", "liberationsansmono", "txtt", "zi4"
)

ENGLISH_FUNCTION_WORDS = {
    "the", "a", "an", "of", "to", "in", "is", "are", "was", "were", "for", "with",
    "that", "by", "on", "as", "can", "be", "from", "which", "or", "and", "not",
    "this", "these", "those", "have", "has", "had", "but", "at", "their", "its",
    "into", "between", "through", "during", "before", "after", "above", "below",
    "more", "most", "some", "such", "no", "nor", "only", "own", "same", "so",
    "than", "too", "very", "will", "would", "should", "could", "may", "might",
    "must", "when", "where", "how", "why", "who", "whom", "whose", "you", "your",
    "we", "our", "us", "they", "them", "he", "she", "it", "if", "because", "while",
    "although", "though", "since", "until", "unless", "about", "over", "under",
    "again", "further", "then", "once", "here", "there", "all", "any", "both",
    "each", "few", "other", "another", "every", "either", "neither"
}

KNOWN_CODE_EXTENSIONS = {
    "py", "c", "cpp", "h", "hpp", "sh", "bash", "exe", "dll", "so", "dylib",
    "rb", "js", "ts", "java", "cs", "go", "rs", "php", "pl", "sql", "asm",
    "s", "o", "obj", "bin", "dat", "json", "xml", "yaml", "yml", "ini", "cfg",
    "conf", "log", "txt", "pcap", "jar", "war", "ps1", "bat", "cmd", "vbs",
    "vhd", "vhdl", "v", "sv", "all", "std_logic_1164", "numeric_std"
}

INLINE_CODE_EXACT_TOKENS = {
    "target_host", "target_port", "bind_ip", "bind_port", "client_socket",
    "server_loop", "client_handler", "handle_client", "buffer", "argc",
    "argv", "argv[]", "envp", "sys.exit", "stdin", "stdout", "stderr",
    "sockaddr", "sockaddr_in", "AF_INET", "SOCK_STREAM", "SOCK_DGRAM",
    "SOL_SOCKET", "SO_REUSEADDR", "O_RDONLY", "O_WRONLY", "O_RDWR",
    "NULL", "EOF", "TRUE", "FALSE", "None", "True", "False", "self",
    "__init__", "__main__", "__name__", "malloc", "calloc", "realloc",
    "free", "memcpy", "memset", "strcpy", "strncpy", "strcat", "strcmp",
    "strlen", "printf", "sprintf", "snprintf", "fprintf", "scanf", "gets",
    "fgets", "recv", "send", "recvfrom", "sendto", "connect", "bind",
    "listen", "accept", "ioctl", "setsockopt", "execve", "fork",
    "WaitForSingleObject", "VirtualAlloc", "CreateThread",
    "WriteProcessMemory", "ReadProcessMemory", "surgemail.exe",
    "pattern_create", "pattern_offset", "imap_fuzz", "Rex::Text",
    # VHDL / Verilog / FPGA Donanım Sinyalleri ve Anahtar Terimleri
    "std_logic", "std_logic_vector", "std_ulogic", "std_ulogic_vector",
    "posedge", "negedge", "endmodule", "endprimitive", "endtable",
    "clk", "clock", "rst", "reset", "rst_n", "reset_n", "enable", "en",
    "Q_next", "Q_reg", "D_in", "data_in", "data_out", "sel", "downto"
}

# VHDL ve Verilog satır yapılarını %100 tanıyan derleyici级 (compiler-grade) Regex
HDL_LINE_REGEX = re.compile(
    r'^(?:'
    r'library\s+ieee\b|use\s+ieee\.[a-zA-Z0-9_\.]+\b|'
    r'entity\s+[a-zA-Z_][a-zA-Z0-9_]*\s+is\b|'
    r'architecture\s+[a-zA-Z_][a-zA-Z0-9_]*\s+of\s+[a-zA-Z_][a-zA-Z0-9_]*\s+is\b|'
    r'component\s+[a-zA-Z_][a-zA-Z0-9_]*\b|'
    r'port\s*\(|generic\s*\(|port\s+map\s*\(|generic\s+map\s*\(|'
    r'(?:signal|variable|constant|subtype|type)\s+[a-zA-Z0-9_,\s]+\s*:\s*[a-zA-Z_]|'
    r'[a-zA-Z_][a-zA-Z0-9_,\s]*\s*:\s*(?:in|out|inout|buffer|std_logic|std_logic_vector|bit|integer|unsigned|signed)\b|'
    r'process\s*(?:\([^\)]*\))?\s*(?:is)?\s*$|'
    r'begin\s*$|end\s*(?:process|if|case|loop|architecture|component|[a-zA-Z_][a-zA-Z0-9_]*)?\s*;?\s*$|'
    r'when\s+.+?=>|with\s+[a-zA-Z0-9_]+\s+select\b|'
    r'module\s+[a-zA-Z_][a-zA-Z0-9_]*\s*(?:\(|#|;)|'
    r'endmodule\b|primitive\s+[a-zA-Z_]|endprimitive\b|endtable\b|'
    r'(?:input|output|inout|wire|reg|logic|parameter|localparam|supply0|supply1|tri)\s+(?:wire\s+|reg\s+|signed\s+)?(?:\[[0-9:a-zA-Z_\-\+]+\]\s*)?[a-zA-Z_]|'
    r'always\s*@\s*\(|always_ff\b|always_comb\b|always_latch\b|initial\s+begin\b|initial\b|'
    r'assign\s+[a-zA-Z_][a-zA-Z0-9_\[\]:]*\s*=|'
    r'(?:and|or|nand|nor|xor|xnor|not|buf|bufif0|bufif1)\s+(?:#\s*\([^\)]*\)\s*)?[a-zA-Z0-9_]*\s*\('
    r')',
    re.I
)


class UniversalFormalismQuarantine:
    """
    Evrensel 1D-CRF / Markov Komşuluk Karantinası:
    VHDL, Verilog, C, Python, Rust, SQL ve BNF bloklarını karakter geçiş entropisi,
    operatör yoğunluğu ve alt/üst komşu satırların formalizm enerjisiyle yakalar.
    """
    NATURAL_COLLOCATIONS = {
        "the", "of the", "in the", "to the", "for the", "on the", "with the",
        "is a", "are the", "can be", "that is", "such as", "which is", "from the",
        "by the", "as a", "into the", "between the", "through the", "this is"
    }
    FORMAL_OPERATORS = set("=<>+-*/|{}[]()^_~\\@#$%&;:!")

    @staticmethod
    def _char_class(ch: str) -> int:
        if ch.islower(): return 1
        if ch.isupper(): return 2
        if ch.isdigit(): return 3
        if ch.isspace(): return 4
        if ch in UniversalFormalismQuarantine.FORMAL_OPERATORS: return 5
        return 6

    @classmethod
    def compute_line_formal_probability(
        cls, text: str, x0: float, x1: float, col_left: float, col_right: float, is_mono: bool
    ) -> float:
        if is_mono:
            return 1.0
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        if not clean:
            return 1.0

        if HDL_LINE_REGEX.match(clean):
            return 1.0

        n = len(clean)
        transitions = 0
        classes = [cls._char_class(c) for c in clean]
        for i in range(n - 1):
            c1, c2 = classes[i], classes[i + 1]
            if c1 != c2 and not ((c1 == 2 and c2 == 1) or (c1 == 1 and c2 == 4) or (c1 == 4 and c2 in (1, 2))):
                transitions += 1
        trans_score = min(1.0, (transitions / max(1, n)) * 3.0)

        op_count = sum(1 for c in clean if c in cls.FORMAL_OPERATORS)
        multi_ops = len(re.findall(
            r'(?:<=|=>|:=|::|->|==|!=|>>|<<|\|\||&&|;\s*$|\b(?:downto|posedge|negedge|std_logic)\b|\b[a-zA-Z0-9_]+\s*:\s*(?:in|out|inout|std_logic|bit))',
            clean, re.I
        ))
        op_score = min(1.0, (op_count / max(1, n)) * 3.8 + multi_ops * 0.42)

        low_text = f" {clean.lower()} "
        colloc_hits = sum(1 for col in cls.NATURAL_COLLOCATIONS if f" {col} " in low_text)
        words = re.findall(r'[a-zA-Z]{2,}', clean)
        prose_brake = min(0.85, colloc_hits * 0.30) if len(words) >= 6 else 0.0

        col_width = max(50.0, col_right - col_left)
        indent_ratio = max(0.0, (x0 - col_left) / col_width)
        short_line_ratio = max(0.0, (col_right - x1) / col_width)
        lacks_prose_end = not clean.endswith((".", "!", "?", '"', "\u201d"))

        geo_score = 0.0
        if lacks_prose_end:
            if 0.03 < indent_ratio < 0.50:
                geo_score += 0.22
            if short_line_ratio > 0.22:
                geo_score += 0.18

        raw_prob = (0.35 * trans_score) + (0.45 * op_score) + geo_score - prose_brake
        return max(0.0, min(1.0, raw_prob))

    @classmethod
    def apply_spatial_markov_quarantine(
        cls, lines: List[Dict[str, Any]], col_left: float, col_right: float
    ) -> List[Dict[str, Any]]:
        probs = [
            1.0 if l.get("is_code", False) else cls.compute_line_formal_probability(
                l["text"], l["bbox"][0], l["bbox"][2], col_left, col_right, False
            )
            for l in lines
        ]
        smoothed = list(probs)
        n = len(lines)
        # 3-adımlı Belief Propagation ile VHDL/Verilog bloklarının tamamını kilitle
        for _ in range(3):
            new_p = list(smoothed)
            for i in range(n):
                if smoothed[i] >= 0.85 or lines[i].get("is_hdr_ftr", False):
                    continue
                prev_p = smoothed[i - 1] if i > 0 and (lines[i]["bbox"][1] - lines[i - 1]["bbox"][3]) < 22.0 else 0.0
                next_p = smoothed[i + 1] if i < n - 1 and (lines[i + 1]["bbox"][1] - lines[i]["bbox"][3]) < 22.0 else 0.0
                if prev_p > 0.58 and next_p > 0.58:
                    new_p[i] = max(smoothed[i], 0.85)
                elif (prev_p > 0.68 or next_p > 0.68) and len(lines[i]["text"].split()) <= 7:
                    if not lines[i]["text"].endswith("."):
                        new_p[i] = max(smoothed[i], 0.68)
            smoothed = new_p

        for i, l in enumerate(lines):
            if smoothed[i] >= 0.55:
                l["is_code"] = True
                l["is_formal"] = True
        return lines


class FormalismAnalyzer:
    @staticmethod
    def is_monospace_span(font_name: str, flags: int) -> bool:
        if (flags & 8) != 0:
            return True
        fn = font_name.lower()
        return any(k in fn for k in MONOSPACE_FONT_KEYWORDS)

    @staticmethod
    def is_code_line_syntax(text: str, leading_indent: float = 0.0) -> bool:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean = re.sub(r'\u27e6(?:CODE|MTH|INLCODE)[^\u27e7]*\u27e7', '', clean).strip()
        clean_no_step = re.sub(r'^[\u2776-\u2793\u2460-\u2473]\s*', '', clean).strip()
        if not clean_no_step:
            return False

        # 1. VHDL ve Verilog Donanım Tanımlama Dili (HDL) Kontrolü
        if HDL_LINE_REGEX.match(clean_no_step):
            return True

        # VHDL/Verilog yorum satırları (-- veya //) ve sinyal atamaları (<=, :=, =>)
        if re.match(r'^(?:--\s*|//\s*)', clean_no_step):
            return True
        if re.search(r'(?:<=|:=|=>)', clean_no_step) and (
            re.search(r';\s*$', clean_no_step) or len(clean_no_step.split()) <= 9
        ):
            return True
        if re.search(r'\b(?:std_logic_vector|std_logic|downto|posedge|negedge|endmodule|port\s+map)\b', clean_no_step, re.I):
            words = re.findall(r'[a-zA-Z]{2,}', clean_no_step)
            func_cnt = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
            if func_cnt / max(1, len(words)) <= 0.18 or len(words) <= 8:
                return True

        # 2. Terminal istemcileri ve konsol çıktıları
        if re.match(
            r'^(?:\$\s+|#\s+|>>>\s+|\.{3}\s+|msf\s+|msf\s*>|msf\d?\s*>|msf\s+auxiliary\(|'
            r'\[\*\]\s*|\[\+\]\s*|\[\-\]\s*|\[!\]\s*|C:\\>|root@|kali@)',
            clean_no_step
        ):
            return True

        # 3. Genel Programlama Dilleri (C/C++, Python, Java, Assembly)
        if re.match(
            r'^(?:#include\s+|#define\s+|#ifdef\s+|#ifndef\s+|#endif\b|#pragma\s+|'
            r'import\s+[a-zA-Z0-9_\.]+|from\s+[a-zA-Z0-9_\.]+\s+import\b|'
            r'def\s+[a-zA-Z_][a-zA-Z0-9_]*|class\s+[a-zA-Z_][a-zA-Z0-9_]*|'
            r'return\b|const\s+|void\s+|int\s+|char\s+|float\s+|double\s+|'
            r'unsigned\s+|struct\s+|typedef\s+|static\s+|extern\s+|public\s+|private\s+|protected\s+|'
            r'printf\b|fprintf\b|sprintf\b|snprintf\b|print_status\b|print_good\b|'
            r'print_error\b|print_line\b|print\s+["\'\(]|'
            r'mov\s+|push\s+|pop\s+|xor\s+|lea\s+|jmp\s+|call\s+|ret\b|'
            r'cmp\s+|test\s+|je\s+|jne\s+|jz\s+|jnz\s+|nop\b|db\s+|dd\s+|dw\s+|'
            r'while\s+True\s*:|while\s*\(|for\s+[a-zA-Z_][a-zA-Z0-9_,\s]*\s+in\s+|for\s*\(|'
            r'if\s+__name__\s*==|if\s*\(|elif\s+|else\s*:|try\s*:|except\b|finally\s*:|with\s+open\()',
            clean_no_step
        ):
            return True

        if re.search(r'(?:Rex::Text|pattern_create|pattern_offset)', clean_no_step):
            words = re.findall(r'[a-zA-Z]{2,}', clean_no_step)
            func_cnt = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
            if func_cnt / max(1, len(words)) <= 0.12 or len(words) < 6:
                return True

        if re.search(r';\s*$', clean_no_step) and (
            re.search(r'[=\(\)\[\]\{\}:]', clean_no_step)
            or leading_indent > 10.0
            or len(clean_no_step.split()) <= 8
        ):
            return True

        if re.search(r'[A-Za-z0-9+/=]{28,}', clean_no_step):
            return True

        if re.match(r'^(?:\.\s*){3}SNIP(?:\s*\.)*$', clean_no_step, re.I):
            return True

        if re.match(
            r'^[a-zA-Z_][a-zA-Z0-9_,\s]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?\s*(?:=|\+=|\-=|:=|<=)\s*[^\s]+',
            clean_no_step
        ):
            words = re.findall(r'[a-zA-Z]{2,}', clean_no_step)
            func_cnt = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
            if func_cnt <= 1:
                return True

        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\s*\([^\)]*\)\s*$', clean_no_step):
            return True

        if re.search(r'\b0x[0-9a-fA-F]+\b', clean_no_step) and len(clean_no_step.split()) <= 8:
            return True
        if re.match(r'^\[\*\]\s*000\d\s+(?:LIST|OK|LOGIN|CAPABILITY)\b', clean_no_step):
            return True

        return False

    @staticmethod
    def is_header_or_footer(text: str, box: BoundingBox, page_height: float) -> bool:
        clean = text.strip()
        if not clean:
            return True

        is_single_line = box.height <= 24.0 and len(clean) <= 115
        in_top_zone = box.y0 <= page_height * 0.055 or box.y1 <= page_height * 0.070
        in_bottom_zone = box.y1 >= page_height * 0.940 or box.y0 >= page_height * 0.925

        if is_single_line and (in_top_zone or in_bottom_zone):
            if re.search(
                r'(?:All\s+rights\s+reserved|All\s+rghts\s+reserved|Copyright|Addison-?Wesley|'
                r'\bChapter\s+\d+\b|\bSection\s+\d+(?:\.\d+)*\b|^\d+\s*[-–]\s*\d+$|^\d{1,4}$)',
                clean,
                re.I
            ):
                return True
            if re.match(r'^(?:\d+\s+.+|\S.+?\s+\d+)$', clean) and len(clean.split()) <= 7:
                return True

        if is_single_line and re.search(
            r'(?:Copyright\s*©?\s*\d{4}|All\s+rights\s+reserved|All\s+rghts\s+reserved|\bAddison-?Wesley\b)',
            clean,
            re.I
        ):
            return True

        if re.fullmatch(r'\d{1,3}\s*[-–]\s*\d{1,3}|\d{1,4}', clean):
            return True

        return False

    @staticmethod
    def is_formal_expression(text: str) -> bool:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean = re.sub(r'\u27e6(?:CODE|MTH|INLCODE)[^\u27e7]*\u27e7', ' codevar ', clean).strip()
        clean = re.sub(r'^[\u2022\-\+\*]\s*', '', clean).strip()
        if not clean:
            return True

        if FormalismAnalyzer.is_code_line_syntax(clean):
            return True

        words = re.findall(r'[a-zA-Z]{2,}', clean)
        word_count = len(words)
        func_word_count = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
        func_ratio = func_word_count / max(1, word_count)

        if word_count >= 4 and func_ratio > 0.12:
            if not re.search(r'(?:->|\u2192|\u2190|::=|<=|=>)', clean):
                return False

        total_len = len(clean)
        alpha_chars = sum(1 for c in clean if c.isalpha())
        digit_chars = sum(1 for c in clean if c.isdigit())
        formal_ops = set("=<>+-*/|{}[]()^_~\\@#$%&")
        sym_chars = sum(1 for c in clean if c in formal_ops)

        if alpha_chars == 0:
            return True

        has_bnf_or_arrow = bool(re.search(r'(?:->|\u2192|\u2190|::=|=>|==|!=|<=|>=|:=|<[a-zA-Z_][a-zA-Z0-9_]*>)', clean))
        has_equation = bool(re.search(r'(?:^|\s)[a-zA-Z0-9_\']+\s*[=<>\u2264\u2265\u2260\u2295]\s*[a-zA-Z0-9_\'\(\[\+\-\u03a3\u03a0]', clean))

        has_strict_dot_code = False
        for m_dot in re.finditer(r'\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)(\s*\()?', clean):
            left_p, right_p, has_paren = m_dot.group(1), m_dot.group(2), m_dot.group(3)
            if left_p.lower() in {
                "www", "http", "https", "ftp", "e", "i", "fig", "figure", "sec", "section",
                "ch", "chapter", "dr", "mr", "ms", "vs", "etc", "al", "no", "vol", "p", "pp"
            }:
                continue
            if right_p.lower() in KNOWN_CODE_EXTENSIONS:
                has_strict_dot_code = True
                break
            if has_paren or "_" in left_p or "_" in right_p:
                has_strict_dot_code = True
                break

        if (has_bnf_or_arrow or has_equation or has_strict_dot_code) and func_ratio <= 0.12:
            return True

        if (sym_chars + digit_chars) / max(1, total_len) > 0.36 and func_word_count == 0:
            return True

        if word_count <= 2 and clean.isupper() and func_word_count == 0 and len(clean) <= 20:
            return True
        if re.fullmatch(r'[A-Z]+\s+[A-Z]\.\s+[A-Z]+', clean):
            return True

        return False

    @staticmethod
    def _is_valid_inline_code_token(token: str) -> bool:
        t = token.strip()
        if not t:
            return False
        if re.match(r'^(?:CODE|MTH|INLCODE)_\d+$', t, re.I):
            return False
        if t.startswith(("CODE_", "MTH_", "INLCODE_", "\u27e6")) or t.endswith("\u27e7"):
            return False
        if re.fullmatch(r'[\u2776-\u2793\u2460-\u2473]', t):
            return True
        if len(t) < 2:
            return False
        if t in INLINE_CODE_EXACT_TOKENS:
            return True
        if re.match(r'^(?:www\.|http|e\.g\.|i\.e\.|fig\.|vs\.|[A-Z][a-z]+\.)', t, re.I):
            return False
        if "_" in t and re.search(r'[a-zA-Z]', t):
            return True
        if re.search(r'\[[0-9:a-zA-Z_\-\+]+\]$|\[\]$|\(\)$', t):
            return True
        if re.match(r'^(?:0x[0-9a-fA-F]+|\d+\'[bBhHdDoO][0-9a-fA-F_xXzZ]+)$', t):
            return True
        if re.fullmatch(r'[0-9A-Fa-f]{8}', t) and re.search(r'[A-Fa-f]', t) and re.search(r'[0-9]', t):
            return True
        if "::" in t:
            return True
        if "." in t:
            parts = t.split(".")
            if len(parts) == 2 and parts[1].lower() in KNOWN_CODE_EXTENSIONS:
                return True
            if len(parts) >= 2 and all(re.fullmatch(r'[a-z_][a-zA-Z0-9_]*', p) for p in parts):
                return True
        return False

    @staticmethod
    def mask_inline_formal_tokens(sentence: str) -> Tuple[str, Dict[str, str]]:
        t = normalize_unicode_text(sentence)
        masks: Dict[str, str] = {}
        code_idx = 0
        math_idx = 0

        def add_code_mask(val: str) -> str:
            nonlocal code_idx
            key = f"\u27e6CODE_{code_idx}\u27e7"
            masks[key] = val
            code_idx += 1
            return f" {key} "

        def add_math_mask(m) -> str:
            nonlocal math_idx
            val = m.group(0).strip()
            if (
                val.startswith(("CODE_", "MTH_", "INLCODE_", "\u27e6"))
                or val.endswith("\u27e7")
                or re.search(r'(?:CODE|MTH|INLCODE)_\d+', val, re.I)
            ):
                return val
            if val.startswith("(") and val.endswith(")"):
                inner_words = re.findall(r'[a-zA-Z]{2,}', re.sub(r'<(?:sub|sup):[^>]+>', '', val))
                if len(inner_words) >= 1 and not any(c in val for c in "=+-*/<>^_'"):
                    return val
            key = f"\u27e6MTH_{math_idx}\u27e7"
            masks[key] = val
            math_idx += 1
            return f" {key} "

        def repl_premarked(m) -> str:
            inner_val = m.group(1).strip()
            if re.match(r'^(?:CODE|MTH|INLCODE)_\d+$', inner_val, re.I):
                return inner_val
            return add_code_mask(inner_val)

        t = re.sub(r'\u27e6INLCODE:(.*?)\u27e7', repl_premarked, t)

        inline_code_pattern = (
            r'(?:'
            r'[\u2776-\u2793\u2460-\u2473]'
            r'|\b\d+\'[bBhHdDoO][0-9a-fA-F_xXzZ]+\b'
            r'|\b0x[0-9a-fA-F]+\b'
            r'|\b[0-9A-Fa-f]{8}\b'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_][a-zA-Z0-9_]*)+(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*(?:\([^\)]*\))?'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*\[[0-9:a-zA-Z_\-\+]*\]'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*\(\d+\s+(?:downto|to)\s+\d+\)'
            r'|\b(?!(?:CODE|MTH|INLCODE)_\d+\b)[a-zA-Z_][a-zA-Z0-9_]*_[a-zA-Z0-9_]+(?:\([^\)]*\))?'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*(?:\([^\)]*\))?'
            r'|\b(?:target_port|target_host|buffer|argc|argv|stdin|stdout|stderr|malloc|free|printf|recv|send|fork|execve|surgemail\.exe|pattern_create|std_logic_vector|std_logic|posedge|negedge|rst_n|clk)\b'
            r')'
        )

        def repl_inline_code(m) -> str:
            cand = m.group(0).strip()
            if (
                cand.startswith("CODE_")
                or cand.startswith("MTH_")
                or cand.startswith("INLCODE_")
                or cand.startswith("\u27e6")
                or cand.endswith("\u27e7")
                or re.match(r'^(?:CODE|MTH|INLCODE)_\d+$', cand, re.I)
            ):
                return cand
            if FormalismAnalyzer._is_valid_inline_code_token(cand):
                return add_code_mask(cand)
            return cand

        t = re.sub(inline_code_pattern, repl_inline_code, t)

        # Boolean minterm/maxterm ifadeleri: Σ(0, 2, 5), Π(1, 3, 4), F(A, B, C) = ...
        t = re.sub(
            r'(?:[\u03a3\u03a0]\s*\([0-9,\s]+\)|<[a-zA-Z_][a-zA-Z0-9_\s]*>|\{[^{}]+\}|\bC\+\+|\bC#|\.NET\b|#include\b|#define\b)',
            add_math_mask,
            t
        )

        math_atom = (
            r'(?:'
            r'\([0-9\s\+\-\*\/\^\<\>\:\_\u00b1NXYMrnABxy\']+?\)(?:<(?:sub|sup):[^>]+>)?'
            r'|[+\-]?\b(?:[0-9]+(?:\s+[0-9]{4})*|[a-zA-Z])(?:<(?:sub|sup):[^>]+>)+[a-zA-Z0-9\']*'
            r'|[+\-]?\b[0-9]+(?:\s+[0-9]{4})*\b'
            r'|[+\-]?\b[a-zA-Z]\'?(?=\s*(?:[=\u2260<>\u2264\u2265\+\*\/\u2295]|-\s*(?:[0-9\(]|[a-zA-Z]\b)))'
            r'|[+\-]?(?<=[=\u2260<>\u2264\u2265\+\-\*\/\u2295]\s)\b[a-zA-Z]\'?\b'
            r')'
        )
        t = re.sub(
            rf'{math_atom}(?:\s*(?:!=|==|<=|>=|[=\u2260<>\u2264\u2265\+\*\/\u2295]|-(?!\s*[a-zA-Z]{{2,}}))\s*{math_atom})+',
            add_math_mask,
            t
        )
        t = re.sub(r'(?:\([0-9a-zA-Z\s\+\-]+\)|[+\-]?\b[0-9a-zA-Z]+)?<(?:sub|sup):[^>]+>', add_math_mask, t)
        t = re.sub(r'\(\s*[\u00b1\+\-]?\s*[a-zA-Z0-9]\s*(?:[\-\+\|]\s*[a-zA-Z0-9]\s*)+\)', add_math_mask, t)

        return re.sub(r'\s+', ' ', t).strip(), masks

    @staticmethod
    def unmask_formal_tokens(translated: str, masks: Dict[str, str]) -> str:
        res = translated
        for key, orig in masks.items():
            m_type = "CODE" if "CODE" in key else "MTH"
            num = re.sub(r'\D', '', key)
            val = orig.strip()
            pat_bracket = rf'[\u27e6\u0028\u005b\u007b\u003c\ufd3e\u003f]\s*{m_type}[_\-]?{num}\s*[\u27e7\u0029\u005d\u007d\u003e\ufd3f\u003f]'
            res = re.sub(pat_bracket, lambda _, v=val: f" {v} ", res, flags=re.I)
            pat_bare = rf'\b{m_type}[_\-]?{num}\b'
            res = re.sub(pat_bare, lambda _, v=val: v, res, flags=re.I)
        return re.sub(r'\s+', ' ', res).strip()
'''

# ============================================================================
# 3. EXTRACTORS/TOC_RECOGNIZER.PY -> SAYFA 6-15 İÇİNDEKİLER DİKEY HİZA KİLİDİ
# ============================================================================
FILES["extractors/toc_recognizer.py"] = r'''import re
from typing import List, Dict, Any
import pymupdf as fitz
from core.models import BoundingBox, ParagraphBlock
from core.unicode_sanitizer import normalize_unicode_text


class SpatialTOCRecognizer:
    """
    Sayfa 6-15 arasındaki İçindekiler (TOC) sayfalarında sayfa numaralarının yukarıda,
    bölüm isimlerinin aşağıda kalmasını (dikey kopmayı) önleyen 2B Y-Band Hiza Motoru.
    - PyMuPDF'in sayfa numaralarını ayrı bir dikey sütun bloğuna bölmesini engeller.
    - Başlıkları ve sağdaki sayfa numaralarını aynı yatay Y-bandında (y0..y1) kilitler.
    """
    LEADER_DOTS_RE = re.compile(r'(?:\.\s*){4,}|_{4,}|-{4,}')
    PAGE_NUM_RE = re.compile(r'^(?:[ivxlcdmIVXLCDM]+|\d{1,4}(?:[\-\.]\d{1,3})?)$')
    SECTION_PREFIX_RE = re.compile(r'^(?:Chapter\s+\d+|\d+\.\d+(?:\.\d+)?)\b', re.I)

    @classmethod
    def is_toc_or_index_page(cls, page: fitz.Page, raw_spans: List[Dict[str, Any]], page_num: int = 0) -> bool:
        full_txt = page.get_text("text")
        if re.search(r'\b(?:Table\s+of\s+Contents|Contents|İçindekiler)\b', full_txt[:600], re.I):
            return True

        leader_lines = len(cls.LEADER_DOTS_RE.findall(full_txt))
        if leader_lines >= 4:
            return True

        # Sayfa 1-25 arasındaki kılavuz noktasız (modern) İçindekiler devam sayfalarını yakala
        if page_num <= 25 and raw_spans:
            page_w = page.rect.width
            right_aligned_nums = sum(
                1 for s in raw_spans
                if s["bbox"][0] > page_w * 0.62 and cls.PAGE_NUM_RE.match(s["text"].strip())
            )
            section_entries = sum(
                1 for s in raw_spans
                if s["bbox"][0] < page_w * 0.45 and cls.SECTION_PREFIX_RE.match(s["text"].strip())
            )
            if right_aligned_nums >= 5 and section_entries >= 3:
                return True
            if right_aligned_nums >= 8:
                return True

        return False

    @classmethod
    def reconstruct_toc_rows(cls, page_num: int, raw_spans: List[Dict[str, Any]], page_w: float) -> List[ParagraphBlock]:
        # Tüm span'leri dikey merkezlerine (y_center) göre sırala; Y-ekseni toleransıyla aynı satıra kilitle
        valid_spans = [s for s in raw_spans if s.get("text", "").strip()]
        sorted_spans = sorted(valid_spans, key=lambda s: ((s["bbox"][1] + s["bbox"][3]) / 2.0, s["bbox"][0]))
        y_bands: List[List[Dict[str, Any]]] = []

        for sp in sorted_spans:
            yc = (sp["bbox"][1] + sp["bbox"][3]) / 2.0
            sh = max(6.5, sp["bbox"][3] - sp["bbox"][1])
            if y_bands:
                prev_band = y_bands[-1]
                prev_yc = sum((s["bbox"][1] + s["bbox"][3]) / 2.0 for s in prev_band) / len(prev_band)
                prev_sh = max(6.5, max(s["bbox"][3] - s["bbox"][1] for s in prev_band))
                tol = max(4.5, min(sh, prev_sh) * 0.58)
                if abs(yc - prev_yc) <= tol:
                    prev_band.append(sp)
                    continue
            y_bands.append([sp])

        toc_blocks: List[ParagraphBlock] = []
        b_id = 0
        for band in y_bands:
            band.sort(key=lambda s: s["bbox"][0])
            title_spans: List[Dict[str, Any]] = []
            page_num_spans: List[Dict[str, Any]] = []
            right_bound_x0 = page_w - 15.0

            for idx_s, sp in enumerate(band):
                raw_t = normalize_unicode_text(sp["text"].strip())
                if not raw_t:
                    continue

                is_rightmost = (idx_s == len(band) - 1)
                if cls.PAGE_NUM_RE.match(raw_t) and (sp["bbox"][0] > page_w * 0.52 or (is_rightmost and len(band) >= 2 and sp["bbox"][0] > page_w * 0.42)):
                    right_bound_x0 = min(right_bound_x0, sp["bbox"][0] - 4.0)
                    page_num_spans.append(sp)
                    continue

                if cls.LEADER_DOTS_RE.search(raw_t):
                    cleaned_t = cls.LEADER_DOTS_RE.sub("", raw_t).strip()
                    m_tail_num = re.search(r'\s+(\d{1,4}|[ivxlcdmIVXLCDM]+)$', cleaned_t)
                    if m_tail_num:
                        cleaned_t = cleaned_t[:m_tail_num.start()].strip()
                    if cleaned_t:
                        sp_copy = dict(sp)
                        sp_copy["text"] = cleaned_t
                        ratio = len(cleaned_t) / max(1, len(raw_t))
                        sp_copy["bbox"] = (
                            sp["bbox"][0], sp["bbox"][1],
                            sp["bbox"][0] + (sp["bbox"][2] - sp["bbox"][0]) * min(0.85, ratio + 0.08),
                            sp["bbox"][3]
                        )
                        title_spans.append(sp_copy)
                    right_bound_x0 = min(right_bound_x0, sp["bbox"][2])
                    continue

                title_spans.append(sp)

            row_y0 = min(s["bbox"][1] for s in band)
            row_y1 = max(s["bbox"][3] for s in band)

            if title_spans:
                title_text = " ".join(normalize_unicode_text(s["text"].strip()) for s in title_spans).strip()
                title_text = re.sub(r'[\.\s]{2,}\d{1,4}$', '', title_text).strip()
                if len(title_text) >= 2 and not cls.PAGE_NUM_RE.match(title_text):
                    x0 = min(s["bbox"][0] for s in title_spans)
                    x1 = min(right_bound_x0, max(s["bbox"][2] for s in title_spans))
                    fs = max(s.get("size", 9.5) for s in title_spans)
                    is_bold = any((s.get("flags", 0) & 16) != 0 or "bold" in s.get("font", "").lower() for s in title_spans)

                    toc_blocks.append(ParagraphBlock(
                        id=b_id,
                        page_num=page_num,
                        box=BoundingBox(x0, row_y0, max(x0 + 24.0, x1), row_y1),
                        text=title_text,
                        font_size=fs,
                        is_standalone_math=False,
                        is_code_block=False,
                        is_header_footer=False,
                        is_bold=is_bold,
                        max_allowed_x1=right_bound_x0,
                        max_allowed_y1=row_y1 + 1.5
                    ))
                    b_id += 1

            # Sağdaki sayfa numarasını aynı Y koordinatında (row_y0..row_y1) korunan çapa olarak kilitle
            if page_num_spans:
                pnum_text = " ".join(s["text"].strip() for s in page_num_spans).strip()
                px0 = min(s["bbox"][0] for s in page_num_spans)
                px1 = max(s["bbox"][2] for s in page_num_spans)
                pfs = max(s.get("size", 9.5) for s in page_num_spans)
                toc_blocks.append(ParagraphBlock(
                    id=b_id,
                    page_num=page_num,
                    box=BoundingBox(px0, row_y0, px1, row_y1),
                    text=pnum_text,
                    translated_text=pnum_text,
                    font_size=pfs,
                    is_standalone_math=False,
                    is_code_block=False,
                    is_header_footer=True,
                    is_bold=False,
                    max_allowed_x1=px1 + 2.0,
                    max_allowed_y1=row_y1 + 1.0
                ))
                b_id += 1

        return toc_blocks
'''

# ============================================================================
# 4. EXTRACTORS/LAYOUT_ENGINE.PY -> TOC SAYFA NUMARASI PARAMETRESİ AKTARIMI
# ============================================================================
FILES["extractors/layout_engine.py"] = r'''import re
from typing import List, Tuple, Dict, Any, Optional
import pymupdf as fitz
from PIL import Image
import cv2
import numpy as np
import pytesseract

from core.models import BoundingBox, ParagraphBlock
from core.hardware import HAS_TESSERACT
from core.unicode_sanitizer import normalize_unicode_text
from extractors.formalism import FormalismAnalyzer, UniversalFormalismQuarantine
from extractors.toc_recognizer import SpatialTOCRecognizer


class GeometricLayoutEngine:
    def extract_paragraphs(self, page: fitz.Page, page_num: int) -> List[ParagraphBlock]:
        raw_text_blocks = page.get_text("blocks")
        has_selectable_text = any(
            b[6] == 0 and len(str(b[4]).strip()) > 0 for b in raw_text_blocks
        )

        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES)
        blocks = page_dict.get("blocks", [])

        raw_spans = [
            s for b in blocks if b.get("type") == 0
            for l in b.get("lines", [])
            for s in l.get("spans", []) if s.get("text", "").strip()
        ]
        if has_selectable_text and SpatialTOCRecognizer.is_toc_or_index_page(page, raw_spans, page_num):
            toc_rows = SpatialTOCRecognizer.reconstruct_toc_rows(page_num, raw_spans, page.rect.width)
            if len(toc_rows) >= 4:
                return toc_rows

        digital_blocks = self._extract_digital(page, page_num, blocks)

        if has_selectable_text and len(digital_blocks) > 0:
            final_blocks = digital_blocks
        else:
            final_blocks = list(digital_blocks)
            if HAS_TESSERACT:
                ocr_blocks = self._extract_scanned_ocr(page, page_num, quarantined_blocks=digital_blocks)
                if ocr_blocks:
                    print(f"   [TARANMIS SAYFA OCR] Sayfa {page_num + 1}: {len(ocr_blocks)} gorsel blok ayristirildi.")
                    final_blocks.extend(ocr_blocks)

        for idx, b in enumerate(final_blocks):
            b.id = idx

        return self._compute_two_column_and_collision_limits(final_blocks, page.rect.width, page.rect.height)

    @staticmethod
    def _detect_two_column_gutter(blocks: List[ParagraphBlock], page_w: float) -> Optional[float]:
        mid_left = page_w * 0.42
        mid_right = page_w * 0.58
        left_col = [
            b for b in blocks
            if not b.is_header_footer and b.box.width < page_w * 0.46 and b.box.x1 <= mid_right
        ]
        right_col = [
            b for b in blocks
            if not b.is_header_footer and b.box.width < page_w * 0.46 and b.box.x0 >= mid_left
        ]
        if len(left_col) >= 2 and len(right_col) >= 2:
            max_left_x1 = max(b.box.x1 for b in left_col)
            min_right_x0 = min(b.box.x0 for b in right_col)
            if min_right_x0 > max_left_x1 + 5.0:
                return (max_left_x1 + min_right_x0) / 2.0
        return None

    def _compute_two_column_and_collision_limits(
        self, blocks: List[ParagraphBlock], page_w: float, page_h: float
    ) -> List[ParagraphBlock]:
        gutter_x = self._detect_two_column_gutter(blocks, page_w)
        sorted_b = sorted(blocks, key=lambda b: (b.box.y0, b.box.x0))

        for i, b in enumerate(sorted_b):
            min_next_y0 = page_h - 8.0
            hard_right_limit = b.box.x1
            if gutter_x is not None and b.box.x1 <= gutter_x + 4.0:
                hard_right_limit = min(hard_right_limit, gutter_x - 2.0)

            for j, other in enumerate(sorted_b):
                if i == j:
                    continue
                vert_overlap = min(b.box.y1, other.box.y1) - max(b.box.y0, other.box.y0)
                if vert_overlap > 2.0 and other.box.x0 >= b.box.x1 - 2.0:
                    hard_right_limit = min(hard_right_limit, other.box.x0 - 2.0)

                horiz_overlap = min(b.box.x1, other.box.x1) - max(b.box.x0, other.box.x0)
                if horiz_overlap > 8.0 and other.box.y0 >= b.box.y1 - 1.5:
                    min_next_y0 = min(min_next_y0, other.box.y0)

            b.max_allowed_x1 = max(b.box.x0 + 16.0, hard_right_limit)
            b.max_allowed_y1 = max(b.box.y1 + 2.0, min_next_y0 - 0.8)

        return blocks

    @staticmethod
    def _int_to_rgb(color_int: int) -> Tuple[float, float, float]:
        return (((color_int >> 16) & 255) / 255.0, ((color_int >> 8) & 255) / 255.0, (color_int & 255) / 255.0)

    @staticmethod
    def _join_hyphenated_or_spaced(prev_text: str, next_text: str) -> str:
        p = prev_text.rstrip()
        n = next_text.lstrip()
        if p.endswith("-") and not p.endswith(" -") and len(n) > 0 and n[0].islower():
            return p[:-1] + n
        return f"{p} {n}"

    def _extract_digital(self, page: fitz.Page, page_num: int, blocks: List[Dict[str, Any]]) -> List[ParagraphBlock]:
        page_h = page.rect.height
        page_w = page.rect.width
        size_counts: Dict[float, int] = {}
        for b in blocks:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    txt = s.get("text", "").strip()
                    if len(txt) >= 3:
                        sz = round(s.get("size", 9.5), 1)
                        size_counts[sz] = size_counts.get(sz, 0) + len(txt)

        page_body_size = max(size_counts.items(), key=lambda x: x[1])[0] if size_counts else 9.5
        out_blocks: List[ParagraphBlock] = []
        p_idx = 0

        for b in blocks:
            if b.get("type") != 0:
                continue
            raw_lines = b.get("lines", [])
            if not raw_lines:
                continue

            block_left_x0 = min(l["bbox"][0] for l in raw_lines if "bbox" in l)
            block_right_x1 = max(l["bbox"][2] for l in raw_lines if "bbox" in l)
            sorted_raw = sorted(raw_lines, key=lambda l: (round(l["bbox"][1] / 2.5), l["bbox"][0]))
            visual_lines: List[Dict[str, Any]] = []

            for rl in sorted_raw:
                rl_bbox = rl.get("bbox", (0, 0, 0, 0))
                rl_spans = rl.get("spans", [])
                if not rl_spans:
                    continue
                if visual_lines:
                    prev = visual_lines[-1]
                    p_bbox = prev["bbox"]
                    same_row = abs(rl_bbox[1] - p_bbox[1]) < 4.0 or abs(rl_bbox[3] - p_bbox[3]) < 4.0
                    horiz_gap = rl_bbox[0] - p_bbox[2]
                    if same_row and -3.0 <= horiz_gap <= 14.0:
                        prev["spans"].extend(rl_spans)
                        prev["bbox"] = (
                            min(p_bbox[0], rl_bbox[0]), min(p_bbox[1], rl_bbox[1]),
                            max(p_bbox[2], rl_bbox[2]), max(p_bbox[3], rl_bbox[3])
                        )
                        continue
                visual_lines.append({"bbox": rl_bbox, "spans": list(rl_spans)})

            parsed_lines: List[Dict[str, Any]] = []
            for vl in visual_lines:
                spans = vl["spans"]
                normal_spans = [
                    s for s in spans
                    if s.get("text", "").strip() and s.get("size", page_body_size) >= page_body_size * 0.86
                ]
                if not normal_spans:
                    normal_spans = [s for s in spans if s.get("text", "").strip()]
                if not normal_spans:
                    continue

                ref_size = max(s.get("size", page_body_size) for s in normal_spans)
                ref_y = normal_spans[0]["origin"][1]

                total_chars = 0
                mono_chars = 0
                bold_chars = 0
                first_color = (0.0, 0.0, 0.0)

                for idx_s, s in enumerate(spans):
                    stxt = s.get("text", "").strip()
                    if not stxt:
                        continue
                    c_len = len(stxt)
                    total_chars += c_len
                    if FormalismAnalyzer.is_monospace_span(s.get("font", ""), s.get("flags", 0)):
                        mono_chars += c_len
                    if (s.get("flags", 0) & 16) or "bold" in s.get("font", "").lower():
                        bold_chars += c_len
                    if idx_s == 0 and "color" in s:
                        first_color = self._int_to_rgb(s["color"])

                line_is_monospace = (total_chars > 0) and (mono_chars / total_chars >= 0.50)

                line_str = ""
                line_sizes = []

                for s in spans:
                    raw_span = normalize_unicode_text(s.get("text", ""))
                    if not raw_span:
                        continue
                    s_size = s.get("size", ref_size)
                    s_y = s["origin"][1]
                    s_flags = s.get("flags", 0)
                    s_bbox = s.get("bbox", (0, 0, 0, 0))
                    s_height = s_bbox[3] - s_bbox[1]
                    span_is_mono = FormalismAnalyzer.is_monospace_span(s.get("font", ""), s_flags)

                    stripped = raw_span.strip()
                    is_short = 1 <= len(stripped) <= 4
                    is_smaller = (s_size < ref_size * 0.85) or (s_height < ref_size * 0.80)
                    dy = s_y - ref_y

                    if not line_is_monospace and is_short and ((s_flags & 1) or (dy < -ref_size * 0.10) or (is_smaller and dy < -ref_size * 0.04)):
                        line_str += f"<sup:{stripped}>"
                    elif not line_is_monospace and is_short and ((dy > ref_size * 0.08) or (is_smaller and dy >= 0.02)):
                        line_str += f"<sub:{stripped}>"
                    else:
                        if line_str and not line_str.endswith(" ") and not raw_span.startswith(" "):
                            line_str += " "
                        if not line_is_monospace and span_is_mono and len(stripped) >= 1:
                            line_str += f"\u27e6INLCODE:{stripped}\u27e7"
                        else:
                            line_str += raw_span
                        line_sizes.append(s_size)
                        if s_size >= ref_size * 0.88:
                            ref_y = s_y

                clean_line = re.sub(r'\s+', ' ', line_str).strip()
                if not clean_line:
                    continue

                l_bbox = vl["bbox"]
                leading_indent = max(0.0, l_bbox[0] - block_left_x0)
                is_code = line_is_monospace or FormalismAnalyzer.is_code_line_syntax(clean_line, leading_indent)
                l_box_obj = BoundingBox(l_bbox[0], l_bbox[1], l_bbox[2], l_bbox[3])
                is_hdr_ftr = FormalismAnalyzer.is_header_or_footer(clean_line, l_box_obj, page_h)
                is_formal = is_code or is_hdr_ftr or FormalismAnalyzer.is_formal_expression(clean_line)
                avg_sz = sum(line_sizes) / len(line_sizes) if line_sizes else ref_size

                parsed_lines.append({
                    "text": clean_line,
                    "bbox": l_bbox,
                    "size": avg_sz,
                    "bold": bold_chars > (total_chars * 0.45),
                    "color": first_color,
                    "is_code": is_code,
                    "is_hdr_ftr": is_hdr_ftr,
                    "is_formal": is_formal
                })

            parsed_lines = UniversalFormalismQuarantine.apply_spatial_markov_quarantine(
                parsed_lines, block_left_x0, max(block_right_x1, page_w * 0.85)
            )

            grouped: List[Dict[str, Any]] = []
            curr: Dict[str, Any] = {}

            for pl in parsed_lines:
                if curr and not curr["is_code"] and not curr["is_hdr_ftr"] and not pl["is_code"] and not pl["is_hdr_ftr"]:
                    v_gap = pl["bbox"][1] - curr["bbox"][3]
                    word_cnt = len(pl["text"].split())
                    is_orphan_tail = (
                        word_cnt <= 3
                        and not pl["text"].startswith("\u2022")
                        and not curr["text"].rstrip().endswith((".", "!", "?", ":"))
                        and v_gap <= curr["size"] * 1.30
                        and abs(pl["bbox"][0] - curr["bbox"][0]) <= 38.0
                    )
                    if is_orphan_tail:
                        curr["text"] = self._join_hyphenated_or_spaced(curr["text"], pl["text"])
                        b0, b1 = curr["bbox"], pl["bbox"]
                        curr["bbox"] = (min(b0[0], b1[0]), min(b0[1], b1[1]), max(b0[2], b1[2]), max(b0[3], b1[3]))
                        curr["is_formal"] = False
                        continue

                is_standalone = (
                    pl["is_code"]
                    or pl["is_hdr_ftr"]
                    or pl["is_formal"]
                    or pl["text"].startswith("\u2022")
                )
                if is_standalone:
                    if curr:
                        grouped.append(curr)
                        curr = {}
                    grouped.append(pl.copy())
                else:
                    if not curr:
                        curr = pl.copy()
                    else:
                        v_gap = pl["bbox"][1] - curr["bbox"][3]
                        same_style = (curr["bold"] == pl["bold"]) and (abs(curr["size"] - pl["size"]) < 1.2)
                        if v_gap > curr["size"] * 0.95 or not same_style:
                            grouped.append(curr)
                            curr = pl.copy()
                        else:
                            curr["text"] = self._join_hyphenated_or_spaced(curr["text"], pl["text"])
                            b0, b1 = curr["bbox"], pl["bbox"]
                            curr["bbox"] = (min(b0[0], b1[0]), min(b0[1], b1[1]), max(b0[2], b1[2]), max(b0[3], b1[3]))
            if curr:
                grouped.append(curr)

            for item in grouped:
                txt = item["text"].strip()
                if len(txt) < 2 and not item["is_code"]:
                    continue
                bb = item["bbox"]
                box_obj = BoundingBox(bb[0], bb[1], bb[2], bb[3])
                is_hdr_ftr = item["is_hdr_ftr"] or FormalismAnalyzer.is_header_or_footer(txt, box_obj, page_h)
                is_code = item["is_code"]
                is_math = is_code or is_hdr_ftr or FormalismAnalyzer.is_formal_expression(txt)

                out_blocks.append(ParagraphBlock(
                    id=p_idx,
                    page_num=page_num,
                    box=box_obj,
                    text=txt,
                    font_size=max(6.5, min(18.0, item["size"])),
                    is_standalone_math=is_math,
                    is_code_block=is_code,
                    is_header_footer=is_hdr_ftr,
                    is_from_ocr=False,
                    is_bold=item["bold"],
                    text_color=item["color"]
                ))
                p_idx += 1

        merged_out: List[ParagraphBlock] = []
        for blk in out_blocks:
            if (
                merged_out
                and not blk.is_code_block
                and not blk.is_header_footer
                and not merged_out[-1].is_protected
                and len(blk.text.split()) <= 3
                and not blk.text.startswith("\u2022")
                and not merged_out[-1].text.rstrip().endswith((".", "!", "?", ":"))
            ):
                prev_b = merged_out[-1]
                v_gap = blk.box.y0 - prev_b.box.y1
                if -2.0 <= v_gap <= prev_b.font_size * 1.45 and abs(blk.box.x0 - prev_b.box.x0) <= 38.0:
                    prev_b.text = self._join_hyphenated_or_spaced(prev_b.text, blk.text)
                    prev_b.box = BoundingBox(
                        min(prev_b.box.x0, blk.box.x0), min(prev_b.box.y0, blk.box.y0),
                        max(prev_b.box.x1, blk.box.x1), max(prev_b.box.y1, blk.box.y1)
                    )
                    prev_b.is_standalone_math = False
                    continue
            merged_out.append(blk)

        return merged_out

    @staticmethod
    def _sample_outer_ring(
        bgr_img: np.ndarray, x0: int, y0: int, x1: int, y1: int
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], float, float]:
        h_img, w_img = bgr_img.shape[:2]
        pad = 5
        ox0, oy0 = max(0, x0 - pad), max(0, y0 - pad)
        ox1, oy1 = min(w_img, x1 + pad), min(h_img, y1 + pad)

        outer_roi = bgr_img[oy0:oy1, ox0:ox1]
        inner_roi = bgr_img[max(0, y0):min(h_img, y1), max(0, x0):min(w_img, x1)]
        if inner_roi.size == 0 or outer_roi.size == 0:
            return (1.0, 1.0, 1.0), (0.0, 0.0, 0.0), 1.0, 0.0

        strips = [
            outer_roi[0:max(1, y0 - oy0), :, :].reshape(-1, 3),
            outer_roi[max(0, outer_roi.shape[0] - (oy1 - y1)):, :, :].reshape(-1, 3),
            outer_roi[:, 0:max(1, x0 - ox0), :].reshape(-1, 3),
            outer_roi[:, max(0, outer_roi.shape[1] - (ox1 - x1)):, :].reshape(-1, 3),
        ]
        ring_px = np.concatenate([p for p in strips if p.size > 0], axis=0)
        if ring_px.size == 0:
            ring_px = outer_roi.reshape(-1, 3)

        bg_bgr = np.median(ring_px, axis=0)
        bg_rgb = (float(bg_bgr[2]) / 255.0, float(bg_bgr[1]) / 255.0, float(bg_bgr[0]) / 255.0)
        bg_lum = 0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]
        gray_ring = 0.299 * ring_px[:, 2] + 0.587 * ring_px[:, 1] + 0.114 * ring_px[:, 0]
        bg_std = float(np.std(gray_ring))

        gray_inner = cv2.cvtColor(inner_roi, cv2.COLOR_BGR2GRAY)
        if bg_lum < 0.45:
            txt_rgb = (1.0, 1.0, 1.0)
        else:
            dark_mask = gray_inner < np.percentile(gray_inner, 22)
            if np.any(dark_mask):
                fg_bgr = np.median(inner_roi[dark_mask], axis=0)
                txt_rgb = (float(fg_bgr[2]) / 255.0, float(fg_bgr[1]) / 255.0, float(fg_bgr[0]) / 255.0)
            else:
                txt_rgb = (0.0, 0.0, 0.0)

        return bg_rgb, txt_rgb, bg_lum, bg_std

    def _extract_scanned_ocr(
        self,
        page: fitz.Page,
        page_num: int,
        quarantined_blocks: List[ParagraphBlock],
        scale: float = 2.5
    ) -> List[ParagraphBlock]:
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        elif pix.n == 1:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        else:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        quarantined_boxes = [qb.box for qb in quarantined_blocks]
        for qb in quarantined_boxes:
            x0, y0 = int(max(0, qb.x0 * scale - 3)), int(max(0, qb.y0 * scale - 3))
            x1, y1 = int(min(bgr.shape[1], qb.x1 * scale + 3)), int(min(bgr.shape[0], qb.y1 * scale + 3))
            bgr[y0:y1, x0:x1] = (255, 255, 255)

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        page_h = page.rect.height
        page_w = page.rect.width

        data = pytesseract.image_to_data(
            Image.fromarray(gray),
            lang="eng",
            config="--oem 3 --psm 3",
            output_type=pytesseract.Output.DICT
        )

        lines_raw: Dict[Tuple[int, int, int], List[Dict[str, Any]]] = {}
        for i in range(len(data["text"])):
            if int(data["level"][i]) != 5:
                continue
            word = data["text"][i].strip()
            conf = float(data["conf"][i])
            if not word or conf < 48.0:
                continue

            w_box = BoundingBox(
                data["left"][i] / scale, data["top"][i] / scale,
                (data["left"][i] + data["width"][i]) / scale, (data["top"][i] + data["height"][i]) / scale
            )
            if any(w_box.overlaps(eb, margin=2.0) for eb in quarantined_boxes):
                continue

            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines_raw.setdefault(key, []).append({
                "text": word, "conf": conf,
                "left": data["left"][i], "top": data["top"][i],
                "width": data["width"][i], "height": data["height"][i]
            })

        raw_segments: List[Dict[str, Any]] = []
        for _, words in lines_raw.items():
            words_sorted = sorted(words, key=lambda w: w["left"])
            segs: List[List[Dict[str, Any]]] = []
            curr_seg: List[Dict[str, Any]] = []
            for w in words_sorted:
                if curr_seg:
                    prev_r = curr_seg[-1]["left"] + curr_seg[-1]["width"]
                    gap = (w["left"] - prev_r) / scale
                    if gap > 18.0:
                        segs.append(curr_seg)
                        curr_seg = [w]
                        continue
                curr_seg.append(w)
            if curr_seg:
                segs.append(curr_seg)

            for seg in segs:
                line_txt = normalize_unicode_text(" ".join(w["text"] for w in seg))
                if len(line_txt) < 2:
                    continue
                avg_conf = sum(w["conf"] for w in seg) / len(seg)
                x0_px, y0_px = min(w["left"] for w in seg), min(w["top"] for w in seg)
                x1_px, y1_px = max(w["left"] + w["width"] for w in seg), max(w["top"] + w["height"] for w in seg)

                bg_rgb, txt_rgb, bg_lum, bg_std = self._sample_outer_ring(bgr, x0_px, y0_px, x1_px, y1_px)
                if bg_std > 42.0 and avg_conf < 82.0:
                    continue

                b_obj = BoundingBox(x0_px / scale, y0_px / scale, x1_px / scale, y1_px / scale)
                raw_segments.append({
                    "text": line_txt,
                    "box": b_obj,
                    "bg_color": bg_rgb,
                    "text_color": txt_rgb,
                    "bg_lum": bg_lum,
                    "is_multi_col": len(segs) > 1
                })

        raw_segments.sort(key=lambda item: (round(item["box"].y0 / 5.0), item["box"].x0))
        merged_blocks: List[ParagraphBlock] = []

        for item in raw_segments:
            b = item["box"]
            txt = item["text"]
            est_fs = max(7.0, min(18.0, b.height * 0.78))
            is_hdr_ftr = FormalismAnalyzer.is_header_or_footer(txt, b, page_h)
            is_code = FormalismAnalyzer.is_code_line_syntax(txt)
            is_formal = is_hdr_ftr or is_code or FormalismAnalyzer.is_formal_expression(txt)

            merged = False
            if not is_formal and not item["is_multi_col"]:
                for prev in reversed(merged_blocks[-3:]):
                    if prev.is_protected or prev.is_table_or_diagram_cell:
                        continue
                    single_lh = prev.font_size / 0.78
                    v_gap = b.y0 - prev.box.y1
                    left_diff = b.x0 - prev.box.x0
                    if (
                        0.0 <= v_gap <= single_lh * 0.52
                        and -14.0 <= left_diff <= 36.0
                        and abs(est_fs - prev.font_size) <= max(est_fs, prev.font_size) * 0.25
                        and not txt.startswith("\u2022")
                        and not prev.text.endswith((".", "!", "?", ";", ":"))
                    ):
                        ends_conn = bool(re.search(
                            r'\b(?:of|to|for|with|which|a|an|the|in|on|by|from|that|than|as|and|or|are|is|be|into|over|between|already|have|has|can|cannot|will|must)\s*$',
                            prev.text, re.I
                        ))
                        reaches_edge = prev.box.x1 > page_w * 0.60
                        is_short_orphan = len(txt.split()) <= 3
                        if ends_conn or is_short_orphan or (reaches_edge and txt[0].islower()):
                            prev.text = self._join_hyphenated_or_spaced(prev.text, txt)
                            prev.box = BoundingBox(
                                min(prev_b.box.x0, b.x0) if (prev_b := prev) else b.x0,
                                min(prev.box.y0, b.y0),
                                max(prev.box.x1, b.x1),
                                max(prev.box.y1, b.y1)
                            )
                            merged = True
                            break

            if not merged:
                merged_blocks.append(ParagraphBlock(
                    id=len(merged_blocks),
                    page_num=page_num,
                    box=b,
                    text=txt,
                    font_size=est_fs,
                    is_standalone_math=is_formal,
                    is_code_block=is_code,
                    is_header_footer=is_hdr_ftr,
                    is_from_ocr=True,
                    is_bold=(est_fs > 13.5) or (item["bg_lum"] < 0.42),
                    is_table_or_diagram_cell=item["is_multi_col"],
                    text_color=item["text_color"],
                    bg_color=item["bg_color"]
                ))

        return merged_blocks
'''

# ============================================================================
# 5. TRANSLATORS/DOMAIN_REGISTRY.PY -> IEEE DONANIM MÜHENDİSLİĞİ TERMİNOLOJİSİ
# ============================================================================
FILES["translators/domain_registry.py"] = r'''import re
from collections import Counter
from typing import List, Tuple
import pymupdf as fitz

# Çeviri Öncesi (Pre-Normalization) IEEE Donanım ve Bilgisayar Mühendisliği Kilitleri
ENGLISH_PRE_NORMALIZATION = [
    # 1. Don't-Care Conditions -> Farketmez durumlar
    (r"\bdon[\'\u2019`]?t[\-\s]+care\s+conditions\b", "farketmez durumlar (don't-care conditions)"),
    (r"\bdon[\'\u2019`]?t[\-\s]+care\s+condition\b", "farketmez durum (don't-care condition)"),
    (r"\bdon[\'\u2019`]?t[\-\s]+care\s+terms\b", "farketmez terimler"),
    (r"\bdon[\'\u2019`]?t[\-\s]+care\s+minterms\b", "farketmez mintermler"),
    (r"\bdon[\'\u2019`]?t[\-\s]+cares\b", "farketmez durumlar"),
    (r"\bdon[\'\u2019`]?t[\-\s]+care\b", "farketmez (don't-care)"),

    # 2. Prime Implicants -> Asal bileşenler / Asal kapsayanlar
    (r"\bessential\s+prime\s+implicants\b", "temel asal kapsayanlar (essential prime implicants)"),
    (r"\bessential\s+prime\s+implicant\b", "temel asal kapsayan (essential prime implicant)"),
    (r"\bprime\s+implicants\b", "asal kapsayanlar (asal bileşenler)"),
    (r"\bprime\s+implicant\b", "asal kapsayan (asal bileşen)"),
    (r"\bimplicants\b", "kapsayanlar (bileşenler)"),
    (r"\bimplicant\b", "kapsayan (bileşen)"),

    # 3. Sum of Products (SOP) & Product of Sums (POS)
    (r"\bsum[\-\s]+of[\-\s]+products\b", "Çarpımların Toplamı (SOP)"),
    (r"\bproduct[\-\s]+of[\-\s]+sums\b", "Toplamların Çarpımı (POS)"),
    (r"\bsum\s+of\s+minterms\b", "mintermlerin toplamı"),
    (r"\bproduct\s+of\s+maxterms\b", "makstermlerin çarpımı"),
    (r"\bproduct\s+terms\b", "çarpım terimleri"),
    (r"\bproduct\s+term\b", "çarpım terimi"),
    (r"\bsum\s+terms\b", "toplam terimleri"),
    (r"\bsum\s+term\b", "toplam terimi"),

    # 4. Port, Latch, Flip-Flop, MUX, DEMUX, FSM, Timing
    (r"\binput[\-\s]+output\s+ports\b", "giriş-çıkış portları"),
    (r"\binput\s+ports\b", "giriş portları"),
    (r"\binput\s+port\b", "giriş portu"),
    (r"\boutput\s+ports\b", "çıkış portları"),
    (r"\boutput\s+port\b", "çıkış portu"),
    (r"\bSR\s+latch\b", "SR mandal devresi (SR latch)"),
    (r"\bD\s+latch\b", "D mandal devresi (D latch)"),
    (r"\blatches\b", "mandal devreleri (latches)"),
    (r"\blatch\b", "mandal devresi (latch)"),
    (r"\bflip[\-\s]+flops\b", "flip-flop devreleri"),
    (r"\bflip[\-\s]+flop\b", "flip-flop"),
    (r"\btiming\s+diagrams\b", "zamanlama diyagramları"),
    (r"\btiming\s+diagram\b", "zamanlama diyagramı"),
    (r"\bclock\s+skew\b", "saat kayması (clock skew)"),
    (r"\bpropagation\s+delays\b", "yayılım gecikmeleri"),
    (r"\bpropagation\s+delay\b", "yayılım gecikmesi"),
    (r"\bmultiplexers\b", "çoklayıcılar (MUX)"),
    (r"\bmultiplexer\b", "çoklayıcı (MUX)"),
    (r"\bdemultiplexers\b", "ters çoklayıcılar (DEMUX)"),
    (r"\bdemultiplexer\b", "ters çoklayıcı (DEMUX)"),
    (r"\bfinite\s+state\s+machines\b", "Sonlu Durum Makineleri (FSM)"),
    (r"\bfinite\s+state\s+machine\b", "Sonlu Durum Makinesi (FSM)"),
    (r"\bstate\s+machines\b", "durum makineleri (FSM)"),
    (r"\bstate\s+machine\b", "durum makinesi (FSM)"),
    (r"\bstate\s+table\b", "durum tablosu"),
    (r"\bstate\s+diagram\b", "durum diyagramı"),
    (r"\btruth\s+table\b", "doğruluk tablosu"),
    (r"\bexcitation\s+table\b", "uyarım tablosu"),
    (r"\bcharacteristic\s+table\b", "karakteristik tablo"),
    (r"\bKarnaugh\s+map\b", "Karnaugh haritası (K-map)"),
    (r"\bK[\-\s]map\b", "K-haritası (K-map)"),
    (r"\bfan[\-\s]+out\b", "çıkış yükleme kapasitesi (fan-out)"),
    (r"\bfan[\-\s]+in\b", "giriş kapasitesi (fan-in)"),
    (r"\bnoise\s+margin\b", "gürültü payı"),
    (r"\bpower\s+dissipation\b", "güç tüketimi"),
    (r"\bthree[\-\s]+state\s+gates?\b", "üç durumlu (tri-state) kapılar"),
    (r"\btri[\-\s]+state\b", "üç durumlu (tri-state)"),

    # 5. Şekil / Tablo / Örnek / Bölüm Standartlaştırması
    (r"\bFigures?\s+(\d+(?:[\.\-]\d+)*)\b", r"Şekil \1"),
    (r"\bFig\.\s*(\d+(?:[\.\-]\d+)*)\b", r"Şekil \1"),
    (r"\bTables?\s+(\d+(?:[\.\-]\d+)*)\b", r"Tablo \1"),
    (r"\bExamples?\s+(\d+(?:[\.\-]\d+)*)\b", r"Örnek \1"),
    (r"\bSections?\s+(\d+(?:[\.\-]\d+)*)\b", r"Bölüm \1"),

    # 6. Programlama Dilleri & İkilik Aritmetik
    (r"\bContext-Free\s+Grammars\b", "Bağlamdan Bağımsız Dilbilgileri"),
    (r"\bcontext-free\s+grammars\b", "bağlamdan bağımsız dilbilgileri"),
    (r"\bContext-Free\s+Grammar\b", "Bağlamdan Bağımsız Dilbilgisi"),
    (r"\bcontext-free\s+grammar\b", "bağlamdan bağımsız dilbilgisi"),
    (r"\bDenotational\s+Semantics\b", "Gösterimsel Anlambilim"),
    (r"\bOperational\s+Semantics\b", "İşlemsel Anlambilim"),
    (r"\bAxiomatic\s+Semantics\b", "Belitsel Anlambilim"),
    (r"\bStatic\s+Semantics\b", "Statik Anlambilim"),
    (r"\bDynamic\s+Semantics\b", "Dinamik Anlambilim"),
    (r"\bAttribute\s+Grammars\b", "Öznitelik Dilbilgileri"),
    (r"\bAttribute\s+Grammar\b", "Öznitelik Dilbilgisi"),
    (r"\bImmunity\s+Debugger\b", "\u27e6INLCODE:Immunity Debugger\u27e7"),
    (r"\bVisual\s+Studio\s*\.NET\b", "\u27e6INLCODE:Visual Studio .NET\u27e7"),
    (r"\bcost\s+of\s+execution\b", "cost of program runtime"),
    (r"\bexecution\s+costs\b", "program runtime costs"),
    (r"\bfor\s+execution\b", "for running the program"),
    (r"\bat\s+compile\s+time\b", "derleme zamanında"),
    (r"\bat\s+run\s+time\b", "çalışma zamanında"),
    (r"\bsigned-([0-9a-zA-Z]+)'s-complement\b", r"signed \1's complement"),
    (r"\b([0-9a-zA-Z]+)'s-complement\b", r"\1's complement"),
    (r"\bsigned-magnitude\b", "signed magnitude"),
    (r"\bsigned-complement\b", "signed complement"),
    (r"\bend-around carry\b", "end around carry"),
]

# Çeviri Sonrası (Post-Translation) Kesin Onarım ve Gaf Temizleme Kuralları
POST_TRANSLATION_FIXES = [
    # 0. Süslü parantez ve bozuk sembol kalıntıları
    (r'[\ufd3e\u27e6]', '('),
    (r'[\ufd3f\u27e7]', ')'),
    (r'(\w)\s*@\s*(\w)', r'\1-\2'),
    (r'@', ''),
    (r'\b([0-9a-zA-Z]+)\s*>\s*s\b', r"\1'e"),
    (r'!=', '\u2260'),

    # 1. "Don't-Care Conditions" -> "Bakım Koşulları" Gafının Kesin Onarımı
    (r'\b[Bb]akım\s+koşulları(?:nın|na|nı|ndan|nda)?\b', 'farketmez durumları'),
    (r'\b[Bb]akım\s+koşulu(?:nun|na|nu|ndan|nda)?\b', 'farketmez durumu'),
    (r'\b[Bb]akım\s+şartları(?:nın|na|nı|ndan|nda)?\b', 'farketmez durumları'),
    (r'\b[Bb]akım\s+şartı(?:nın|na|nı|ndan|nda)?\b', 'farketmez durumu'),
    (r'\b[Bb]akım\s+durumları\b', 'farketmez durumları'),
    (r'\bumursamazlık\s+koşulları\b', 'farketmez durumları'),
    (r'\bönemsenmeyen\s+koşullar\b', 'farketmez durumlar'),

    # 2. "Prime Implicants" -> "Asal İmplantlar" Gafının Kesin Onarımı
    (r'\b[Tt]emel\s+asal\s+implantlar(?:ın|a|ı|dan|da)?\b', 'temel asal kapsayanlar'),
    (r'\b[Aa]sal\s+implantlar(?:ın|a|ı|dan|da)?\b', 'asal kapsayanlar (asal bileşenler)'),
    (r'\b[Aa]sal\s+implant(?:ın|a|ı|tan|ta)?\b', 'asal kapsayan (asal bileşen)'),
    (r'\b[Bb]irincil\s+implantlar\b', 'asal kapsayanlar'),
    (r'\b[Bb]irincil\s+implant\b', 'asal kapsayan'),
    (r'\bimplantlar\b', 'kapsayanlar (bileşenler)'),
    (r'\bimplant\b', 'kapsayan (bileşen)'),

    # 3. "Sum of Products (SOP)" -> "Ürünlerin Toplamı" Gafının Kesin Onarımı
    (r'\b[Üü]rünlerin\s+[Tt]oplamı\b', 'Çarpımların Toplamı'),
    (r'\b[Üü]rün\s+toplamı\b', 'Çarpımların toplamı'),
    (r'\b[Tt]oplamların\s+[Üü]rünü\b', 'Toplamların Çarpımı'),
    (r'\b[Üü]rün\s+terimleri(?:nin|ne|ni|nden|nde)?\b', 'çarpım terimleri'),
    (r'\b[Üü]rün\s+terimi(?:nin|ne|ni|nden|nde)?\b', 'çarpım terimi'),

    # 4. "Port" -> "Liman" Gafının Kesin Onarımı
    (r'\bgiriş[\-\s]*çıkış\s+limanları\b', 'giriş-çıkış portları'),
    (r'\bgiriş\s+limanları\b', 'giriş portları'),
    (r'\bgiriş\s+limanı\b', 'giriş portu'),
    (r'\bçıkış\s+limanları\b', 'çıkış portları'),
    (r'\bçıkış\s+limanı\b', 'çıkış portu'),
    (r'\bvarlığın\s+limanı\b', 'varlığın (entity) portu'),
    (r'\b[Ll]imanların\b', 'portların'),
    (r'\b[Ll]imanlara\b', 'portlara'),
    (r'\b[Ll]imanları\b', 'portları'),
    (r'\b[Ll]imanlar\b', 'portlar'),
    (r'\b[Ll]imanın\b', 'portun'),
    (r'\b[Ll]imana\b', 'porta'),
    (r'\b[Ll]imanı\b', 'portu'),
    (r'\b[Ll]imanda\b', 'portta'),
    (r'\b[Ll]imandan\b', 'porttan'),
    (r'\b[Ll]iman\b', 'port'),

    # 5. "Latch" -> "Mandal" & "Figure" -> "Figür" Onarımları
    (r'\bSR\s+mandalı\b', 'SR mandal devresi (SR latch)'),
    (r'\bD\s+mandalı\b', 'D mandal devresi (D latch)'),
    (r'\bmandal\s+devresi\s+\(latch\)\s+devresi\b', 'mandal devresi (latch)'),
    (r'\b[Ff]igür\s+(\d+(?:[\.\-]\d+)*)\b', r'Şekil \1'),
    (r'\b[Bb]ölüm\s+Bölüm\s+(\d+)\b', r'Bölüm \1'),
    (r'\b[Şş]ekil\s+Şekil\s+(\d+)\b', r'Şekil \1'),

    # 6. Diğer Akademik Terim Düzeltmeleri
    (r'\b[İi]dam\s+maliyetine\b', 'Yürütme maliyetine'),
    (r'\b[İi]dam\s+masrafları\b', 'yürütme maliyetleri'),
    (r'\b[İi]dam\b', 'yürütme'),
    (r'\bsaf\s+tercümanlar\b', 'saf yorumlayıcılar'),
    (r'\btercümanlar\b', 'yorumlayıcılar'),
    (r'\btercümanı\b', 'yorumlayıcısı'),
    (r'\btercümanın\b', 'yorumlayıcının'),
    (r'\bTercüman\b', 'Yorumlayıcı'),
    (r'\btercüman\b', 'yorumlayıcı'),
    (r'\bBağışıklık\s+Hata\s+Ayıklayıcısını\b', 'Immunity Debugger aracını'),
    (r'\bmüşteri\s+taşıma\s+ipliğimiz\b', 'istemci işleme iş parçacığımız (thread)'),
    (r'\biş\s+ipliği\b', 'iş parçacığı (thread)'),
    (r'[Tt]amamlayıcısının\b', 'tümleyeninin'),
    (r'[Tt]amamlayıcısına\b', 'tümleyenine'),
    (r'[Tt]amamlayıcısından\b', 'tümleyeninden'),
    (r'[Tt]amamlayıcısında\b', 'tümleyeninde'),
    (r'[Tt]amamlayıcısını\b', 'tümleyenini'),
    (r'[Tt]amamlayıcısıdır\b', 'tümleyenidir'),
    (r'[Tt]amamlayıcısı\b', 'tümleyeni'),
    (r'[Tt]amamlayıcının\b', 'tümleyenin'),
    (r'[Tt]amamlayıcıların\b', 'tümleyenlerin'),
    (r'[Tt]amamlayıcıları\b', 'tümleyenleri'),
    (r'\bTamamlayıcılar\b', 'Tümleyenler'),
    (r'\btamamlayıcılar\b', 'tümleyenler'),
    (r'\bTamamlayıcı\b', 'Tümleyen'),
    (r'\btamamlayıcı\b', 'tümleyen'),
    (r"\b1's\s*comp(?:lement)?\b", "1'e tümleyen"),
    (r"\b2's\s*comp(?:lement)?\b", "2'ye tümleyen"),
    (r"\b9's\s*comp(?:lement)?\b", "9'a tümleyen"),
    (r"\b10's\s*comp(?:lement)?\b", "10'a tümleyen"),
    (r'\bsigned\s+magnitude\b', 'işaret-büyüklük'),
    (r'\bsigned-magnitude\b', 'işaret-büyüklük'),
    (r'\bPractice\s+Exercise\b', 'Uygulama Alıştırması'),
    (r'\bAnswer\s*:', 'Cevap:'),
    (r'\bEXAMPLE\b', 'ÖRNEK'),
    (r'\bWritability\b', 'Yazılabilirlik'),
    (r'\bReadability\b', 'Okunabilirlik'),
    (r'\bOrthogonality\b', 'Dikgenlik (Ortogonallik)'),
    (r'\bExpressivity\b', 'İfade Gücü'),
    (r'\bAliasing\b', 'Takma Ad Kullanımı (Aliasing)'),
]


class DynamicAcademicRegistry:
    DOMAIN_SIGNATURES = {
        "digital_electronics": {
            "label": "Sayısal Tasarım ve Donanım Mühendisliği (IEEE)",
            "keywords": {
                "vhdl", "verilog", "flip-flop", "karnaugh", "minterm", "maxterm",
                "cmos", "nand", "multiplexer", "implicant", "latch", "boolean"
            },
            "polysemy_locks": [
                (r"\bessential\s+prime\s+implicants\b", "temel asal kapsayanlar (essential prime implicants)"),
                (r"\bprime\s+implicants\b", "asal kapsayanlar (asal bileşenler)"),
                (r"\bprime\s+implicant\b", "asal kapsayan (asal bileşen)"),
                (r"\bdon[\'\u2019`]?t[\-\s]+care\s+conditions?\b", "farketmez (don't-care) durumları"),
                (r"\bdon[\'\u2019`]?t[\-\s]+cares?\b", "farketmez (don't-care) durumları"),
                (r"\bsum[\-\s]+of[\-\s]+products\b", "Çarpımların Toplamı (SOP)"),
                (r"\bproduct[\-\s]+of[\-\s]+sums\b", "Toplamların Çarpımı (POS)"),
                (r"\bproduct\s+terms?\b", "çarpım terimleri"),
                (r"\bsum\s+terms?\b", "toplam terimleri"),
                (r"\bpropagation\s+delay\b", "yayılım gecikmesi"),
                (r"\bclock\s+skew\b", "saat kayması"),
                (r"\btiming\s+diagram\b", "zamanlama diyagramı"),
                (r"\bfan[\-\s]+out\b", "çıkış yükleme kapasitesi (fan-out)"),
                (r"\bfan[\-\s]+in\b", "giriş kapasitesi (fan-in)"),
                (r"\bnoise\s+margin\b", "gürültü payı"),
                (r"\bpower\s+dissipation\b", "güç tüketimi"),
                (r"\bstate\s+table\b", "durum tablosu"),
                (r"\bstate\s+diagram\b", "durum diyagramı"),
                (r"\btruth\s+table\b", "doğruluk tablosu"),
                (r"\bentity\s+declaration\b", "varlık (entity) bildirimi"),
            ]
        },
        "compiler_pl": {
            "label": "Programlama Dilleri ve Derleyici Tasarımı",
            "keywords": {
                "lexeme", "nonterminal", "bnf", "ebnf", "grammars", "sentential",
                "parse", "denotational", "axiomatic", "subprogram"
            },
            "polysemy_locks": [
                (r"\bsentential\s+forms?\b", "cümlesel biçimler (sentential forms)"),
                (r"\bparse\s+trees?\b", "ayrıştırma ağaçları (parse trees)"),
                (r"\bsymbol\s+table\b", "sembol tablosu"),
            ]
        },
        "cybersecurity": {
            "label": "Siber Güvenlik ve Sızma Testi Mühendisliği",
            "keywords": {
                "metasploit", "payload", "exploit", "shellcode", "fuzzer",
                "debugger", "vulnerability", "overflow", "socket"
            },
            "polysemy_locks": [
                (r"\breturn\s+address\b", "dönüş adresi (return address)"),
                (r"\bbuffer\s+overflow\b", "arabellek taşması (buffer overflow)"),
                (r"\bcommand\s+shells?\b", "komut kabukları"),
                (r"\blistening\s+port\b", "dinleme portu"),
            ]
        }
    }

    def __init__(self):
        self.active_domains: List[str] = []
        self.active_label: str = "Bilgisayar ve Donanım Mühendisliği (IEEE)"
        self.active_locks: List[Tuple[re.Pattern, str]] = []

    def profile_document(self, doc: fitz.Document, sample_pages: int = 25) -> None:
        word_counts: Counter = Counter()
        total_p = len(doc)
        step = max(1, total_p // max(1, sample_pages))
        for p_idx in range(0, total_p, step):
            txt = doc[p_idx].get_text("text").lower()
            words = re.findall(r'\b[a-z][a-z\-]{2,}\b', txt)
            word_counts.update(words)

        scored: List[Tuple[int, str]] = []
        for dom_name, dom_data in self.DOMAIN_SIGNATURES.items():
            score = sum(word_counts.get(kw, 0) for kw in dom_data["keywords"])
            if score >= 2:
                scored.append((score, dom_name))

        scored.sort(reverse=True)
        self.active_domains = [d[1] for d in scored[:2]]
        self.active_locks.clear()

        if self.active_domains:
            primary = self.active_domains[0]
            self.active_label = self.DOMAIN_SIGNATURES[primary]["label"]

        for dom in self.active_domains:
            for pat_str, repl_str in self.DOMAIN_SIGNATURES[dom]["polysemy_locks"]:
                self.active_locks.append((re.compile(pat_str, re.I), repl_str))

        print(f"[ALAN PROFILI] Algilanan Kitap Disiplini: {self.active_label} ({len(self.active_locks)} ozel alan kilidi aktif)")

    def apply_pre_normalization(self, text: str) -> str:
        res = text
        for pat, repl in self.active_locks:
            res = pat.sub(repl, res)
        for pat_s, repl_s in ENGLISH_PRE_NORMALIZATION:
            res = re.sub(pat_s, repl_s, res, flags=re.I)
        return res

    @staticmethod
    def apply_post_fixes(text: str) -> str:
        res = text
        for pat_s, repl_s in POST_TRANSLATION_FIXES:
            res = re.sub(pat_s, repl_s, res)
        return res
'''

# ============================================================================
# 6. TRANSLATORS/CACHE_MANAGER.PY -> ESKİ GAFLARI VE ﴾ ﴿ KAYITLARINI ONARAN ÖNBELLEK
# ============================================================================
FILES["translators/cache_manager.py"] = r'''import os
import re
import json
from typing import Dict, Optional
from core.unicode_sanitizer import DeterministicArtifactPurger
from translators.domain_registry import DynamicAcademicRegistry

CACHE_VERSION = "v19.0_ieee_hdl_forensic_lock"


class SelfHealingCache:
    """
    1) Çözülmemiş maskeleri (CODE_0, MTH_0) içeren bozuk kayıtları siler.
    2) Önceki çevirilerden kalan ﴾ ﴿ (\ufd3e, \ufd3f) parantezlerini ve
       'bakım koşulları', 'asal implantlar', 'ürünlerin toplamı', 'liman' gibi
       terminoloji gaflarını yükleme anında otomatik onarır.
    """
    CONTAMINATION_RE = re.compile(r'(?:CODE_\d+|MTH_\d+)')

    def __init__(self, cache_path: str = "build/translation_cache.json"):
        self.cache_path = cache_path
        self.data: Dict[str, str] = {"__version__": CACHE_VERSION}
        self._load_and_heal()

    def _load_and_heal(self) -> None:
        if not os.path.exists(self.cache_path):
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                return

            clean_cache: Dict[str, str] = {"__version__": CACHE_VERSION}
            purged = 0
            repaired_count = 0

            for k, v in loaded.items():
                if k == "__version__" or not isinstance(v, str):
                    continue
                if self.CONTAMINATION_RE.search(v):
                    purged += 1
                    continue

                healed_v = DynamicAcademicRegistry.apply_post_fixes(v)
                healed_v = DeterministicArtifactPurger.sanitize_stream(healed_v)
                if healed_v != v:
                    repaired_count += 1
                clean_cache[k] = healed_v

            self.data = clean_cache
            print(
                f"[ONBELLEK v19.0] {len(self.data) - 1} ceviri hazir "
                f"({repaired_count} kayitta IEEE terim/parantez onarimi yapildi, {purged} kirli maske silindi)."
            )
            if purged > 0 or repaired_count > 0:
                self.save()
        except Exception as exc:
            print(f"[ONBELLEK UYARISI] Onbellek sifirlandi: {exc}")

    def get(self, key: str) -> Optional[str]:
        val = self.data.get(key)
        if val is not None:
            return DeterministicArtifactPurger.sanitize_stream(
                DynamicAcademicRegistry.apply_post_fixes(val)
            )
        return None

    def put(self, key: str, value: str) -> None:
        clean_val = DeterministicArtifactPurger.sanitize_stream(
            DynamicAcademicRegistry.apply_post_fixes(value)
        )
        if not self.CONTAMINATION_RE.search(clean_val):
            self.data[key] = clean_val

    def save(self) -> bool:
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
'''

# ============================================================================
# 7. TRANSLATORS/LMSTUDIO_BACKEND.PY -> IEEE DONANIM SİSTEM KOMUTU ENTEGRASYONU
# ============================================================================
FILES["translators/lmstudio_backend.py"] = r'''import json
import urllib.request
from typing import Optional


class LMStudioBackend:
    def __init__(self, base_url: str = "http://localhost:1234/v1", domain_label: str = "Bilgisayar ve Donanım Mühendisliği"):
        self.base_url = base_url.rstrip("/")
        self.domain_label = domain_label
        self.model_id: Optional[str] = None
        self.available: bool = self._check_server()

    def _check_server(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/models", method="GET")
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("data", [])
                if models:
                    self.model_id = models[0].get("id", "local-model")
                    print(f"[LM STUDIO AKTIF] Yerel LLM Sunucusu Algilandi! Aktif Model: {self.model_id}")
                    return True
        except Exception:
            _ = None
        return False

    def set_domain(self, domain_label: str) -> None:
        self.domain_label = domain_label

    def translate_masked_text(self, masked_text: str) -> Optional[str]:
        if not self.available:
            return None

        system_prompt = (
            f"Sen kıdemli bir {self.domain_label} profesörü, IEEE Fellow ve teknik kitap çevirmenisin. "
            "Verilen İngilizce metni %100 matematiksel ve mühendislik sadakatiyle akademik Türkçeye çevir.\n"
            "KESİN KURALLAR:\n"
            "1) ⟦CODE_0⟧, ⟦CODE_1⟧, ⟦MTH_0⟧ gibi maskeleri ASLA silme, değiştirme veya çevirme.\n"
            "2) VHDL, Verilog, C, Python kodlarını ve clk, rst_n, std_logic gibi sinyal adlarını olduğu gibi koru.\n"
            "3) ZORUNLU IEEE TERİMLERİ: 'Don't-care conditions' -> 'Farketmez durumlar' (ASLA bakım koşulu yazma), "
            "'Prime implicants' -> 'Asal kapsayanlar / Asal bileşenler' (ASLA asal implant yazma), "
            "'Sum of Products' -> 'Çarpımların Toplamı', 'Product of Sums' -> 'Toplamların Çarpımı', "
            "'Port' -> 'Port / Giriş-Çıkış Ucu' (ASLA liman yazma), 'Latch' -> 'Mandal Devresi / Latch', "
            "'Figure X' -> 'Şekil X'.\n"
            "4) ASLA ﴾ veya ﴿ gibi süslü parantezler üretme; standart () kullan. Sadece çeviriyi döndür."
        )
        payload = {
            "model": self.model_id or "local-model",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": masked_text}
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
            "stream": False
        }
        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=45.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"].strip()
                if content:
                    return content
        except Exception as exc:
            print(f"[LM STUDIO UYARISI] Yerel LLM yanit vermedi ({exc}), Opus-MT yedegine geciliyor...")
            self.available = False
        return None
'''

# ============================================================================
# 8. RENDERERS/FORENSIC_AUDITOR.PY -> ÇEVİRİ SONRASI ADLİ DENETİM VE PARANTEZ KİLİDİ
# ============================================================================
FILES["renderers/forensic_auditor.py"] = r'''import re
from typing import List, Tuple, Dict
import pymupdf as fitz

from core.models import ParagraphBlock
from core.unicode_sanitizer import DeterministicArtifactPurger
from translators.domain_registry import DynamicAcademicRegistry


class PageForensicAuditor:
    """
    PDF kaydedilmeden hemen önce metin kaybı (omission), çözülmemiş maske kalıntısı,
    donanım terminolojisi gafları, ﴾ ﴿ (\ufd3e, \ufd3f) parantezleri ve 2B kutu
    çakışmalarını (overlap) denetleyip otomatik onaran adli kalite katmanı.
    """
    NUMBER_INVARIANT_RE = re.compile(r'\b(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?)\b')

    @classmethod
    def audit_and_repair_translation(
        cls, orig_text: str, trans_text: str, masks: Dict[str, str]
    ) -> str:
        repaired = DynamicAcademicRegistry.apply_post_fixes(trans_text)
        repaired = DeterministicArtifactPurger.sanitize_stream(repaired)

        for key, val in masks.items():
            m_type = "CODE" if "CODE" in key else "MTH"
            num = re.sub(r'\D', '', key)
            repaired = re.sub(rf'\b{m_type}[_\-\s]?{num}\b', lambda _, v=val: v, repaired, flags=re.I)

        if len(repaired) < len(orig_text) * 0.28 and len(orig_text) > 35:
            return DeterministicArtifactPurger.sanitize_stream(orig_text)

        for _, val in masks.items():
            clean_val = val.strip()
            if len(clean_val) >= 2 and clean_val not in repaired:
                repaired = f"{repaired} ({clean_val})"

        repaired = DynamicAcademicRegistry.apply_post_fixes(repaired)
        return DeterministicArtifactPurger.sanitize_stream(repaired)

    @staticmethod
    def enforce_zero_overlap_geometry(
        render_queue: List[Tuple[ParagraphBlock, fitz.Rect, str, Tuple[float, float, float], Tuple[float, float, float]]],
        protected_rects: List[fitz.Rect]
    ) -> None:
        n = len(render_queue)
        for i in range(n):
            _, rect_i, _, _, _ = render_queue[i]
            for prot_r in protected_rects:
                if rect_i.intersects(prot_r):
                    inter = rect_i & prot_r
                    if inter.width > 4.0 and inter.height > 1.5:
                        if prot_r.y0 >= rect_i.y0 and (prot_r.y0 - rect_i.y0) > 6.0:
                            rect_i.y1 = min(rect_i.y1, prot_r.y0 - 0.8)

            for j in range(i + 1, n):
                _, rect_j, _, _, _ = render_queue[j]
                if rect_i.intersects(rect_j):
                    inter = rect_i & rect_j
                    if inter.width > 6.0 and inter.height > 1.0:
                        if rect_i.y0 <= rect_j.y0 and (rect_j.y0 - rect_i.y0) > 6.0:
                            rect_i.y1 = min(rect_i.y1, rect_j.y0 - 0.5)
'''


def main():
    for folder in ["core", "extractors", "translators", "renderers", "build"]:
        os.makedirs(folder, exist_ok=True)

    for rel_path, content in FILES.items():
        with open(rel_path, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))
        if rel_path.endswith(".py"):
            py_compile.compile(rel_path, doraise=True)
        print(f"  [GÜNCELLENDİ VE DOĞRULANDI] {rel_path}")

    # Mevcut önbelleği (translation_cache.json) v19.0 kurallarıyla anında onar
    from translators.cache_manager import SelfHealingCache
    _ = SelfHealingCache("build/translation_cache.json")

    print("\n====================================================================")
    print("[ADIM 4 GÜNCELLEMESİ TAMAMLANDI - v19.0 IEEE & HDL FORENSIC LOCK]")
    print("  1. VHDL / Verilog Deklarasyon ve Sinyal Karantinası : AKTİF")
    print("  2. IEEE Donanım Terminolojisi (SOP/POS/Port/Latch)  : AKTİF")
    print("  3. ﴾ ﴿ (\\ufd3e, \\ufd3f) Süslü Parantez Sıfırlayıcı : AKTİF")
    print("  4. Sayfa 6-15 İçindekiler (TOC) Y-Band Hiza Kilidi  : AKTİF")
    print("====================================================================")


if __name__ == "__main__":
    main()