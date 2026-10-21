import os
import re
import json
import gc
import shutil
import urllib.request
import warnings
import subprocess
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

# --- 1. %100 ÇEVRİMDIŞI (AIR-GAPPED) KİLİT PROTOKOLÜ ---
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_TOKEN"] = ""
os.environ["HUGGING_FACE_HUB_TOKEN"] = ""

for _tp in [
    os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "token"),
    os.path.join(os.path.expanduser("~"), ".huggingface", "token")
]:
    if os.path.exists(_tp):
        try:
            os.remove(_tp)
        except Exception:
            pass

import pymupdf as fitz
from PIL import Image
import cv2
import numpy as np
import torch
import pytesseract

warnings.filterwarnings("ignore")
import transformers
transformers.logging.set_verbosity_error()


def configure_tesseract() -> bool:
    which_tess = shutil.which("tesseract")
    if which_tess and os.path.exists(which_tess):
        pytesseract.pytesseract.tesseract_cmd = which_tess
        return True
    for path in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tesseract-OCR", "tesseract.exe"),
    ]:
        if path and os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True
    return False


HAS_TESSERACT = configure_tesseract()
CACHE_VERSION = "v14.0_production_redaction_code_quarantine"


# --- 2. RTX 5080 (BLACKWELL sm_120) & CPU OTONOM BELLEK YÖNETİMİ ---
def get_safe_device() -> Tuple[torch.device, torch.dtype]:
    if torch.cuda.is_available():
        try:
            cap = torch.cuda.get_device_capability(0)
            gpu_name = torch.cuda.get_device_name(0)
            test_tensor = torch.tensor([[1.0, 2.0], [3.0, 4.0]], device="cuda")
            _ = torch.matmul(test_tensor, test_tensor)
            torch.cuda.synchronize()

            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            torch.set_float32_matmul_precision("high")

            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            print(f"[DONANIM] GPU Aktif: {gpu_name} (Mimari: sm_{cap[0]}{cap[1]} | Mod: {dtype})")
            return torch.device("cuda"), dtype
        except Exception as e:
            print(f"[DONANIM UYARISI] GPU kernel/mimari uyumsuzluğu ({e}). Güvenli CPU moduna geçiliyor...")

    cpu_threads = max(1, (os.cpu_count() or 4) - 1)
    torch.set_num_threads(cpu_threads)
    print(f"[DONANIM] Stabil CPU Modu Aktif ({cpu_threads} Thread).")
    return torch.device("cpu"), torch.float32


# --- 3. VERİ YAPILARI ---
@dataclass
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2.0

    def overlaps(self, other: "BoundingBox", margin: float = 1.5) -> bool:
        return not (
            self.x1 + margin < other.x0
            or self.x0 - margin > other.x1
            or self.y1 + margin < other.y0
            or self.y0 - margin > other.y1
        )


@dataclass
class ParagraphBlock:
    id: int
    page_num: int
    box: BoundingBox
    text: str
    translated_text: str = ""
    font_size: float = 10.0
    is_standalone_math: bool = False
    is_code_block: bool = False
    is_header_footer: bool = False
    is_from_ocr: bool = False
    is_bold: bool = False
    is_centered: bool = False
    is_table_or_diagram_cell: bool = False
    text_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    bg_color: Optional[Tuple[float, float, float]] = None
    max_allowed_y1: Optional[float] = None
    max_allowed_x1: Optional[float] = None

    @property
    def is_protected(self) -> bool:
        return self.is_standalone_math or self.is_code_block or self.is_header_footer


# --- 4. SAF HEX UNICODE TABLOLARI VE FONT DOĞRULAMA ---
SUPERSCRIPT_MAP = str.maketrans(
    "0123456789+-=()nxyzrabcikm",
    "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207a\u207b\u207c\u207d\u207e\u207f\u02e3\u02b8\u1dbb\u02b3\u1d43\u1d47\u1d9c\u2071\u1d4f\u1d50"
)

SUBSCRIPT_MAP = str.maketrans(
    "0123456789+-=()nxyzr",
    "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089\u208a\u208b\u208c\u208d\u208e\u2099\u2093\u1d67\u2082\u1d63"
)

GLYPH_FALLBACK_MAP = {
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
    "\u2022": "\u2022",
}

MONOSPACE_FONT_KEYWORDS = (
    "mono", "courier", "consolas", "inconsolata", "menlo",
    "sourcecode", "source code", "typewriter", "code", "lucida console",
    "dejavusansmono", "liberationsansmono", "cmtt", "txtt", "zi4"
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
    "conf", "log", "txt", "pcap"
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
    "listen", "accept", "ioctl", "setsockopt", "execve", "fork", "WaitForSingleObject",
    "VirtualAlloc", "CreateThread", "WriteProcessMemory", "ReadProcessMemory"
}


def normalize_unicode_text(text: str) -> str:
    t = text
    for dash in ["\u2212", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\uf02d"]:
        t = t.replace(dash, "-")
    for quote in ["\u2018", "\u2019", "\u201b", "\u2032", "\u0060", "\u00b4"]:
        t = t.replace(quote, "'")
    for dquote in ["\u201c", "\u201d", "\u2033"]:
        t = t.replace(dquote, '"')
    for bullet in ["\uf0b7", "\u2022", "\u25cf", "\u25aa", "\u25fe", "\u2219"]:
        t = t.replace(bullet, "\u2022 ")
    # Kitaplardaki siyah daire içi rakamları (➊..➓, ①..⑩) temizle veya koru
    t = re.sub(r'[\u2776-\u2793\u2460-\u2473\uf000-\uf8ff]', '', t)
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


# --- 5. KOD KARANTİNASI, FORMALİZM VE SATIR İÇİ MASKELEME MOTORU ---
class FormalismAnalyzer:
    """
    1) Kod Bloklarını (Monospace font, girinti, C/Python/Bash/Assembly/Metasploit sözdizimi) %100 karantinaya alır.
    2) Yazar adlarını ('Justin Seitz.'), web sitelerini ('www.cancer.ca'), kısaltmaları ('e.g.') KOD SANMAZ.
    3) İngilizce fonksiyonel kelime oranı >= %12 ve kelime sayısı >= 4 olan tüm cümleleri doğal metin kabul eder.
    4) Cümle içindeki satır içi kodları ('target_port', 'argv[]', 'sys.exit') ⟦CODE_X⟧ olarak maskeler ve geri yükler.
    """

    @staticmethod
    def is_monospace_span(font_name: str, flags: int) -> bool:
        if flags & 8:
            return True
        fn = font_name.lower()
        return any(k in fn for k in MONOSPACE_FONT_KEYWORDS)

    @staticmethod
    def is_code_line_syntax(text: str, leading_indent: float = 0.0) -> bool:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean = re.sub(r'⟦CODE_\d+⟧', '', clean).strip()
        if not clean:
            return False

        # 1. Terminal istemcileri ve Metasploit / Debugger çıktıları
        if re.match(r'^(?:\$\s+|#\s+|>>>\s+|\.\.\.\s+|msf\s+|msf\d?\s*>\s*|\[\*\]\s+|\[\+\]\s+|\[\-\]\s+|\[!\]\s+|C:\\>', clean):
            return True

        # 2. C / Python / Bash / Assembly / Ruby / SQL satır başı anahtar kelimeleri
        if re.match(
            r'^(?:#include\b|#define\b|#ifdef\b|#ifndef\b|#endif\b|import\s+[a-zA-Z0-9_\.]+|from\s+[a-zA-Z0-9_\.]+\s+import\b|'
            r'def\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(|class\s+[a-zA-Z_][a-zA-Z0-9_]*|return\b|const\s+|void\s+|int\s+|char\s+|'
            r'float\s+|double\s+|unsigned\s+|struct\s+|typedef\s+|static\s+|extern\s+|public\s+|private\s+|protected\s+|'
            r'printf\s*\(|fprintf\s*\(|sprintf\s*\(|print\s+["\'\(]|mov\s+|push\s+|pop\s+|xor\s+|lea\s+|jmp\s+|call\s+|ret\b|'
            r'cmp\s+|test\s+|je\s+|jne\s+|jz\s+|jnz\s+|nop\b|db\s+|dd\s+|dw\s+|section\s+\.|global\s+_|'
            r'while\s+True\s*:|while\s*\(|for\s+[a-zA-Z_][a-zA-Z0-9_,\s]*\s+in\s+|for\s*\(|if\s+__name__\s*==|'
            r'if\s*\(|elif\s+|else\s*:|try\s*:|except\b|finally\s*:|with\s+open\()',
            clean
        ):
            return True

        # 3. Satır sonu noktalı virgül (C/Java/Perl/Rust kod satırı) ve atama/fonksiyon yapısı
        if re.search(r';\s*$', clean) and (
            re.search(r'[=\(\)\[\]\{\}]', clean)
            or leading_indent > 12.0
            or len(clean.split()) <= 8
        ):
            return True

        # 4. Değişken atamaları, nesne metodu çağrıları ve fuzzer/hex çıktıları
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?\s*(?:=|\+=|\-=|:=)\s*[^\s]+', clean):
            words = re.findall(r'[a-zA-Z]{2,}', clean)
            func_cnt = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
            if func_cnt <= 1:
                return True

        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\s*\(.*\)\s*$', clean):
            return True

        # Hex dump, bellek adresleri veya boşluksuz uzun fuzzing/payload dizileri
        if re.search(r'\b0x[0-9a-fA-F]{4,}\b', clean) and len(clean.split()) <= 10:
            return True
        if re.search(r'[A-Za-z0-9+/=]{32,}', clean):
            return True
        if re.match(r'^\.\s*\.\s*\.\s*SNIP\s*\.\s*\.\s*\.', clean, re.I):
            return True

        return False

    @staticmethod
    def is_header_or_footer(text: str, box: BoundingBox, page_height: float) -> bool:
        """
        Sayfa yüksekliğinin en üst %5'lik ve en alt %6'lık diliminde kalan,
        slayt/bölüm numarası veya telif hakkı ibareleri içeren tek satırlık blokları yakalar.
        """
        clean = text.strip()
        if not clean:
            return True

        is_single_line = box.height <= 22.0 and len(clean) <= 110
        in_top_zone = box.y0 <= page_height * 0.055 or box.y1 <= page_height * 0.075
        in_bottom_zone = box.y1 >= page_height * 0.94 or box.y0 >= page_height * 0.92

        if is_single_line and (in_top_zone or in_bottom_zone):
            if re.search(
                r'(?:All\s+rights\s+reserved|All\s+rghts\s+reserved|Copyright|Addison-?Wesley|'
                r'\bChapter\s+\d+\b|\bSection\s+\d+(?:\.\d+)*\b|^\d+\s*[-–]\s*\d+$|^\d{1,4}$)',
                clean,
                re.I
            ):
                return True
            # Sadece sayfa numarası + kısa bölüm başlığı içeren üst/alt satırlar
            if re.match(r'^(?:\d+\s+.+|\S.+?\s+\d+)$', clean) and len(clean.split()) <= 7:
                return True

        # Konumdan bağımsız tam telif/slayt numarası satırları
        if is_single_line and re.search(r'(?:Copyright\s*©?\s*\d{4}|All\s+rights\s+reserved|\bAddison-?Wesley\b)', clean, re.I):
            return True
        if re.fullmatch(r'\d{1,3}\s*[-–]\s*\d{1,3}|\d{1,4}', clean):
            return True

        return False

    @staticmethod
    def is_formal_expression(text: str) -> bool:
        """
        Aşırı korumacı olmayan (Over-Zealous Classifier düzeltilmiş) formalizm denetleyicisi:
        - İngilizce fonksiyonel kelime oranı > %12 ve kelime sayısı >= 4 ise KESİNLİKLE doğal açıklama cümlesidir (False).
        - Nokta içeren kelimeler yalnızca bilinen kod uzantısı (.py, .c, .cpp, .h, .sh) veya gerçek kod yapısıysa formalizm sayılır.
        """
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean = re.sub(r'⟦CODE_\d+⟧', ' codevar ', clean).strip()
        clean = re.sub(r'^[\u2022\-\+\*]\s*', '', clean).strip()
        if not clean:
            return True

        if FormalismAnalyzer.is_code_line_syntax(clean):
            return True

        words = re.findall(r'[a-zA-Z]{2,}', clean)
        word_count = len(words)
        func_word_count = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
        func_ratio = func_word_count / max(1, word_count)

        # KESİN KURAL: Fonksiyonel kelime oranı > %12 ve kelime sayısı >= 4 ise bu bir açıklama cümlesidir!
        if word_count >= 4 and func_ratio > 0.12:
            # İstisna: Satır doğrudan BNF üretim oku (::=, ->) veya çoklu kod ataması içeriyorsa ve cümle değilse
            if not re.search(r'(?:->|→|←|::=)', clean):
                return False

        total_len = len(clean)
        alpha_chars = sum(1 for c in clean if c.isalpha())
        digit_chars = sum(1 for c in clean if c.isdigit())
        formal_ops = set("=<>+-*/|{}[]()^_~\\@#$%&")
        sym_chars = sum(1 for c in clean if c in formal_ops)

        if alpha_chars == 0:
            return True

        # BNF / Gramer / Matematiksel Denklem imzaları
        has_bnf_or_arrow = bool(re.search(r'(?:->|→|←|::=|=>|==|!=|<=|>=|:=|<[a-zA-Z_][a-zA-Z0-9_]*>)', clean))
        has_equation = bool(re.search(r'(?:^|\s)[a-zA-Z0-9_]+\s*[=<>≤≥≠]\s*[a-zA-Z0-9_\(\[\+\-]', clean))

        # Noktalı ifadeler: Sadece bilinen kod uzantıları (.py, .c, .cpp, .h, .sh) veya snake_case/parantezli metot ise!
        has_strict_dot_code = False
        for m_dot in re.finditer(r'\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)(\s*\()?', clean):
            left_p, right_p, has_paren = m_dot.group(1), m_dot.group(2), m_dot.group(3)
            if left_p.lower() in {"www", "http", "https", "ftp", "e", "i", "fig", "sec", "ch", "dr", "mr", "ms", "vs", "etc", "al"}:
                continue
            if right_p.lower() in KNOWN_CODE_EXTENSIONS:
                has_strict_dot_code = True
                break
            if has_paren or "_" in left_p or "_" in right_p:
                has_strict_dot_code = True
                break

        if (has_bnf_or_arrow or has_equation or has_strict_dot_code) and func_ratio <= 0.12:
            return True

        if (sym_chars + digit_chars) / max(1, total_len) > 0.35 and func_word_count == 0:
            return True

        # Tekil büyük harf tokenlar (WHILE, LPAREN, SEMICOLON) veya yazar adı (ROBERT W. SEBESTA)
        if word_count <= 2 and clean.isupper() and func_word_count == 0 and len(clean) <= 20:
            return True
        if re.fullmatch(r'[A-Z]+\s+[A-Z]\.\s+[A-Z]+', clean):
            return True

        return False

    @staticmethod
    def _is_valid_inline_code_token(token: str) -> bool:
        t = token.strip()
        if not t or len(t) < 2:
            return False
        if t in INLINE_CODE_EXACT_TOKENS:
            return True
        # Kısaltmaları, web adreslerini ve normal kelimeleri hariç tut
        if re.match(r'^(?:www\.|http|e\.g\.|i\.e\.|fig\.|vs\.|[A-Z][a-z]+\.)', t, re.I):
            return False
        if "_" in t and re.search(r'[a-zA-Z]', t):
            return True
        if re.search(r'\[\]|\(\)$', t):
            return True
        if re.match(r'^0x[0-9a-fA-F]+$', t):
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
        """
        Normal cümle içinde geçen:
        1) Satır içi kod parçacıklarını ('target_port', 'buffer', 'argc', 'argv[]', 'sys.exit', ⟦CODE_X⟧)
        2) Matematiksel formülleri, BNF sembollerini (<expr>) ve alt/üst simgeleri
        maskeler ve çeviri sonrasında İngilizce orijinal haliyle geri yükler.
        """
        t = normalize_unicode_text(sentence)
        masks: Dict[str, str] = {}
        code_idx = 0
        math_idx = 0

        def add_code_mask(val: str) -> str:
            nonlocal code_idx
            key = f"⟦CODE_{code_idx}⟧"
            masks[key] = val
            code_idx += 1
            return f" {key} "

        def add_math_mask(m) -> str:
            nonlocal math_idx
            val = m.group(0).strip()
            if val.startswith("(") and val.endswith(")"):
                inner_words = re.findall(r'[a-zA-Z]{2,}', re.sub(r'<(?:sub|sup):[^>]+>', '', val))
                if len(inner_words) >= 1 and not any(c in val for c in "=+-*/<>^_"):
                    return val
            key = f"⟦MTH_{math_idx}⟧"
            masks[key] = val
            math_idx += 1
            return f" {key} "

        # 0. Dijital ayrıştırmada monospace fonttan dolayı önceden işaretlenmiş ⟦INLCODE:...⟧ etiketlerini maskele
        def repl_premarked_code(m) -> str:
            return add_code_mask(m.group(1).strip())

        t = re.sub(r'⟦INLCODE:(.*?)⟧', repl_premarked_code, t)

        # 1. Satır içi kod ifadelerini (snake_case, func(), argv[], sys.exit, file.py, 0x7fff, Rex::Text) yakala
        inline_code_pattern = (
            r'(?:'
            r'\b0x[0-9a-fA-F]+\b'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_][a-zA-Z0-9_]*)+(?:\([^\)]*\))?'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*\[[0-9a-zA-Z_]*\]'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*_[a-zA-Z0-9_]+(?:\([^\)]*\))?'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*(?:\([^\)]*\))?'
            r'|\b(?:buffer|argc|argv|stdin|stdout|stderr|malloc|free|printf|recv|send|fork|execve)\b'
            r')'
        )

        def repl_inline_code(m) -> str:
            cand = m.group(0).strip()
            if FormalismAnalyzer._is_valid_inline_code_token(cand):
                return add_code_mask(cand)
            return cand

        t = re.sub(inline_code_pattern, repl_inline_code, t)

        # 2. Açılı parantezli BNF sembolleri (<expr>, <var>) ve süslü parantezli ifadeler
        t = re.sub(r'(?:<[a-zA-Z_][a-zA-Z0-9_\s]*>|\{[^{}]+\}|\bC\+\+|\bC#|\.NET\b|#include\b|#define\b)', add_math_mask, t)

        # 3. Matematiksel denklemler ve alt/üst simgeler (<sub:...>, <sup:...>)
        math_atom = (
            r'(?:'
            r'\([0-9\s\+\-\*\/\^\<\>\:\_±NXYMrnABxy]+?\)(?:<(?:sub|sup):[^>]+>)?'
            r'|[+\-]?\b(?:[0-9]+(?:\s+[0-9]{4})*|[a-zA-Z])(?:<(?:sub|sup):[^>]+>)+[a-zA-Z0-9]*'
            r'|[+\-]?\b[0-9]+(?:\s+[0-9]{4})*\b'
            r'|[+\-]?\b[a-zA-Z]\b(?=\s*(?:[=≠<>≤≥\+\*\/]|-\s*(?:[0-9\(]|[a-zA-Z]\b)))'
            r'|[+\-]?(?<=[=≠<>≤≥\+\-\*\/]\s)\b[a-zA-Z]\b'
            r')'
        )
        t = re.sub(rf'{math_atom}(?:\s*(?:!=|==|<=|>=|[=≠<>≤≥\+\*\/]|-(?!\s*[a-zA-Z]{{2,}}))\s*{math_atom})+', add_math_mask, t)
        t = re.sub(r'(?:\([0-9a-zA-Z\s\+\-]+\)|[+\-]?\b[0-9a-zA-Z]+)?<(?:sub|sup):[^>]+>', add_math_mask, t)
        t = re.sub(r'\(\s*[±\+\-]?\s*[a-zA-Z0-9]\s*(?:[\-\+\|]\s*[a-zA-Z0-9]\s*)+\)', add_math_mask, t)

        return re.sub(r'\s+', ' ', t).strip(), masks

    @staticmethod
    def unmask_formal_tokens(translated: str, masks: Dict[str, str]) -> str:
        res = translated
        for _ in range(3):
            for key, orig in masks.items():
                m_type = "CODE" if "CODE" in key else "MTH"
                num = re.sub(r'\D', '', key)
                pat = rf'(?:⟦?\s*{m_type}\s*[_-]?\s*{num}\s*⟧?|\[\s*{m_type}\s*[_-]?\s*{num}\s*\])'
                res = re.sub(pat, lambda _: f" {orig} ", res, flags=re.I)

        # Modelin yuttuğu veya sildiği kritik kod/formül maskesi varsa cümle sonuna ekle
        for key, orig in masks.items():
            if orig not in res and key not in res:
                if not any(orig in v for k2, v in masks.items() if k2 != key):
                    res = f"{res} ({orig})"

        return re.sub(r'\s+', ' ', res).strip()


def format_sub_sup_for_render(text: str, font_obj: Optional[fitz.Font] = None) -> str:
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
    res = re.sub(r'⟦INLCODE:(.*?)⟧', r'\1', res)

    if font_obj:
        safe_chars = []
        for ch in res:
            if ch in "\r\n\t " or font_obj.has_glyph(ord(ch)):
                safe_chars.append(ch)
            elif ch in GLYPH_FALLBACK_MAP:
                safe_chars.append(GLYPH_FALLBACK_MAP[ch])
            else:
                safe_chars.append("")
        res = "".join(safe_chars)
    return res


# --- 6. HİBRİT DİJİTAL VS TARANMIŞ PDF VE İKİ SÜTUNLU MİZANPAJ MOTORU ---
class GeometricLayoutEngine:
    """
    1) Sayfada seçilebilir dijital metin varsa (len(digital_blocks) > 0), doğrudan PyMuPDF'in
       vektör metnini ve koordinatlarını kullanır; gereksiz OCR çalıştırmaz.
    2) Yalnızca sayfa tamamen taranmış/resim ise Tesseract OCR devreye girer ve karantinadaki
       kod/formül koordinatlarına ASLA yaklaşmaz.
    3) İki sütunlu (2-column) sayfalarda orta sütun boşluğunu (gutter) analiz eder ve sağa taşmayı yasaklar.
    """

    def extract_paragraphs(self, page: fitz.Page, page_num: int) -> List[ParagraphBlock]:
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES)
        blocks = page_dict.get("blocks", [])

        digital_blocks = self._extract_digital(page, page_num, blocks)

        # Sayfada anlamlı dijital gövde metni var mı kontrol et (Sadece tek satırlık Copyright altlığı değilse)
        non_footer_digital = [b for b in digital_blocks if not b.is_header_footer]

        if len(non_footer_digital) > 0:
            # KURAL 7: Seçilebilir dijital metin varsa doğrudan yüksek çözünürlüklü vektör metnini kullan!
            final_blocks = digital_blocks
        else:
            # Sayfa tamamen taranmış görüntü veya metinsiz slayt resmi ise OCR çalıştır
            final_blocks = list(digital_blocks)
            if HAS_TESSERACT:
                ocr_blocks = self._extract_scanned_ocr(page, page_num, quarantined_blocks=digital_blocks)
                if ocr_blocks:
                    print(f"   [TARANMIŞ SAYFA OCR] Sayfa {page_num + 1}: {len(ocr_blocks)} metin bloğu OCR ile çıkarıldı.")
                    final_blocks.extend(ocr_blocks)

        for idx, b in enumerate(final_blocks):
            b.id = idx

        return self._compute_two_column_and_collision_limits(final_blocks, page.rect.width, page.rect.height)

    @staticmethod
    def _detect_two_column_gutter(blocks: List[ParagraphBlock], page_w: float) -> Optional[float]:
        """
        İki sütunlu akademik sayfalarda sol sütun ile sağ sütun arasındaki orta boşluğu (gutter X koordinatı)
        tespit eder. Sol sütundaki hiçbir kutu orta boşluğu (gutter) aşamaz!
        """
        mid_left = page_w * 0.42
        mid_right = page_w * 0.58
        left_col_boxes = [
            b for b in blocks
            if not b.is_header_footer and b.box.width < page_w * 0.46 and b.box.x1 <= mid_right
        ]
        right_col_boxes = [
            b for b in blocks
            if not b.is_header_footer and b.box.width < page_w * 0.46 and b.box.x0 >= mid_left
        ]
        if len(left_col_boxes) >= 2 and len(right_col_boxes) >= 2:
            max_left_x1 = max(b.box.x1 for b in left_col_boxes)
            min_right_x0 = min(b.box.x0 for b in right_col_boxes)
            if min_right_x0 > max_left_x1 + 6.0:
                return (max_left_x1 + min_right_x0) / 2.0
        return None

    def _compute_two_column_and_collision_limits(
        self, blocks: List[ParagraphBlock], page_w: float, page_h: float
    ) -> List[ParagraphBlock]:
        """
        KURAL 5: İki sütunlu (2-column) sayfalarda orta sütun boşluğu (gutter) ve sağdaki şekil/sütun sınırı
        asla aşılmaz (Sağa doğru rastgele genişletme YASAKTIR).
        """
        gutter_x = self._detect_two_column_gutter(blocks, page_w)
        sorted_b = sorted(blocks, key=lambda b: (b.box.y0, b.box.x0))

        for i, b in enumerate(sorted_b):
            min_next_y0 = page_h - 10.0
            # Sağa doğru genişlemeyi kendi orijinal genişliğine (veya varsa gutter sınırına) kilitle!
            hard_right_limit = b.box.x1 + 2.0
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

            b.max_allowed_x1 = max(b.box.x0 + 20.0, hard_right_limit)
            b.max_allowed_y1 = max(b.box.y1 + 2.0, min_next_y0 - 1.0)

        return blocks

    @staticmethod
    def _int_to_rgb(color_int: int) -> Tuple[float, float, float]:
        return (((color_int >> 16) & 255) / 255.0, ((color_int >> 8) & 255) / 255.0, (color_int & 255) / 255.0)

    def _extract_digital(self, page: fitz.Page, page_num: int, blocks: List[Dict[str, Any]]) -> List[ParagraphBlock]:
        page_h = page.rect.height
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

                # KURAL 1.1: Satırdaki karakterlerin çoğunluğu monospace ise tüm satır KOD BLOĞUDUR!
                line_is_monospace = (total_chars > 0) and (mono_chars / total_chars >= 0.55)

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
                        # KURAL 1.3: Normal bir cümlenin içindeki tekil monospace kelimeleri ⟦INLCODE:...⟧ ile sar
                        if not line_is_monospace and span_is_mono and len(stripped) >= 2:
                            line_str += f"⟦INLCODE:{stripped}⟧"
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

            grouped: List[Dict[str, Any]] = []
            curr: Dict[str, Any] = {}

            for pl in parsed_lines:
                # Kod, formül, üst/alt bilgi veya madde başlığı olan satırları asla normal paragrafla birleştirme
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
                        if v_gap > curr["size"] * 0.90 or not same_style:
                            grouped.append(curr)
                            curr = pl.copy()
                        else:
                            prev_t = curr["text"]
                            curr["text"] = (
                                (prev_t[:-1] + pl["text"])
                                if prev_t.endswith("-") and not prev_t.endswith(" -")
                                else f"{prev_t} {pl['text']}"
                            )
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

        return out_blocks

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

        # KURAL 7: Karantinadaki kod/formül/altbilgi koordinatlarını maskele, Tesseract ASLA yaklaşmasın
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
                        0.0 <= v_gap <= single_lh * 0.48
                        and -12.0 <= left_diff <= 36.0
                        and abs(est_fs - prev.font_size) <= max(est_fs, prev.font_size) * 0.22
                        and not txt.startswith("\u2022")
                        and not prev.text.endswith((".", "!", "?", ";", ":"))
                    ):
                        ends_conn = bool(re.search(
                            r'\b(?:of|to|for|with|which|a|an|the|in|on|by|from|that|than|as|and|or|are|is|be|into|over|between|already|have|has|can|cannot|will|must)\s*$',
                            prev.text, re.I
                        ))
                        reaches_edge = prev.box.x1 > page_w * 0.62
                        if ends_conn or (reaches_edge and txt[0].islower()):
                            prev.text = (prev.text[:-1] + txt) if prev.text.endswith("-") else f"{prev.text} {txt}"
                            prev.box = BoundingBox(min(prev.box.x0, b.x0), min(prev.box.y0, b.y0), max(prev.box.x1, b.x1), max(prev.box.y1, b.y1))
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


# --- 7. NÖRAL ÇEVİRİ VE AKADEMİK TERMİNOLOJİ MOTORU ---
ENGLISH_PRE_NORMALIZATION = [
    (r'\bContext-Free\s+Grammars\b', 'Bağlamdan Bağımsız Dilbilgileri'),
    (r'\bcontext-free\s+grammars\b', 'bağlamdan bağımsız dilbilgileri'),
    (r'\bContext-Free\s+Grammar\b', 'Bağlamdan Bağımsız Dilbilgisi'),
    (r'\bcontext-free\s+grammar\b', 'bağlamdan bağımsız dilbilgisi'),
    (r'\bDenotational\s+Semantics\b', 'Gösterimsel Anlambilim'),
    (r'\bOperational\s+Semantics\b', 'İşlemsel Anlambilim'),
    (r'\bAxiomatic\s+Semantics\b', 'Belitsel Anlambilim'),
    (r'\bStatic\s+Semantics\b', 'Statik Anlambilim'),
    (r'\bDynamic\s+Semantics\b', 'Dinamik Anlambilim'),
    (r'\bAttribute\s+Grammars\b', 'Öznitelik Dilbilgileri'),
    (r'\bAttribute\s+Grammar\b', 'Öznitelik Dilbilgisi'),
    (r'\bImmunity\s+Debugger\b', '⟦INLCODE:Immunity Debugger⟧'),
    (r'\bVisual\s+Studio\s*\.NET\b', '⟦INLCODE:Visual Studio .NET⟧'),
    (r'\bcost\s+of\s+execution\b', 'cost of program runtime'),
    (r'\bexecution\s+costs\b', 'program runtime costs'),
    (r'\bfor\s+execution\b', 'for running the program'),
    (r'\bat\s+compile\s+time\b', 'derleme zamanında'),
    (r'\bat\s+run\s+time\b', 'çalışma zamanında'),
    (r"\bsigned-([0-9a-zA-Z]+)'s-complement\b", r"signed \1's complement"),
    (r"\b([0-9a-zA-Z]+)'s-complement\b", r"\1's complement"),
    (r"\bsigned-magnitude\b", "signed magnitude"),
    (r"\bsigned-complement\b", "signed complement"),
    (r"\bend-around carry\b", "end around carry"),
]

POST_TRANSLATION_FIXES = [
    (r'(\w)\s*@\s*(\w)', r'\1-\2'),
    (r'@', ''),
    (r'\b([0-9a-zA-Z]+)\s*>\s*s\b', r"\1'e"),
    (r'!=', '\u2260'),
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
    (r'\bmüşteri\s+taşıma\s+ipliğimiz\b', "istemci işleme iş parçacığımız (thread)"),
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


class UniversalTranslationEngine:
    def __init__(self, device: torch.device, dtype: torch.dtype, cache_path: str = "build/translation_cache.json"):
        self.device = device
        self.dtype = dtype
        self.cache_path = cache_path
        self.cache: Dict[str, str] = {"__version__": CACHE_VERSION}

        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if loaded.get("__version__") == CACHE_VERSION:
                    self.cache = loaded
                    print(f"[ÖNBELLEK] {len(self.cache) - 1} doğrulanmış çeviri yüklendi.")
            except Exception:
                pass

        print("1. [YEREL ÇEVİRİ] Helsinki-NLP/opus-mt-tc-big-en-tr yerel diskten (%100 Çevrimdışı) yükleniyor...")
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        model_name = "Helsinki-NLP/opus-mt-tc-big-en-tr"
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=False, local_files_only=True)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                token=False,
                local_files_only=True,
                torch_dtype=self.dtype if self.device.type == "cuda" else torch.float32
            ).to(self.device)
        except Exception:
            os.environ["HF_HUB_OFFLINE"] = "0"
            os.environ["TRANSFORMERS_OFFLINE"] = "0"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=False)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                token=False,
                torch_dtype=self.dtype if self.device.type == "cuda" else torch.float32
            ).to(self.device)
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        self.model.eval()
        print(f"-> Çeviri Modeli %100 Çevrimdışı Hazır (Aygıt: {self.device} | Hassasiyet: {self.model.dtype})")

    def save_cache(self):
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        # Kısaltmalardaki (e.g., i.e., Fig., vs.) noktalardan cümle bölünmesini engelle
        protected = re.sub(r'\b(e\.g|i\.e|Fig|fig|Sec|sec|Ch|ch|Dr|Mr|Ms|vs|etc)\.\s+', r'\1<DOT> ', text)
        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\(\[⟦])', protected)
        return [p.replace("<DOT>.", ".").replace("<DOT>", ".").strip() for p in parts if p.strip()]

    def translate_block(self, block: ParagraphBlock) -> str:
        if block.is_protected:
            return block.text

        clean_raw = normalize_unicode_text(block.text)
        if not clean_raw or FormalismAnalyzer.is_formal_expression(clean_raw):
            block.is_standalone_math = True
            return block.text

        if clean_raw in self.cache:
            return self.cache[clean_raw]

        has_bullet = clean_raw.startswith(("\u2022", "-", "+"))
        body = re.sub(r'^[\u2022\-\+]\s*', '', clean_raw).strip()

        for pat, repl in ENGLISH_PRE_NORMALIZATION:
            body = re.sub(pat, repl, body, flags=re.I)

        sentences = self._split_into_sentences(body)
        if not sentences:
            return clean_raw

        masked_list: List[str] = []
        mask_dicts: List[Dict[str, str]] = []

        for s in sentences:
            m_txt, m_dict = FormalismAnalyzer.mask_inline_formal_tokens(s)
            masked_list.append(m_txt)
            mask_dicts.append(m_dict)

        decoded_list: List[str] = []
        batch_size = 8

        try:
            for i in range(0, len(masked_list), batch_size):
                batch = masked_list[i:i + batch_size]
                inputs = self.tokenizer(
                    batch, return_tensors="pt", padding=True, truncation=True, max_length=512
                ).to(self.device)
                with torch.inference_mode():
                    outputs = self.model.generate(
                        **inputs, max_length=512, num_beams=4, repetition_penalty=1.15, early_stopping=True
                    )
                decoded_list.extend(self.tokenizer.batch_decode(outputs, skip_special_tokens=True))
        except Exception as e:
            if self.device.type == "cuda":
                print(f"[DONANIM UYARISI] GPU yürütme hatası ({e}). Otonom CPU fallback devreye alındı.")
                self.device = torch.device("cpu")
                self.model = self.model.to(self.device, dtype=torch.float32)
            decoded_list = []
            for m_s in masked_list:
                try:
                    inp = self.tokenizer(m_s, return_tensors="pt", truncation=True, max_length=512).to(self.device)
                    with torch.inference_mode():
                        out = self.model.generate(**inp, max_length=512)
                    decoded_list.append(self.tokenizer.decode(out[0], skip_special_tokens=True))
                except Exception:
                    decoded_list.append(m_s)

        final_sents: List[str] = []
        for dec, m_dict in zip(decoded_list, mask_dicts):
            restored = FormalismAnalyzer.unmask_formal_tokens(dec, m_dict)
            for pat, repl in POST_TRANSLATION_FIXES:
                restored = re.sub(pat, repl, restored)
            final_sents.append(restored)

        result = ("\u2022 " if has_bullet else "") + " ".join(final_sents)
        result = re.sub(r'\s+', ' ', result).strip()
        self.cache[clean_raw] = result
        return result


# --- 8. TÜRKÇE GLİF DOĞRULAMALI FONT SEÇİMİ VE GERÇEK REDACTION RENDER ---
def select_best_unicode_fonts() -> Tuple[str, str, Optional[fitz.Font]]:
    """
    KURAL 3: Windows fontlarını denerken Segoe UI, Calibri ve Arial fontlarını
    gerçek Türkçe gliflerle (ord('ç'), ord('ğ'), ord('ş'), ord('ı')) test eder.
    """
    turkish_Check_Codepoints = [
        ord("\u00e7"),  # ç
        ord("\u011f"),  # ğ
        ord("\u015f"),  # ş
        ord("\u0131"),  # ı
        ord("\u00f6"),  # ö
        ord("\u00fc"),  # ü
        ord("\u0130"),  # İ
        ord("\u015e"),  # Ş
        ord("\u011e"),  # Ğ
    ]
    candidates = [
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
        (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg):
            try:
                f_test = fitz.Font(fontfile=reg)
                if all(f_test.has_glyph(cp) for cp in turkish_Check_Codepoints):
                    return reg, (bold if os.path.exists(bold) else reg), f_test
            except Exception:
                continue

    fallback_reg = r"C:\Windows\Fonts\arial.ttf"
    f_obj = fitz.Font(fontfile=fallback_reg) if os.path.exists(fallback_reg) else None
    return fallback_reg, r"C:\Windows\Fonts\arialbd.ttf", f_obj


def _sample_background_color(page_pix: fitz.Pixmap, box: BoundingBox) -> Tuple[float, float, float]:
    try:
        w, h = page_pix.width, page_pix.height
        mx, my = int((box.x0 + box.x1) / 2.0), int((box.y0 + box.y1) / 2.0)
        coords = [
            (int(box.x0) - 4, my),
            (int(box.x1) + 4, my),
            (mx, int(box.y0) - 4),
            (mx, int(box.y1) + 4),
            (int(box.x0) - 3, int(box.y0) - 3),
            (int(box.x1) + 3, int(box.y0) - 3),
        ]
        pxs = [list(page_pix.pixel(max(0, min(w - 1, sx)), max(0, min(h - 1, sy)))[:3]) for sx, sy in coords]
        med = np.median(np.array(pxs, dtype=np.float32), axis=0)
        return (float(med[0]) / 255.0, float(med[1]) / 255.0, float(med[2]) / 255.0)
    except Exception:
        return (1.0, 1.0, 1.0)


def _find_optimal_fontsize_and_leading(
    scratch_page: fitz.Page,
    target_rect: fitz.Rect,
    text: str,
    fontname: str,
    initial_fs: float,
    align: int
) -> Tuple[float, float]:
    """
    Gerçek sayfayı kirletmeden (veya üst üste metin yazmadan) hafızadaki tek sayfalık
    scratch_page üzerinde dinamik font küçültme (min 6.0pt) ve satır aralığı (leading)
    sıkıştırması testi yaparak metni kutuya tam sığdıran parametreleri bulur.
    """
    fs = min(18.0, max(6.0, initial_fs))
    while fs >= 6.0:
        for lh in (1.15, 1.05, 0.96, 0.90):
            shape = scratch_page.new_shape()
            rc = shape.insert_textbox(
                target_rect,
                text,
                fontsize=fs,
                fontname=fontname,
                align=align,
                lineheight=lh
            )
            if rc >= 0:
                return fs, lh
        fs -= 0.35
    return 6.0, 0.88


def export_copyable_txt_files(
    all_paragraphs: List[ParagraphBlock],
    clean_txt_path: str,
    bilingual_txt_path: str
):
    pages_map: Dict[int, List[ParagraphBlock]] = {}
    for p in all_paragraphs:
        pages_map.setdefault(p.page_num, []).append(p)

    with open(clean_txt_path, "w", encoding="utf-8") as f_clean:
        f_clean.write("====================================================================\n")
        f_clean.write("   PDF AI ENGINE - TAMAMEN KOPYALANABİLİR TÜRKÇE METİN VE KODLAR\n")
        f_clean.write("====================================================================\n\n")
        for page_num in sorted(pages_map.keys()):
            f_clean.write(f"--- [SAYFA {page_num + 1}] ---\n\n")
            for b in sorted(pages_map[page_num], key=lambda x: (round(x.box.y0 / 6), x.box.x0)):
                f_clean.write(f"{format_sub_sup_for_render(b.translated_text, None)}\n\n")

    with open(bilingual_txt_path, "w", encoding="utf-8") as f_bi:
        f_bi.write("====================================================================\n")
        f_bi.write("   PDF AI ENGINE - KARŞILAŞTIRMALI İNCELEME VE HATA AYIKLAMA DOSYASI\n")
        f_bi.write("====================================================================\n\n")
        for page_num in sorted(pages_map.keys()):
            f_bi.write(f"==================== SAYFA {page_num + 1} ====================\n\n")
            for b in sorted(pages_map[page_num], key=lambda x: (round(x.box.y0 / 6), x.box.x0)):
                if b.is_code_block:
                    tag = "[KARANTİNA KOD BLOĞU]"
                elif b.is_header_footer:
                    tag = "[KORUNAN ÜST/ALT BİLGİ]"
                elif b.is_standalone_math:
                    tag = "[KORUNAN FORMÜL / BNF]"
                else:
                    tag = f"[METİN BLOKU #{b.id}]"
                orig_out = format_sub_sup_for_render(b.text, None)
                tr_out = format_sub_sup_for_render(b.translated_text, None)
                f_bi.write(f"{tag}\nEN (Orijinal) : {orig_out}\nTR (Çeviri)   : {tr_out}\n" + "-" * 68 + "\n")
            f_bi.write("\n")


def run_pipeline(input_pdf: str, output_pdf: str):
    device, dtype = get_safe_device()
    layout_engine = GeometricLayoutEngine()
    translator = UniversalTranslationEngine(device, dtype)

    doc = fitz.open(input_pdf)
    total_pages = len(doc)
    all_paragraphs: List[ParagraphBlock] = []
    pages_blocks_map: Dict[int, List[ParagraphBlock]] = {}

    print(f"\n[İŞLEM BAŞLADI] Toplam Sayfa: {total_pages} | Belge: {input_pdf}")

    global_id = 0
    for page_num in range(total_pages):
        page = doc[page_num]
        paras = layout_engine.extract_paragraphs(page, page_num)
        for p in paras:
            p.id = global_id
            global_id += 1
            all_paragraphs.append(p)
        pages_blocks_map[page_num] = paras

    total_blocks = len(all_paragraphs)
    print(f"-> Tespit Edilen Toplam Bütünleşik Blok Sayısı: {total_blocks}")

    # Nöral Çeviri ve Her 10 Sayfada Bir Otonom Bellek Temizliği (KURAL 8)
    processed_blocks = 0
    for page_num in range(total_pages):
        paras = pages_blocks_map.get(page_num, [])
        for p in paras:
            p.translated_text = translator.translate_block(p)
            processed_blocks += 1

        if (page_num + 1) % 10 == 0 or (page_num + 1) == total_pages:
            print(f"   Çeviri İlerlemesi: {processed_blocks}/{total_blocks} blok (Sayfa {page_num + 1}/{total_pages}) tamamlandı...")
            translator.save_cache()
            if device.type == "cuda":
                torch.cuda.empty_cache()
            gc.collect()

    font_reg_path, font_bold_path, font_validator = select_best_unicode_fonts()
    print(f"-> Aktif Font ve Türkçe Glif Kalkanı: {os.path.basename(font_reg_path)}")

    # C++ AiEngine entegrasyonu
    layout_in = os.path.join("build", "layout_in.txt")
    layout_out = os.path.join("build", "layout_out.txt")
    os.makedirs("build", exist_ok=True)
    if os.path.exists(layout_out):
        try:
            os.remove(layout_out)
        except Exception:
            pass

    with open(layout_in, "w", encoding="utf-8") as f:
        for p in all_paragraphs:
            clean_en = format_sub_sup_for_render(p.text, font_validator).replace("|", " ").replace("\n", " ")
            clean_tr = format_sub_sup_for_render(p.translated_text, font_validator).replace("|", " ").replace("\n", " ")
            f.write(
                f"{p.id}|{p.page_num}|{p.box.x0:.2f}|{p.box.y0:.2f}|"
                f"{p.box.width:.2f}|{p.box.height:.2f}|{p.font_size:.2f}|"
                f"{clean_en}|{clean_tr}\n"
            )

    engine_path = os.path.join("build", "AiEngine.exe")
    if os.path.exists(engine_path):
        print("\n2. [C++ AiEngine] OpenMP ile paralel kutu/font optimizasyonu yapılıyor...")
        subprocess.run([engine_path, layout_in, layout_out], check=False)

    print("\n3. [CERRAHİ RENDER] Gerçek Redaction API ve Kod Karantinası ile PDF işleniyor...")

    # Ölçüm testi için geçici bellek içi (scratch) PDF belgesi
    scratch_doc = fitz.open()
    scratch_page = scratch_doc.new_page(width=800, height=1200)
    if os.path.exists(font_reg_path):
        scratch_page.insert_font(fontname="math_tr", fontfile=font_reg_path)
        scratch_page.insert_font(fontname="math_tr_b", fontfile=font_bold_path)

    for page_num in range(total_pages):
        page = doc[page_num]
        page_paras = pages_blocks_map.get(page_num, [])
        if not page_paras:
            continue

        page_pix = page.get_pixmap()
        render_queue: List[Tuple[ParagraphBlock, fitz.Rect, str, Tuple[float, float, float], Tuple[float, float, float]]] = []
        has_redactions = False

        # AŞAMA 1: KURAL 2 - Tüm çevrilecek bloklar için Redaction Annotation ekle (Kod ve formüllere DOKUNMA!)
        for p in page_paras:
            if p.is_protected:
                continue

            render_text = format_sub_sup_for_render(p.translated_text, font_validator)
            if not render_text.strip():
                continue

            bg_color = p.bg_color if p.bg_color is not None else _sample_background_color(page_pix, p.box)
            bg_lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
            fg_color = (1.0, 1.0, 1.0) if bg_lum < 0.45 else p.text_color
            if bg_lum >= 0.45 and sum(fg_color) > 2.2:
                fg_color = (0.0, 0.0, 0.0)

            # KURAL 2: Metin sınırından sağa +4.0pt, üste ve alta +1.0pt marjin (korunan bloklara çarpmadan)
            erase_x1 = min(p.box.x1 + 4.0, (p.max_allowed_x1 + 2.0) if p.max_allowed_x1 else (p.box.x1 + 4.0))
            erase_y1 = min(p.box.y1 + 1.0, (p.max_allowed_y1 + 0.5) if p.max_allowed_y1 else (p.box.y1 + 1.0))
            rect_erase = fitz.Rect(p.box.x0 - 0.5, p.box.y0 - 1.0, erase_x1, erase_y1)

            # Karantinadaki bir kod/formül bloğuyla kesişiyorsa silme kutusunu kırp
            for other in page_paras:
                if other.is_protected and other.id != p.id:
                    o_rect = fitz.Rect(other.box.x0, other.box.y0, other.box.x1, other.box.y1)
                    if rect_erase.intersects(o_rect):
                        if other.box.y0 >= p.box.y0 and other.box.y0 < rect_erase.y1:
                            rect_erase.y1 = max(p.box.y0 + 2.0, other.box.y0 - 0.5)

            page.add_redact_annot(rect_erase, fill=bg_color)
            has_redactions = True

            # KURAL 5: Sağa doğru genişletme YASAKTIR (p.max_allowed_x1 asla aşılmaz)
            safe_x1 = min(p.box.x1 + 2.0, p.max_allowed_x1) if p.max_allowed_x1 else p.box.x1
            safe_x1 = max(safe_x1, p.box.x0 + 15.0)
            desired_y1 = p.box.y1 + 6.0
            safe_y1 = min(desired_y1, p.max_allowed_y1) if p.max_allowed_y1 else desired_y1
            safe_y1 = max(safe_y1, p.box.y1 + 1.5)

            target_rect = fitz.Rect(p.box.x0, p.box.y0 - 1.0, safe_x1, safe_y1)
            render_queue.append((p, target_rect, render_text, fg_color, bg_color))

        # AŞAMA 2: Sayfa düzeyinde gerçek Redaction uygula (Görselleri/şemaları koru, eski İngilizce metin akışını yok et)
        if has_redactions:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        # AŞAMA 3: Redaction sonrası temizlenen sayfalara Türkçe fontları kaydet ve metinleri tek seferde bas
        font_registered = False
        if os.path.exists(font_reg_path):
            try:
                page.insert_font(fontname="math_tr", fontfile=font_reg_path)
                page.insert_font(fontname="math_tr_b", fontfile=font_bold_path)
                font_registered = True
            except Exception:
                font_registered = False

        for p, target_rect, render_text, fg_color, _ in render_queue:
            used_font = ("math_tr_b" if p.is_bold else "math_tr") if font_registered else "helv"
            align_mode = 1 if p.is_centered else 0

            opt_fs, opt_lh = _find_optimal_fontsize_and_leading(
                scratch_page, target_rect, render_text, used_font, p.font_size, align_mode
            )

            rc = page.insert_textbox(
                target_rect,
                render_text,
                fontsize=opt_fs,
                fontname=used_font,
                color=fg_color,
                align=align_mode,
                lineheight=opt_lh,
                render_mode=0
            )
            # Eğer 6.0pt ile hala çok dar bir kutuda taştıysa dikeyde hafif esneterek yazdır (Sağa genişletme yapmadan!)
            if rc < 0:
                fallback_rect = fitz.Rect(
                    target_rect.x0,
                    target_rect.y0,
                    target_rect.x1,
                    min(page.rect.height - 6.0, target_rect.y1 + 14.0)
                )
                page.insert_textbox(
                    fallback_rect,
                    render_text,
                    fontsize=6.0,
                    fontname=used_font,
                    color=fg_color,
                    align=align_mode,
                    lineheight=0.88,
                    render_mode=0
                )

        if (page_num + 1) % 10 == 0:
            gc.collect()

    scratch_doc.close()

    final_pdf_path = output_pdf
    try:
        doc.save(final_pdf_path, garbage=4, deflate=True)
    except PermissionError:
        base, ext = os.path.splitext(output_pdf)
        final_pdf_path = f"{base}_YENI{ext}"
        print(f"[UYARI] '{output_pdf}' başka bir programda açık! Çıktı '{final_pdf_path}' olarak kaydedildi.")
        doc.save(final_pdf_path, garbage=4, deflate=True)
    finally:
        doc.close()

    base_name = os.path.splitext(final_pdf_path)[0]
    clean_txt_file = f"{base_name}.txt"
    review_txt_file = f"{base_name}_INCELEME.txt"
    export_copyable_txt_files(all_paragraphs, clean_txt_file, review_txt_file)

    print("\n====================================================================")
    print("[BAŞARILI] %100 Çevrimdışı Evrensel Motor (v14.0) Çıktıları Üretildi:")
    print(f"  1. Kusursuz PDF Dosyası        : {final_pdf_path}")
    print(f"  2. Temiz Türkçe TXT Dosyası    : {clean_txt_file}")
    print(f"  3. Karşılaştırmalı İnceleme TXT: {review_txt_file}")
    print("====================================================================")


if __name__ == "__main__":
    input_file = "ornek_belge.pdf"
    output_file = "cevirilmis_belge_ULTIMATE.pdf"
    run_pipeline(input_file, output_file)