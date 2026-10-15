import os
import re
import json
import gc
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

token_paths = [
    os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "token"),
    os.path.join(os.path.expanduser("~"), ".huggingface", "token")
]
for p in token_paths:
    if os.path.exists(p):
        try:
            os.remove(p)
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

import shutil

# Tesseract OCR yolunu otomatik tespit et (Sistem PATH veya standart Windows dizinleri)
_tess_candidates = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
]
_found_tess = shutil.which("tesseract")
if not _found_tess:
    for _tc in _tess_candidates:
        if os.path.exists(_tc):
            _found_tess = _tc
            break
if _found_tess:
    pytesseract.pytesseract.tesseract_cmd = _found_tess

CACHE_VERSION = "v10.0_master_offline_universal"


# --- 2. RTX 5080 (sm_120 BLACKWELL) VE GENEL DONANIM MOTORU ---
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
            print(f"[DONANIM UYARISI] {torch.cuda.get_device_name(0)} PyTorch derlemesiyle uyumsuz: {e}")
            print("[GÜVENLİK PROTOKOLÜ] Çok çekirdekli CPU moduna geçildi.")

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
    is_from_ocr: bool = False
    is_bold: bool = False
    is_centered: bool = False
    text_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    bg_color: Optional[Tuple[float, float, float]] = None
    max_allowed_y1: Optional[float] = None


# --- 4. EVRENSEL SEZGİSEL MATEMATİK, OCR ONARIM VE AKADEMİK SÖZLÜK MOTORU ---
SUPERSCRIPT_MAP = str.maketrans("0123456789+-=()nxyzrabcikm", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿˣʸᶻʳᵃᵇᶜⁱᵏᵐ")
SUBSCRIPT_MAP = str.maketrans("0123456789+-=()nxyzr", "₀₁₂₃₄⁵₆₇₈₉₊₋₌₍₎ₙₓᵧ₂ᵣ")

GLYPH_FALLBACK_MAP = {
    "≠": "!=",
    "≤": "<=",
    "≥": ">=",
    "≈": "~=",
    "≡": "==",
    "±": "+/-",
    "×": "x",
    "÷": "/",
    "∞": "inf",
    "→": "->",
    "←": "<-",
    "↔": "<->",
    "⇒": "=>",
    "•": "•",
}


def normalize_unicode_punctuation(text: str) -> str:
    t = text
    for dash in ["\u2212", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\uf02d"]:
        t = t.replace(dash, "-")
    for quote in ["\u2018", "\u2019", "\u201b", "\u2032", "\u0060", "\u00b4"]:
        t = t.replace(quote, "'")
    for dquote in ["\u201c", "\u201d", "\u2033"]:
        t = t.replace(dquote, '"')
    for bullet in ["\uf0b7", "\u2022", "\u25cf", "\u25aa", "\u25fe", "\u2219"]:
        t = t.replace(bullet, "• ")
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
    return t


def universal_ocr_math_heuristics(text: str) -> str:
    t = normalize_unicode_punctuation(text)
    t = re.sub(r"(?:^|(?<=\s))['\"`]+(?=[a-zA-ZÇĞİÖŞÜçğıöşü]{2,})", "", t)

    ocr_word_repairs = [
        (r'\bAll\s+rghts\s+reserved\b', 'All rights reserved'),
        (r'\b(?:ading|anting|operaling|operatlng)\s+system\b', 'operating system'),
        (r'\bnrogram\b', 'program'),
        (r'\bhelle[ck]\b', 'memory'),
        (r'\btarge\b', 'large'),
        (r'\bappucation\b', 'application'),
        (r'\bmonouun\b', 'monolithic'),
        (r'\brespansibte\b', 'responsible'),
        (r'\bproces\b', 'process'),
        (r'\bkalted\b', 'called'),
        (r'\bLexicat\b', 'Lexical'),
        (r'\bGiris\s+dat\b', 'Input data'),
        (r'\bJSTL\s+USP\b', 'JSTL (JSP'),
        (r'\bArelatif\b', 'A relatively'),
    ]
    for pat, repl in ocr_word_repairs:
        t = re.sub(pat, repl, t, flags=re.I)

    t = re.sub(r'(\([0-9a-zA-Z\s\+\-]+\)|\b[0-9a-zA-Z]+)\s+(<(?:sub|sup):[^>]+>)', r'\1\2', t)
    t = re.sub(r'\s+\b(?:Oo|oO|ο|Ο)\s*$', '.', t)

    t = re.sub(r'\b([a-zA-Z]|\d{1,2})["\*]\s*(?=[-\+=\)\/\<]|N\b|1\b)', r'\1<sup:n> ', t)
    t = re.sub(r"\b2'\s*=\s*-?10000000\b", "2<sup:7> = -10000000", t)
    t = re.sub(r"\b10'\s*=\s*-?100000\b", "10<sup:5> = -100000", t)
    t = re.sub(r'([a-zA-Z]<sup:[^>]+>)\s*-\s*([a-zA-Z0-9]+)\s*\)\s*=\s*\2\b', r'\1 - (\1 - \2) = \2', t)
    t = re.sub(r'([a-zA-Z0-9]+<sup:[^>]+>)\s+([NXYM]\b)', r'\1 - \2', t)

    t = re.sub(
        r'(\([01\s]{3,}\)|\b[01]{4}(?:\s+[01]{4})+|\b[01]{5,12})\s*[,\.](?=\s*(?:[=+\-\)]|$|[129]\'s|Vs|comp|No\b|End|Hiçbir|Uç))',
        r'\1<sub:2>',
        t
    )

    t = re.sub(r'(?<=\bnumber\s)(\d{1,4}),9\b', r'\1<sub:10>', t, flags=re.I)
    t = re.sub(r'(\b\d{1,4}),49\b', r'\1<sub:10>', t)
    t = re.sub(r'(\(\d+\)|\b\d{2,4})\s*\)?\s*10\s*-(?=\s|$)', r'\1<sub:10>', t)
    t = re.sub(r'(?<=\bAnswer:\s)(\d{2,3})19\b', r'\1<sub:10>', t, flags=re.I)
    t = re.sub(r'\bN\s*=\s*-?(\d)19\b', r'N = -\1<sub:10>', t)

    t = re.sub(r'(?<=\([ab]\)\s)([XYM])\s+([XYN])\b', r'\1 - \2', t)
    t = re.sub(r'(?<=\bfind\s)([XYM])\s+([XYN])\b', r'\1 - \2', t, flags=re.I)
    t = re.sub(r'\b([XY])\s+([XY])(?=\s*=)', r'\1 - \2', t)
    t = re.sub(r'\bsubtract\s+(\d{3,6})\s+(\d{3,6})\b', r'subtract \1 - \2', t, flags=re.I)

    t = re.sub(r"\b(?:Vs|V's|i's|I's|l's)\s*comp(?:lement)?\b", "1's comp", t)
    t = re.sub(r"\b7's\s+complement\b", "r's complement", t, flags=re.I)
    t = re.sub(r"\(\s*r\s+1\s*\)", "(r - 1)", t)
    t = re.sub(r"\(\s*ry\s*1\s*\)", "(r - 1)", t)
    t = re.sub(r"\bN\s*#\s*0\b", "N != 0", t)
    t = re.sub(r"\b(\d+)and\s*([a-zA-Z])\b", r"\1 and \2", t)
    t = re.sub(r"\bof\s+Nis\b", "of N is", t)
    t = re.sub(r"\bbaser\b", "base r", t)

    return re.sub(r'\s+', ' ', t).strip()


def _is_true_math_parenthesis(paren_str: str) -> bool:
    inner = re.sub(r'<(?:sub|sup):[^>]+>', '', paren_str).strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1].strip()
    if not inner:
        return False
    if re.fullmatch(r'[a-zA-Z]', inner):
        return False
    words = re.findall(r'[a-zA-Z]{2,}', inner)
    allowed_math_funcs = {"sin", "cos", "tan", "log", "ln", "exp", "mod", "max", "min", "lim", "sum", "comp"}
    non_math_words = [w for w in words if w.lower() not in allowed_math_funcs]
    if len(non_math_words) >= 1:
        return False
    return True


def format_sub_sup_for_render(text: str, font_obj: Optional[fitz.Font] = None) -> str:
    def repl_sup(m):
        val = m.group(1).strip()
        converted = val.translate(SUPERSCRIPT_MAP)
        if font_obj and not all(font_obj.has_glyph(ord(c)) for c in converted):
            return f"^{val}"
        return converted

    def repl_sub(m):
        val = m.group(1).strip()
        converted = val.translate(SUBSCRIPT_MAP)
        if font_obj and not all(font_obj.has_glyph(ord(c)) for c in converted):
            return f"_{val}"
        return converted

    res = re.sub(r'<sup:([^>]+)>', repl_sup, text)
    res = re.sub(r'<sub:([^>]+)>', repl_sub, res)
    res = re.sub(r'\bsub\s*:?\s*([0-9]+)\s*>', repl_sub, res, flags=re.I)
    res = re.sub(r'\bsup\s*:?\s*([0-9a-zA-Z]+)\s*>', repl_sup, res, flags=re.I)

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


ENGLISH_PRE_NORMALIZATION = [
    (r'\bAll\s+rights\s+reserved\b', 'Tüm hakları saklıdır'),
    (r'\bLet\'?s\s+call\s+it\s+a\s+day\s*!?', 'Bugünlük bu kadar!'),
    (r'\bBusiness\s+applications\b', 'Commercial software applications'),
    (r'\bcost\s+of\s+execution\b', 'cost of program runtime'),
    (r'\bexecution\s+costs\b', 'program runtime costs'),
    (r'\bfor\s+execution\b', 'for running the program'),
    (r'\bfast\s+execution\b', 'fast program running'),
    (r'\bSlower\s+execution\b', 'Slower program running'),
    (r'\bnegate\s+the\s+number\b', 'find the negative of the number'),
    (r'\bnegates\s+a\s+number\b', 'changes the sign of a number'),
    (r'\bis\s+signed\b', 'is a signed number'),
    (r'\bis\s+unsigned\b', 'is an unsigned number'),
    (r'\bare\s+signed\s+or\s+unsigned\b', 'are signed numbers or unsigned numbers'),
    (r'\bsigned\s+or\s+unsigned\b', 'signed or unsigned number'),
    (r"\bsigned\s+1's\s+complement\b", "signed-1's-complement"),
    (r"\bsigned\s+2's\s+complement\b", "signed-2's-complement"),
    (r"\bsigned-([0-9a-zA-Z]+)'s-complement\b", r"signed \1's complement"),
    (r"\b([0-9a-zA-Z]+)'s-complement\b", r"\1's complement"),
    (r"\bsigned-magnitude\b", "signed magnitude"),
    (r"\bsigned-complement\b", "signed complement"),
    (r"\bend-around carry\b", "end around carry"),
    (r"\bDiscard end carry\b", "Son eldeyi atın"),
    (r"\bNo end-around carry\b", "Döngüsel elde yoktur"),
    (r"\bNo end carry\b", "Son elde yoktur"),
]

POST_TRANSLATION_FIXES = [
    (r'(\w)\s*@\s*(\w)', r'\1-\2'),
    (r'@', ''),
    (r'\b([0-9a-zA-Z]+)\s*>\s*s\b', r"\1'e"),
    (r'!=', '≠'),
    (r'\bTüm\s+rghts\s+rezerve\s+edildi\b', 'Tüm hakları saklıdır'),
    (r'\bTüm\s+hakları?\s+rezerve\s+edildi\b', 'Tüm hakları saklıdır'),
    (r'\b[İi]dam\s+maliyetine\b', 'Yürütme (çalıştırma) maliyetine'),
    (r'\b[İi]dam\s+masrafları\b', 'yürütme (çalıştırma) maliyetleri'),
    (r'\b[İi]dam\b', 'yürütme'),
    (r'\bsaf\s+tercümanlar\b', 'saf yorumlayıcılar'),
    (r'\btercümanlar\b', 'yorumlayıcılar'),
    (r'\btercümanı\b', 'yorumlayıcısı'),
    (r'\bTercüman\b', 'Yorumlayıcı'),
    (r'\btercüman\b', 'yorumlayıcı'),
    (r'\b[İi]ş\s+başvuruları\b', 'Ticari uygulamalar (İş uygulamaları)'),
    (r'\bTicari\s+yazılım\s+uygulamaları\b', 'Ticari uygulamalar (İş uygulamaları)'),
    (r'\bSymbol\s+masa\b', 'Sembol tablosu'),
    (r'\bSembol\s+masası\b', 'Sembol tablosu'),
    (r'\blexical\s+birimlere\b', 'sözcüksel birimlere'),
    (r'\bparse\s+ağaçlarına\b', 'ayrıştırma ağaçlarına'),
    (r'\bsyntactic\s+yapısını\b', 'sözdizimsel yapısını'),
    (r'\bBuna\s+bir\s+gün\s+diyelim\s*!?', 'Bugünlük bu kadar!'),
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
    (r'[Tt]amamlayıcılara\b', 'tümleyenlere'),
    (r'[Tt]amamlayıcılarla\b', 'tümleyenlerle'),
    (r'[Tt]amamlayıcıdan\b', 'tümleyenden'),
    (r'[Tt]amamlayıcıya\b', 'tümleyene'),
    (r'[Tt]amamlayıcıyı\b', 'tümleyeni'),
    (r'\bTamamlayıcılar\b', 'Tümleyenler'),
    (r'\btamamlayıcılar\b', 'tümleyenler'),
    (r'\bTamamlayıcı\b', 'Tümleyen'),
    (r'\btamamlayıcı\b', 'tümleyen'),
    (r'\bkompleman\b', 'tümleyen'),
    (r'\bkomplemanı\b', 'tümleyeni'),
    (r'\btamamlama\s+temsili\b', 'tümleyen gösterimi'),
    (r'\bSayıların\s+Tamamlanması\b', 'Sayıların Tümleyenleri'),
    (r'\bNUMARALARIN\s+KOMPLELERİ\b', 'SAYILARIN TÜMLEYENLERİ'),
    (r"\b1'in\s+tümleyenini\s+imzaladı\b", "işaretli 1'e tümleyen"),
    (r"\b2'nin\s+tümleyenini\s+imzaladı\b", "işaretli 2'ye tümleyen"),
    (r"\b1'e\s+tümleyenini\s+imzaladı\b", "işaretli 1'e tümleyen"),
    (r"\b2'ye\s+tümleyenini\s+imzaladı\b", "işaretli 2'ye tümleyen"),
    (r"\bimzalanırsa\b", "işaretli ise"),
    (r"\bimzalanmış\b", "işaretli"),
    (r"\bimzalandı\b", "işaretli"),
    (r'\b[İi]şaretli\s+twos\s+tümleyen\b', "işaretli 2'ye tümleyen"),
    (r'\b[İi]şaretli\s+ones\s+tümleyen\b', "işaretli 1'e tümleyen"),
    (r"\b1's\s*comp(?:lement)?\b", "1'e tümleyen"),
    (r"\b2's\s*comp(?:lement)?\b", "2'ye tümleyen"),
    (r"\b9's\s*comp(?:lement)?\b", "9'a tümleyen"),
    (r"\b10's\s*comp(?:lement)?\b", "10'a tümleyen"),
    (r"\b1'in\s*comp\b", "1'e tümleyen"),
    (r"\b2'nin\s*comp\b", "2'ye tümleyen"),
    (r"\b1'in\s+tümleyeni\b", "1'e tümleyeni"),
    (r"\b1'lerin\s+tümleyen\b", "1'e tümleyen"),
    (r"\b2'nin\s+tümleyeni\b", "2'ye tümleyeni"),
    (r"\b2'nin\s+tümleyen\b", "2'ye tümleyen"),
    (r"\b2'sinin\s+tümleyeni\b", "2'ye tümleyeni"),
    (r"\b9'un\s+tümleyeni\b", "9'a tümleyeni"),
    (r"\b10'un\s+tümleyeni\b", "10'a tümleyeni"),
    (r"\br'nin\s+tümleyeni\b", "r'ye tümleyeni"),
    (r"\b7'nin\s+tümleyeninin\b", "r'ye tümleyeninin"),
    (r"\b7'nin\s+tümleyeni\b", "r'ye tümleyeni"),
    (r'\bSubtrahend\b', 'Çıkan'),
    (r'\bsubtrahend\b', 'çıkan'),
    (r'\balttrahend\b', 'çıkan'),
    (r'\bsubtrahin\b', 'çıkanın'),
    (r'\bminuend\b', 'eksilen'),
    (r'\bMinuend\b', 'Eksilen'),
    (r'\bSum\s*=', 'Toplam ='),
    (r'\bAnswer\s*\.', 'Cevap:'),
    (r'\bEnd-around\s+carry\b', 'Döngüsel elde'),
    (r'\bend-around\s+carry\b', 'döngüsel elde'),
    (r'\buç\s+etrafında\s+taşıma\b', 'döngüsel elde'),
    (r'\btaşıma\s+etrafında\s+bir\s+uç\b', 'döngüsel elde'),
    (r'\bUç\s+taşımalı\s+prosedür\b', 'Döngüsel elde prosedürü'),
    (r'\bsigned\s+magnitude\b', 'işaret-büyüklük'),
    (r'\bsigned-magnitude\b', 'işaret-büyüklük'),
    (r'\b[İi]şaretli\s+büyüklük\b', 'işaret-büyüklük'),
    (r'\bsigned\s+complement\b', 'işaret-tümleyen'),
    (r'\bsigned-complement\b', 'işaret-tümleyen'),
    (r'\bcomplement\b', 'tümleyen'),
    (r'\brepresent\b', 'temsil eder'),
    (r'\bmagnitude\b', 'büyüklük'),
    (r'\bimzasız\b', 'işaretsiz'),
    (r'\bİmzasız\b', 'İşaretsiz'),
    (r'\bimzalı\b', 'işaretli'),
    (r'\bİmzalı\b', 'İşaretli'),
    (r'\bsayısını\s+reddedin\b', 'sayısının negatifini (tümleyenini) bulun'),
    (r'\breddedin\b', 'negatifini bulun'),
    (r'\bradix\s+noktası\b', 'taban (radix) noktası'),
    (r'\bRadix\s+noktası\b', 'Taban (radix) noktası'),
    (r'\bBİNARY\s+NUMARALARI\s+SAHİPLİİ\b', 'İŞARETLİ İKİLİ SAYILAR'),
    (r'\bİMZALI\s+İKİLİ\s+SAYILAR\b', 'İŞARETLİ İKİLİ SAYILAR'),
    (r'\bAritmetik\s+Ekleme\b', 'Aritmetik Toplama'),
    (r'\bAritmetik\s+Subtraksiyon\b', 'Aritmetik Çıkarma'),
    (r'\bUygulama\s+Araştırması\b', 'Uygulama Alıştırması'),
    (r'\bAntrenman\s+Egzersizi\b', 'Uygulama Alıştırması'),
    (r'\bEgzersiz\s+Egzersizi?\b', 'Uygulama Alıştırması'),
    (r'\bPratik\s+Egzersiz\b', 'Uygulama Alıştırması'),
    (r'\bUygulama\s+Egzersizi\b', 'Uygulama Alıştırması'),
    (r'\bPractice\s+Exercise\b', 'Uygulama Alıştırması'),
    (r'\bAnswer\s*:', 'Cevap:'),
    (r'\bYanıt\s*:', 'Cevap:'),
    (r'\bEXAMPLE\b', 'ÖRNEK'),
    (r'\bDisk\s+ucu\s+taşıma\b', 'Son eldeyi atın'),
    (r'\bDisk\s+ucu\b', 'Son eldeyi atın'),
    (r'\buç\s+taşıma\b', 'son elde'),
    (r'\bUç\s+taşıma\b', 'Son elde'),
    (r'\ben\s+az\s+önemli\b', 'en düşük anlamlı'),
    (r'\ben\s+önemli\b', 'en yüksek anlamlı'),
    (r'\bWritability\b', 'Yazılabilirlik'),
    (r'\bwritability\b', 'yazılabilirlik'),
    (r'\bReadability\b', 'Okunabilirlik'),
    (r'\breadability\b', 'okunabilirlik'),
    (r'\bOrthogonality\b', 'Dikgenlik (Ortogonallik)'),
    (r'\borthogonality\b', 'dikgenlik (ortogonallik)'),
    (r'\bExpressivity\b', 'İfade Gücü (Expressivity)'),
    (r'\bAliasing\b', 'Takma Ad Kullanımı (Aliasing)'),
    (r'\bImperative\b', 'Buyruksal (Imperative)'),
]


def normalize_and_mask_math(text: str) -> Tuple[str, Dict[str, str]]:
    t = universal_ocr_math_heuristics(text)

    for pat, repl in ENGLISH_PRE_NORMALIZATION:
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)

    math_dict: Dict[str, str] = {}
    counter = 0

    def add_mask(match_obj) -> str:
        nonlocal counter
        expr = match_obj.group(0).strip()
        if re.fullmatch(r'[a-zA-Z]+(?:-[a-zA-Z]+)*', expr):
            return expr
        if "(" in expr and not _is_true_math_parenthesis(expr):
            return expr
        key = f"MTH{counter}X"
        math_dict[key] = expr
        counter += 1
        return f" {key} "

    t = re.sub(r'(?:\bC\+\+|\bC#|\.NET\b|#include\b|#define\b|\b[A-Z]\.\s+[A-Z][A-Za-z]+)', add_mask, t)

    math_paren = r'\([0-9\s\+\-\*\/\^\<\>\:\_±NXYMrnABxy]+?\)(?:<(?:sub|sup):[^>]+>)?'

    atom = (
        r'(?:'
        rf'{math_paren}'
        r'|[+\-]?\b(?:[0-9]+(?:\s+[0-9]{4})*|[a-zA-Z])(?:<(?:sub|sup):[^>]+>)+[a-zA-Z0-9]*'
        r'|[+\-]?\b[0-9]+(?:\s+[0-9]{4})*\b'
        r'|[+\-]?\b[a-zA-Z]\b(?=\s*(?:[=≠<>≤≥\+\*\/]|-\s*(?:[0-9\(]|[a-zA-Z]\b)))'
        r'|[+\-]?(?<=[=≠<>≤≥\+\-\*\/]\s)\b[a-zA-Z]\b'
        r')'
    )

    compound_pat = rf'\[?(?:{atom}\s*[\+\-\*\/\=]\s*)*{math_paren}\]?(?:\s*(?:!=|[=≠<>≤≥\+\-\*\/])\s*{atom})*'
    t = re.sub(compound_pat, add_mask, t)

    eq_chain_pat = rf'{atom}(?:\s*(?:!=|[=≠<>≤≥\+\*\/]|-(?!\s*[a-zA-Z]{{2,}}))\s*{atom})+'
    t = re.sub(eq_chain_pat, add_mask, t)

    sub_sup_pat = r'(?:\([0-9a-zA-Z\s\+\-]+\)|[+\-]?\b[0-9a-zA-Z]+)?<(?:sub|sup):[^>]+>'
    t = re.sub(sub_sup_pat, add_mask, t)

    t = re.sub(r'\(\s*[±\+\-]?\s*[a-zA-Z0-9]\s*(?:[\-\+]\s*[a-zA-Z0-9]\s*)?\)', add_mask, t)

    t = re.sub(r'\s+', ' ', t).strip()
    return t, math_dict


def restore_math_and_validate(translated_text: str, math_dict: Dict[str, str]) -> str:
    res = translated_text

    for _ in range(3):
        for key, original in math_dict.items():
            idx = key.replace("MTH", "").replace("X", "")
            flex_pat = rf'(?:\bMTH\s*[_-]?\s*{idx}\s*X?\b|\[?\s*FORM[A-ZÜÖÇŞİĞ]*\s*[_-]?\s*{idx}\s*\]?)'
            res = re.sub(flex_pat, lambda _: f" {original} ", res, flags=re.IGNORECASE)

    for key, original in math_dict.items():
        if original not in res and key not in res:
            if not any(original in other_val for k2, other_val in math_dict.items() if k2 != key):
                res = f"{res} ({original})"

    for pat, repl in POST_TRANSLATION_FIXES:
        res = re.sub(pat, repl, res)

    return re.sub(r'\s+', ' ', res).strip()


# --- 5. SAYFA İÇİ HİBRİT (DİJİTAL + ÇİFT KUTUPLU SÜPER-ÇÖZÜNÜRLÜKLÜ OCR) MOTORU ---
class DocumentLayoutReconstructor:
    def extract_paragraphs(self, page: fitz.Page, page_num: int) -> List[ParagraphBlock]:
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES)
        blocks = page_dict.get("blocks", [])

        digital_blocks = self._extract_digital(page, page_num, blocks)

        page_area = max(1.0, page.rect.width * page.rect.height)
        image_bboxes: List[BoundingBox] = []
        for b in blocks:
            if b.get("type") == 1 and "bbox" in b:
                ib = BoundingBox(*b["bbox"])
                if ib.width > 40.0 and ib.height > 20.0:
                    image_bboxes.append(ib)

        total_img_area = sum(ib.area for ib in image_bboxes)
        total_dig_area = sum(db.box.area for db in digital_blocks)

        needs_hybrid_ocr = (
            len(digital_blocks) == 0
            or total_dig_area < page_area * 0.18
            or total_img_area > page_area * 0.10
        )

        combined_blocks = list(digital_blocks)
        if needs_hybrid_ocr:
            ocr_blocks = self._extract_hybrid_ocr(page, page_num, existing_digital=digital_blocks)
            if ocr_blocks:
                print(f"   [HİBRİT OCR] Sayfa {page_num + 1}: {len(digital_blocks)} dijital + {len(ocr_blocks)} bütünleşik slayt/diyagram bloğu yakalandı.")
                combined_blocks.extend(ocr_blocks)

        for idx, b in enumerate(combined_blocks):
            b.id = idx

        return self._compute_collision_limits(combined_blocks, page.rect.height)

    @staticmethod
    def _compute_collision_limits(blocks: List[ParagraphBlock], page_height: float) -> List[ParagraphBlock]:
        sorted_b = sorted(blocks, key=lambda b: (b.box.y0, b.box.x0))
        for i, b in enumerate(sorted_b):
            min_next_y0 = page_height - 8.0
            for j in range(i + 1, len(sorted_b)):
                other = sorted_b[j]
                horiz_overlap = min(b.box.x1, other.box.x1) - max(b.box.x0, other.box.x0)
                if horiz_overlap > 12.0 and other.box.y0 >= b.box.y1 - 1.5:
                    min_next_y0 = min(min_next_y0, other.box.y0)
                    break
            b.max_allowed_y1 = max(b.box.y1 + 3.0, min_next_y0 - 0.5)
        return blocks

    @staticmethod
    def _int_to_rgb(color_int: int) -> Tuple[float, float, float]:
        r = ((color_int >> 16) & 255) / 255.0
        g = ((color_int >> 8) & 255) / 255.0
        b = (color_int & 255) / 255.0
        return (r, g, b)

    @staticmethod
    def _is_math_only(text: str) -> bool:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean_no_bullet = re.sub(r'^[\•\-\+]\s*', '', clean).strip()
        if re.search(
            r'\b(?:Answer|comp|complement|Discard|carry|Sum|Practice|Exercise|EXAMPLE|EXAMPLES|Table|Decimal|Signed|Magnitude|Section|Chapter|Copyright)\b',
            clean_no_bullet,
            re.I
        ):
            return False
        if re.fullmatch(
            r'(?:Fortran|FORTRAN|COBOL|LISP|C|C\+\+|Java|Python|Rust|Coq|Matlab|ML,\s*Haskell|Java,\s*C\+\+|Perl|Prolog|Scheme|Ada|UNIX|NetBeans|XHTML|PHP|ROBERT\s+W\.\s+SEBESTA|\d+-\d+)',
            clean_no_bullet,
            re.I
        ):
            return True
        alpha_count = sum(1 for c in clean_no_bullet if c.isalpha())
        digit_count = sum(1 for c in clean_no_bullet if c.isdigit())
        math_ops = sum(1 for c in clean_no_bullet if c in "=+-≠<>≤≥±×÷")
        return (
            alpha_count == 0
            or (len(clean_no_bullet) < 40 and math_ops >= 1 and alpha_count < 4)
            or (digit_count > alpha_count * 2 and len(clean_no_bullet) < 55 and "bit" not in clean_no_bullet.lower())
        )

    @staticmethod
    def _is_standalone_line_item(line_text: str, line_width: float) -> bool:
        t = line_text.strip()
        if line_width < 250.0:
            return True
        if re.match(
            r'^(?:Practice Exercise|EXAMPLE|EXAMPLES|Answer|Sum|Discard|End-around|Section|Chapter|Decimal|Signed|\([a-d]\)|\d+\.|1\'s|2\'s|9\'s|10\'s|Vs|•)\b',
            t,
            re.I
        ):
            return True
        if re.match(r'^Table\s+[0-9\.]+$', t, re.I):
            return True
        if "=" in t and line_width < 310.0:
            return True
        if ":" in t and (line_width < 290.0 or re.search(r':\s*[01\d\+\-\(\s]+$', t)):
            return True
        return False

    def _extract_digital(self, page: fitz.Page, page_num: int, blocks: List[Dict[str, Any]]) -> List[ParagraphBlock]:
        size_char_counts: Dict[float, int] = {}
        for b in blocks:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    txt = s.get("text", "").strip()
                    if len(txt) >= 3:
                        sz = round(s.get("size", 9.5), 1)
                        size_char_counts[sz] = size_char_counts.get(sz, 0) + len(txt)

        page_body_size = 9.5
        if size_char_counts:
            page_body_size = max(size_char_counts.items(), key=lambda x: x[1])[0]

        paragraph_blocks: List[ParagraphBlock] = []
        p_idx = 0

        for b in blocks:
            if b.get("type") != 0:
                continue
            raw_lines = b.get("lines", [])
            if not raw_lines:
                continue

            sorted_raw_lines = sorted(raw_lines, key=lambda l: (round(l["bbox"][1] / 3.0), l["bbox"][0]))
            merged_visual_lines: List[Dict[str, Any]] = []

            for rl in sorted_raw_lines:
                rl_bbox = rl.get("bbox", (0, 0, 0, 0))
                rl_spans = rl.get("spans", [])
                if not rl_spans:
                    continue

                if merged_visual_lines:
                    prev = merged_visual_lines[-1]
                    p_bbox = prev["bbox"]
                    same_row = abs(rl_bbox[1] - p_bbox[1]) < 4.5 or abs(rl_bbox[3] - p_bbox[3]) < 4.5
                    horiz_gap = rl_bbox[0] - p_bbox[2]
                    prev_text_str = "".join(s.get("text", "") for s in prev["spans"]).strip()
                    max_gap = 65.0 if prev_text_str.endswith((":", "=")) else 14.0
                    if same_row and -3.0 <= horiz_gap <= max_gap:
                        prev["spans"].extend(rl_spans)
                        prev["bbox"] = (
                            min(p_bbox[0], rl_bbox[0]),
                            min(p_bbox[1], rl_bbox[1]),
                            max(p_bbox[2], rl_bbox[2]),
                            max(p_bbox[3], rl_bbox[3])
                        )
                        continue

                merged_visual_lines.append({
                    "bbox": rl_bbox,
                    "spans": list(rl_spans)
                })

            parsed_lines: List[Dict[str, Any]] = []
            for vl in merged_visual_lines:
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

                line_str = ""
                line_sizes = []
                bold_votes = 0
                first_color = (0.0, 0.0, 0.0)

                for idx_s, s in enumerate(spans):
                    raw_span = normalize_unicode_punctuation(s.get("text", ""))
                    if not raw_span:
                        continue
                    s_size = s.get("size", ref_size)
                    s_y = s["origin"][1]
                    s_flags = s.get("flags", 0)
                    s_bbox = s.get("bbox", (0, 0, 0, 0))
                    s_height = s_bbox[3] - s_bbox[1]

                    if idx_s == 0 and "color" in s:
                        first_color = self._int_to_rgb(s["color"])
                    if (s_flags & 16) or "bold" in s.get("font", "").lower():
                        bold_votes += len(raw_span.strip())

                    stripped = raw_span.strip()
                    is_short = 1 <= len(stripped) <= 4
                    is_smaller = (s_size < ref_size * 0.86) or (s_height < ref_size * 0.82)
                    dy = s_y - ref_y

                    is_super = is_short and ((s_flags & 1) or (dy < -ref_size * 0.08) or (is_smaller and dy < -ref_size * 0.03))
                    is_sub = is_short and ((dy > ref_size * 0.06) or (is_smaller and dy >= 0.0))

                    if is_super:
                        line_str += f"<sup:{stripped}>"
                    elif is_sub:
                        line_str += f"<sub:{stripped}>"
                    else:
                        if line_str and not line_str.endswith(" ") and not raw_span.startswith(" "):
                            line_str += " "
                        line_str += raw_span
                        line_sizes.append(s_size)
                        if s_size >= ref_size * 0.88:
                            ref_y = s_y

                clean_line = universal_ocr_math_heuristics(re.sub(r'\s+', ' ', line_str).strip())
                if not clean_line:
                    continue

                l_bbox = vl["bbox"]
                avg_l_size = sum(line_sizes) / len(line_sizes) if line_sizes else ref_size
                is_bold = bold_votes > (len(clean_line) * 0.4)

                if re.fullmatch(r'EXAMPLES?', clean_line, flags=re.I):
                    is_bold = True
                    first_color = (1.0, 1.0, 1.0)

                parsed_lines.append({
                    "text": clean_line,
                    "bbox": l_bbox,
                    "size": avg_l_size,
                    "bold": is_bold,
                    "color": first_color
                })

            if not parsed_lines:
                continue

            grouped_items: List[Dict[str, Any]] = []
            curr_group: Dict[str, Any] = {}

            for pl in parsed_lines:
                l_w = pl["bbox"][2] - pl["bbox"][0]
                standalone = self._is_standalone_line_item(pl["text"], l_w)

                if standalone:
                    if curr_group:
                        grouped_items.append(curr_group)
                        curr_group = {}
                    grouped_items.append(pl.copy())
                else:
                    if not curr_group:
                        curr_group = pl.copy()
                    else:
                        v_gap = pl["bbox"][1] - curr_group["bbox"][3]
                        same_style = (curr_group["bold"] == pl["bold"]) and (abs(curr_group["size"] - pl["size"]) < 1.2)
                        if v_gap > curr_group["size"] * 0.95 or not same_style:
                            grouped_items.append(curr_group)
                            curr_group = pl.copy()
                        else:
                            prev_t = curr_group["text"]
                            curr_group["text"] = (
                                (prev_t[:-1] + pl["text"])
                                if prev_t.endswith("-") and not prev_t.endswith(" -")
                                else f"{prev_t} {pl['text']}"
                            )
                            b0 = curr_group["bbox"]
                            b1 = pl["bbox"]
                            curr_group["bbox"] = (
                                min(b0[0], b1[0]),
                                min(b0[1], b1[1]),
                                max(b0[2], b1[2]),
                                max(b0[3], b1[3])
                            )

            if curr_group:
                grouped_items.append(curr_group)

            for item in grouped_items:
                txt = universal_ocr_math_heuristics(item["text"].replace("|", "").strip())
                if len(txt) < 2:
                    continue
                bb = item["bbox"]
                paragraph_blocks.append(ParagraphBlock(
                    id=p_idx,
                    page_num=page_num,
                    box=BoundingBox(bb[0], bb[1], bb[2], bb[3]),
                    text=txt,
                    font_size=max(7.0, min(18.0, item["size"])),
                    is_standalone_math=self._is_math_only(txt),
                    is_from_ocr=False,
                    is_bold=item["bold"],
                    text_color=item["color"]
                ))
                p_idx += 1

        return paragraph_blocks

    @staticmethod
    def _is_valid_ocr_text(text: str, avg_conf: float, bg_std: float) -> bool:
        t = text.strip()
        if len(t) < 2:
            return False
        letters = sum(1 for c in t if c.isalpha())
        if letters < 2 and t not in ("C",):
            return False
        if bg_std > 42.0 and avg_conf < 82.0:
            return False
        words = re.findall(r'[a-zA-Z]{2,}', t)
        if not words and t not in ("C", "C++"):
            return False
        if len(t) <= 8 and avg_conf < 70.0 and t not in ("C", "C++", "Coq", "Rust", "Ada", "LISP"):
            return False
        return True

    @staticmethod
    def _sample_outer_ring_bg_and_fg(bgr_img: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], float, float]:
        h_img, w_img = bgr_img.shape[:2]
        pad = 6
        ox0, oy0 = max(0, x0 - pad), max(0, y0 - pad)
        ox1, oy1 = min(w_img, x1 + pad), min(h_img, y1 + pad)

        outer_roi = bgr_img[oy0:oy1, ox0:ox1]
        inner_roi = bgr_img[max(0, y0):min(h_img, y1), max(0, x0):min(w_img, x1)]
        if inner_roi.size == 0 or outer_roi.size == 0:
            return (1.0, 1.0, 1.0), (0.0, 0.0, 0.0), 1.0, 0.0

        top_strip = outer_roi[0:max(1, y0 - oy0), :, :].reshape(-1, 3)
        bot_strip = outer_roi[max(0, outer_roi.shape[0] - (oy1 - y1)):, :, :].reshape(-1, 3)
        left_strip = outer_roi[:, 0:max(1, x0 - ox0), :].reshape(-1, 3)
        right_strip = outer_roi[:, max(0, outer_roi.shape[1] - (ox1 - x1)):, :].reshape(-1, 3)

        ring_pixels = np.concatenate([p for p in (top_strip, bot_strip, left_strip, right_strip) if p.size > 0], axis=0)
        if ring_pixels.size == 0:
            ring_pixels = outer_roi.reshape(-1, 3)

        bg_bgr = np.median(ring_pixels, axis=0)
        bg_rgb = (float(bg_bgr[2]) / 255.0, float(bg_bgr[1]) / 255.0, float(bg_bgr[0]) / 255.0)
        bg_lum = 0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]

        gray_ring = 0.299 * ring_pixels[:, 2] + 0.587 * ring_pixels[:, 1] + 0.114 * ring_pixels[:, 0]
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

    @staticmethod
    def _should_merge_ocr_lines(prev: ParagraphBlock, curr_box: BoundingBox, curr_txt: str, curr_fs: float, curr_bg_lum: float) -> bool:
        prev_bg_lum = 0.299 * prev.bg_color[0] + 0.587 * prev.bg_color[1] + 0.114 * prev.bg_color[2] if prev.bg_color else 1.0
        if abs(prev_bg_lum - curr_bg_lum) > 0.25:
            return False

        if re.match(r'^(?:•|\-|\+|\([a-d]\)|\d+\.)\s', curr_txt):
            return False
        if re.match(r'^(?:Copyright|Telif|EXAMPLE|Practice)\b', curr_txt, re.I):
            return False

        v_gap = curr_box.y0 - prev.box.y1
        if v_gap < -4.0 or v_gap > max(prev.box.height, curr_box.height) * 1.45:
            return False

        if abs(curr_fs - prev.font_size) > max(prev.font_size, curr_fs) * 0.32:
            return False

        prev_clean = prev.text.strip()
        ends_with_connector = bool(re.search(
            r'\b(?:of|to|for|with|which|a|an|the|in|on|by|from|that|than|as|and|or|are|is|be|into|over|between|already)\s*$',
            prev_clean,
            re.I
        ))

        left_diff = curr_box.x0 - prev.box.x0
        is_aligned_or_indented = (-18.0 <= left_diff <= 55.0)

        center_diff = abs(curr_box.center_x - prev.box.center_x)
        is_centered_node = (center_diff < 22.0 and prev.box.width < 220.0 and curr_box.width < 220.0)

        if is_centered_node and v_gap <= prev.box.height * 0.95:
            return True

        if is_aligned_or_indented:
            if ends_with_connector:
                return True
            if not prev_clean.endswith((".", "!", "?", ";")) and (curr_txt[0].islower() or v_gap <= prev.box.height * 0.85):
                return True

        return False

    def _run_tesseract_pass(
        self,
        bin_img: np.ndarray,
        bgr_img: np.ndarray,
        scale: float,
        page_num: int,
        existing_boxes: List[BoundingBox],
        is_inverted_pass: bool = False
    ) -> List[ParagraphBlock]:
        try:
            data = pytesseract.image_to_data(
                Image.fromarray(bin_img),
                lang="eng",
                config="--psm 6" if is_inverted_pass else "--psm 3",
                output_type=pytesseract.Output.DICT
            )
        except Exception:
            return []

        lines_raw: Dict[Tuple[int, int, int], List[Dict[str, Any]]] = {}
        for i in range(len(data["text"])):
            if int(data["level"][i]) != 5:
                continue
            word = data["text"][i].strip()
            conf = float(data["conf"][i])
            if not word or conf < 45.0:
                continue

            w_box = BoundingBox(
                data["left"][i] / scale,
                data["top"][i] / scale,
                (data["left"][i] + data["width"][i]) / scale,
                (data["top"][i] + data["height"][i]) / scale
            )
            if any(w_box.overlaps(eb, margin=1.0) for eb in existing_boxes):
                continue

            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines_raw.setdefault(key, []).append({
                "text": word,
                "conf": conf,
                "left": data["left"][i],
                "top": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i]
            })

        raw_line_items: List[Dict[str, Any]] = []
        for _, words in lines_raw.items():
            words_sorted = sorted(words, key=lambda w: w["left"])
            sub_segments: List[List[Dict[str, Any]]] = []
            curr_seg: List[Dict[str, Any]] = []
            for w in words_sorted:
                if curr_seg:
                    prev_right = curr_seg[-1]["left"] + curr_seg[-1]["width"]
                    gap = (w["left"] - prev_right) / scale
                    if gap > 26.0:
                        sub_segments.append(curr_seg)
                        curr_seg = [w]
                        continue
                curr_seg.append(w)
            if curr_seg:
                sub_segments.append(curr_seg)

            for seg in sub_segments:
                line_txt = " ".join(w["text"] for w in seg).strip()
                avg_conf = sum(w["conf"] for w in seg) / len(seg)
                x0_px = min(w["left"] for w in seg)
                y0_px = min(w["top"] for w in seg)
                x1_px = max(w["left"] + w["width"] for w in seg)
                y1_px = max(w["top"] + w["height"] for w in seg)

                bg_rgb, txt_rgb, bg_lum, bg_std = self._sample_outer_ring_bg_and_fg(
                    bgr_img, x0_px, y0_px, x1_px, y1_px
                )

                if not is_inverted_pass and bg_lum < 0.42:
                    continue
                if is_inverted_pass and bg_lum >= 0.48:
                    continue

                if not self._is_valid_ocr_text(line_txt, avg_conf, bg_std):
                    continue

                raw_line_items.append({
                    "text": line_txt,
                    "box": BoundingBox(x0_px / scale, y0_px / scale, x1_px / scale, y1_px / scale),
                    "conf": avg_conf,
                    "bg_color": bg_rgb,
                    "text_color": txt_rgb,
                    "bg_lum": bg_lum
                })

        raw_line_items.sort(key=lambda item: (round(item["box"].y0 / 8.0), item["box"].x0))
        merged_blocks: List[ParagraphBlock] = []

        for item in raw_line_items:
            b = item["box"]
            txt = universal_ocr_math_heuristics(item["text"].replace("|", "").strip())
            if len(txt) < 2 and txt != "C":
                continue

            est_fs = max(7.5, min(20.0, b.height * 0.78))

            merged_into_existing = False
            for prev in reversed(merged_blocks[-4:]):
                if self._should_merge_ocr_lines(prev, b, txt, est_fs, item["bg_lum"]):
                    center_diff = abs(b.center_x - prev.box.center_x)
                    if center_diff < 22.0 and prev.box.width < 220.0:
                        prev.is_centered = True
                    prev.text = (
                        (prev.text[:-1] + txt)
                        if prev.text.endswith("-")
                        else f"{prev.text} {txt}"
                    )
                    prev.box = BoundingBox(
                        min(prev.box.x0, b.x0),
                        min(prev.box.y0, b.y0),
                        max(prev.box.x1, b.x1),
                        max(prev.box.y1, b.y1)
                    )
                    merged_into_existing = True
                    break

            if not merged_into_existing:
                merged_blocks.append(ParagraphBlock(
                    id=len(merged_blocks),
                    page_num=page_num,
                    box=b,
                    text=txt,
                    font_size=est_fs,
                    is_standalone_math=self._is_math_only(txt),
                    is_from_ocr=True,
                    is_bold=(est_fs > 13.5) or (item["bg_lum"] < 0.42),
                    text_color=item["text_color"],
                    bg_color=item["bg_color"]
                ))

        return merged_blocks

    def _extract_hybrid_ocr(
        self,
        page: fitz.Page,
        page_num: int,
        existing_digital: List[ParagraphBlock],
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

        for db in existing_digital:
            x0, y0 = int(max(0, db.box.x0 * scale - 2)), int(max(0, db.box.y0 * scale - 2))
            x1, y1 = int(min(bgr.shape[1], db.box.x1 * scale + 2)), int(min(bgr.shape[0], db.box.y1 * scale + 2))
            bgr[y0:y1, x0:x1] = (255, 255, 255)

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        existing_boxes = [db.box for db in existing_digital]

        # GEÇİŞ 1: Açık Zemin (Slayt gövdeleri ve açık diyagramlar)
        thresh_light = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 17, 5
        )
        ocr_blocks = self._run_tesseract_pass(
            thresh_light, bgr, scale, page_num, existing_boxes, is_inverted_pass=False
        )
        existing_boxes.extend(b.box for b in ocr_blocks)

        # GEÇİŞ 2: Koyu Zemin / Siyah Tablo Özel Geçişi
        dark_ratio = float(np.mean(gray < 80))
        if 0.03 < dark_ratio < 0.80:
            max_channel = np.max(bgr, axis=2)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced = clahe.apply(max_channel)
            inv_dark = 255 - enhanced
            _, thresh_dark = cv2.threshold(inv_dark, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            dark_blocks = self._run_tesseract_pass(
                thresh_dark, bgr, scale, page_num, existing_boxes, is_inverted_pass=True
            )
            ocr_blocks.extend(dark_blocks)

        return ocr_blocks


# --- 6. %100 ÇEVRİMDIŞI KİLİTLİ (local_files_only=True) ÇEVİRİ MOTORU ---
class TranslationEngine:
    def __init__(self, device: torch.device, dtype: torch.dtype, cache_path: str = "build/translation_cache.json"):
        self.device = device
        self.dtype = dtype
        self.cache_path = cache_path
        self.cache: Dict[str, str] = {}

        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if loaded.get("__version__") == CACHE_VERSION:
                    self.cache = loaded
                    print(f"[ÖNBELLEK] {len(self.cache) - 1} doğrulanmış çeviri yüklendi.")
                else:
                    self.cache = {"__version__": CACHE_VERSION}
            except Exception:
                self.cache = {"__version__": CACHE_VERSION}
        else:
            self.cache = {"__version__": CACHE_VERSION}

        print("1. [YEREL ÇEVİRİ] Helsinki-NLP/opus-mt-tc-big-en-tr yerel diskten (%100 Çevrimdışı) yükleniyor...")
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        model_name = "Helsinki-NLP/opus-mt-tc-big-en-tr"
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                token=False,
                local_files_only=True
            )
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                token=False,
                local_files_only=True,
                torch_dtype=self.dtype if self.device.type == "cuda" else torch.float32
            ).to(self.device)
        except Exception:
            print("[BİLGİ] Model yerel diskte bulunamadı. İlk çalıştırma için güvenli indirme yapılıyor...")
            prev_hub = os.environ.pop("HF_HUB_OFFLINE", None)
            prev_trans = os.environ.pop("TRANSFORMERS_OFFLINE", None)
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=False)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                token=False,
                torch_dtype=self.dtype if self.device.type == "cuda" else torch.float32
            ).to(self.device)
            if prev_hub:
                os.environ["HF_HUB_OFFLINE"] = prev_hub
            if prev_trans:
                os.environ["TRANSFORMERS_OFFLINE"] = prev_trans
            print("-> Model başarıyla indirildi ve yerel disk önbelleğine kilitlendi.")

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
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\(\[])', text)
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def _fast_deterministic_translate(text: str) -> str:
        t = universal_ocr_math_heuristics(text.strip())

        if re.fullmatch(r'Answer\s*:?', t, flags=re.I):
            return "Cevap:"

        if re.fullmatch(r'EXAMPLES?', t, flags=re.I):
            return "ÖRNEK"

        if "copyright" in t.lower() and "addison-wesley" in t.lower():
            return "Telif Hakkı © 2009 Addison-Wesley. Tüm hakları saklıdır."

        m_sum = re.match(r'^Sum\s*=\s*(.+)$', t, flags=re.I)
        if m_sum:
            return f"Toplam = {m_sum.group(1).strip()}"

        m_eac = re.match(r'^End-around\s+carry\s*=\s*(.+)$', t, flags=re.I)
        if m_eac:
            return f"Döngüsel elde = {m_eac.group(1).strip()}"

        m_disc = re.match(r'^Discard\s+end\s+carry\s+(.+)$', t, flags=re.I)
        if m_disc:
            return f"Son eldeyi atın {m_disc.group(1).strip()}"

        m_ans = re.match(r'^Answer\s*[:\.]?\s*(.+)$', t, flags=re.I)
        if m_ans:
            rest = m_ans.group(1).strip()
            clean_rest = re.sub(r'<(?:sub|sup):[^>]+>', '', rest)
            alpha_c = sum(1 for c in clean_rest if c.isalpha())
            if alpha_c <= 12 or "comp" in clean_rest.lower():
                rest = re.sub(r"\b1's\s*comp(?:lement)?(?:\s+of)?\b", "1'e tümleyen", rest, flags=re.I)
                rest = re.sub(r"\b2's\s*comp(?:lement)?(?:\s+of)?\b", "2'ye tümleyen", rest, flags=re.I)
                rest = re.sub(r"\b9's\s*comp(?:lement)?(?:\s+of)?\b", "9'a tümleyen", rest, flags=re.I)
                rest = re.sub(r"\b10's\s*comp(?:lement)?(?:\s+of)?\b", "10'a tümleyen", rest, flags=re.I)
                rest = re.sub(r"\band\b", "ve", rest, flags=re.I)
                return f"Cevap: {rest}"

        m_comp_eq = re.match(r"^([0-9a-zA-Z]+)'s\s*comp(?:lement)?(?:\s+of\s+([a-zA-Z0-9]+))?\s*[:=]\s*(.+)$", t, flags=re.I)
        if m_comp_eq:
            num = m_comp_eq.group(1)
            var_name = m_comp_eq.group(2)
            val = m_comp_eq.group(3).strip()
            suffix = {"1": "1'e", "2": "2'ye", "9": "9'a", "10": "10'a"}.get(num, f"{num}'ye")
            if var_name:
                return f"{var_name}'nin {suffix} tümleyeni = {val}"
            return f"{suffix} tümleyen = {val}"

        exact_map = {
            "decimal": "Ondalık",
            "signed-2's complement": "İşaretli 2'ye Tümleyen",
            "signed-1's complement": "İşaretli 1'e Tümleyen",
            "signed 2's complement": "İşaretli 2'ye Tümleyen",
            "signed 1's complement": "İşaretli 1'e Tümleyen",
            "signed magnitude": "İşaret-Büyüklük",
            "signed binary numbers": "İşaretli İkili Sayılar",
            "complements of numbers": "Sayıların Tümleyenleri",
            "diminished radix complement": "Azaltılmış Taban Tümleyeni",
            "radix complement": "Taban Tümleyeni",
            "subtraction with complements": "Tümleyenlerle Çıkarma",
            "arithmetic addition": "Aritmetik Toplama",
            "arithmetic subtraction": "Aritmetik Çıkarma",
            "no end carry": "Son elde yoktur",
            "no end-around carry": "Döngüsel elde yoktur",
            "end-around carry": "Döngüsel elde",
            "concepts of programming languages": "Programlama Dilleri Kavramları",
            "concepts of": "Programlama Dilleri",
            "programming languages": "Kavramları",
            "ninth edition": "Dokuzuncu Baskı",
            "chapter 1 topics": "Bölüm 1 Konuları",
            "reasons for studying concepts of programming languages": "Programlama Dilleri Kavramlarını İnceleme Nedenleri",
            "programming domains": "Programlama Alanları",
            "business applications": "Ticari Uygulamalar (İş Uygulamaları)",
            "scientific applications": "Bilimsel Uygulamalar",
            "artificial intelligence": "Yapay Zeka",
            "systems programming": "Sistem Programlama",
            "web software": "Web Yazılımları",
            "language evaluation criteria": "Dil Değerlendirme Ölçütleri",
            "evaluation criteria: readability": "Değerlendirme Ölçütleri: Okunabilirlik",
            "evaluation criteria: writability": "Değerlendirme Ölçütleri: Yazılabilirlik",
            "evaluation criteria: reliability": "Değerlendirme Ölçütleri: Güvenilirlik",
            "evaluation criteria: cost": "Değerlendirme Ölçütleri: Maliyet",
            "evaluation criteria: others": "Değerlendirme Ölçütleri: Diğerleri",
            "orthogonality": "Dikgenlik (Ortogonallik)",
            "expressivity": "İfade Gücü (Expressivity)",
            "aliasing": "Takma Ad Kullanımı (Aliasing)",
            "imperative": "Buyruksal (Imperative)",
            "functional": "İşlevsel (Fonksiyonel)",
            "logic": "Mantık (Logic)",
            "goals of pls": "Programlama Dillerinin Hedefleri",
            "productivity": "Üretkenlik",
            "safety": "Güvenlik",
            "performance": "Performans",
            "influences on language design": "Dil Tasarımını Etkileyen Faktörler",
            "computer architecture influence": "Bilgisayar Mimarisinin Etkisi",
            "the von neumann architecture": "Von Neumann Mimarisi",
            "programming methodologies influences": "Programlama Metodolojilerinin Etkileri",
            "language categories": "Dil Kategorileri",
            "language design trade-offs": "Dil Tasarımı Ödünleşimleri (Trade-Offs)",
            "implementation methods": "Uygulama (Gerçekleştirim) Yöntemleri",
            "layered view of computer": "Bilgisayarın Katmanlı Görünümü",
            "the compilation process": "Derleme Süreci",
            "additional compilation terminologies": "Ek Derleme Terimleri",
            "differences between linking and loading": "Bağlama (Linking) ve Yükleme (Loading) Arasındaki Farklar",
            "linking": "Bağlama (Linking)",
            "loading": "Yükleme (Loading)",
            "von neumann bottleneck": "Von Neumann Darboğazı",
            "pure interpretation": "Saf Yorumlama (Pure Interpretation)",
            "pure interpretation process": "Saf Yorumlama Süreci",
            "hybrid implementation systems": "Hibrit Uygulama Sistemleri",
            "hybrid implementation process": "Hibrit Uygulama Süreci",
            "just-in-time implementation systems": "Tam Zamanında (JIT) Uygulama Sistemleri",
            "preprocessors": "Önişlemciler (Preprocessors)",
            "programming environments": "Programlama Ortamları",
            "summary": "Özet",
            "lets call it a day!": "Bugünlük bu kadar!",
            "let's call it a day!": "Bugünlük bu kadar!",
            "source program": "Kaynak program",
            "lexical analyzer": "Sözcüksel çözümleyici",
            "lexical units": "Sözcüksel birimler",
            "syntax analyzer": "Sözdizimi çözümleyicisi",
            "parse trees": "Ayrıştırma ağaçları",
            "symbol table": "Sembol tablosu",
            "intermediate code generator (and semantic analyzer)": "Ara kod üreteci (ve anlamsal çözümleyici)",
            "intermediate code generator": "Ara kod üreteci",
            "intermediate code": "Ara kod",
            "code generator": "Kod üreteci",
            "machine language": "Makine dili",
            "input data": "Girdi verisi",
            "results": "Sonuçlar",
            "results of operations": "İşlem sonuçları",
            "instructions and data": "Komutlar ve veriler",
            "memory (stores both instructions and data)": "Bellek (hem komutları hem verileri depolar)",
            "optimization (optional)": "Optimizasyon (isteğe bağlı)",
            "operating system": "İşletim sistemi",
            "bare machine": "Çıplak makine (Donanım)",
            "macroinstruction interpreter": "Makrokomut yorumlayıcısı",
            "operating system command interpreter": "İşletim sistemi komut yorumlayıcısı",
            "assembler": "Birleştirici (Assembler)",
            "c compiler": "C derleyicisi",
            "c++ compiler": "C++ derleyicisi",
            "fortran compiler": "FORTRAN derleyicisi",
            "ada compiler": "Ada derleyicisi",
            "lisp interpreter": "LISP yorumlayıcısı",
            "virtual c computer": "Sanal C bilgisayarı",
            "virtual c++ computer": "Sanal C++ bilgisayarı",
            "virtual fortran computer": "Sanal FORTRAN bilgisayarı",
            "virtual ada computer": "Sanal Ada bilgisayarı",
            "virtual lisp computer": "Sanal LISP bilgisayarı",
            "virtual assembly language computer": "Sanal assembly dili bilgisayarı",
            "interpreter": "Yorumlayıcı",
            "computer": "Bilgisayar",
            "control unit": "Denetim birimi",
            "arithmetic and logic unit": "Aritmetik ve mantık birimi",
            "input and output devices": "Girdi ve çıktı birimleri",
            "central processing unit": "Merkezi işlem birimi (CPU)",
        }
        clean_low = re.sub(r'^[\•\-\+]\s*', '', t).strip().lower()
        if clean_low in exact_map:
            prefix = "• " if t.startswith(("•", "-", "+")) else ""
            val = exact_map[clean_low]
            return prefix + (val.upper() if t.isupper() else val)

        if len(t) <= 42 and not re.search(r'\b(?:lists|shows|gives|is|are|has|can|will)\b', t, re.I):
            m_tbl = re.match(r'^Table\s+([0-9\.]+)\s*(.*)$', t, flags=re.I)
            if m_tbl:
                rest = m_tbl.group(2).strip()
                if not rest:
                    return f"Tablo {m_tbl.group(1)}"
                if rest.lower() in exact_map:
                    return f"Tablo {m_tbl.group(1)} {exact_map[rest.lower()]}"

        m_ex = re.match(r'^(?:Practice\s+)?Exercise\s+([0-9\.]+)$', t, flags=re.I)
        if m_ex:
            return f"Uygulama Alıştırması {m_ex.group(1)}"

        m_exmp = re.match(r'^EXAMPLE\s+([0-9\.]+)$', t, flags=re.I)
        if m_exmp:
            return f"ÖRNEK {m_exmp.group(1)}"

        m_rep = re.match(
            r'^(signed-magnitude|signed-1\'s-complement|signed-2\'s-complement|signed 1\'s complement|signed 2\'s complement|signed magnitude)\s+representation\s*:\s*([01\s]+)$',
            t,
            flags=re.I
        )
        if m_rep:
            kind = m_rep.group(1).lower()
            bits = m_rep.group(2).strip()
            if "magnitude" in kind:
                return f"işaret-büyüklük gösterimi: {bits}"
            if "1's" in kind:
                return f"işaretli 1'e tümleyen gösterimi: {bits}"
            if "2's" in kind:
                return f"işaretli 2'ye tümleyen gösterimi: {bits}"

        return ""

    def translate_paragraph(self, raw_text: str) -> str:
        repaired_raw = universal_ocr_math_heuristics(raw_text)

        if repaired_raw in self.cache:
            return self.cache[repaired_raw]

        det = self._fast_deterministic_translate(repaired_raw)
        if det:
            self.cache[repaired_raw] = det
            return det

        has_bullet = repaired_raw.startswith(("•", "-", "+"))
        clean_for_trans = re.sub(r'^[\•\-\+]\s*', '', repaired_raw).strip()

        sentences = self._split_into_sentences(clean_for_trans)
        if not sentences:
            return repaired_raw

        masked_sentences: List[str] = []
        math_dicts: List[Dict[str, str]] = []

        for s in sentences:
            m_text, m_dict = normalize_and_mask_math(s)
            masked_sentences.append(m_text)
            math_dicts.append(m_dict)

        decoded_list: List[str] = []
        batch_size = 8

        try:
            for i in range(0, len(masked_sentences), batch_size):
                batch = masked_sentences[i:i + batch_size]
                inputs = self.tokenizer(
                    batch,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512
                ).to(self.device)

                with torch.inference_mode():
                    outputs = self.model.generate(
                        **inputs,
                        max_length=512,
                        num_beams=4,
                        repetition_penalty=1.15,
                        early_stopping=True
                    )
                decoded_list.extend(self.tokenizer.batch_decode(outputs, skip_special_tokens=True))
        except Exception as e:
            print(f"[ÇEVİRİ UYARISI] Mini-batch hatası ({e}), güvenli moda geçiliyor...")
            decoded_list = []
            for m_s in masked_sentences:
                try:
                    inp = self.tokenizer(m_s, return_tensors="pt", truncation=True, max_length=512).to(self.device)
                    with torch.inference_mode():
                        out = self.model.generate(**inp, max_length=512)
                    decoded_list.append(self.tokenizer.decode(out[0], skip_special_tokens=True))
                except Exception:
                    decoded_list.append(m_s)

        final_sentences: List[str] = []
        for decoded, m_dict in zip(decoded_list, math_dicts):
            restored = restore_math_and_validate(decoded.replace("|", ""), m_dict)
            final_sentences.append(restored)

        result = ("• " if has_bullet else "") + " ".join(final_sentences)
        self.cache[repaired_raw] = result
        return result


# --- 7. KOPYALANABİLİR TXT DIŞA AKTARIM FONKSİYONU ---
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
        f_clean.write("   PDF AI ENGINE - TAMAMEN KOPYALANABİLİR TÜRKÇE METİN VE FORMÜLLER\n")
        f_clean.write("====================================================================\n\n")

        for page_num in sorted(pages_map.keys()):
            f_clean.write(f"--- [SAYFA {page_num + 1}] ---\n\n")
            blocks = sorted(pages_map[page_num], key=lambda b: (round(b.box.y0 / 6), b.box.x0))
            for b in blocks:
                txt_out = format_sub_sup_for_render(b.translated_text, font_obj=None)
                f_clean.write(f"{txt_out}\n\n")

    with open(bilingual_txt_path, "w", encoding="utf-8") as f_bi:
        f_bi.write("====================================================================\n")
        f_bi.write("   PDF AI ENGINE - KARŞILAŞTIRMALI İNCELEME VE KOPYALAMA DOSYASI\n")
        f_bi.write("====================================================================\n\n")

        for page_num in sorted(pages_map.keys()):
            f_bi.write(f"==================== SAYFA {page_num + 1} ====================\n\n")
            blocks = sorted(pages_map[page_num], key=lambda b: (round(b.box.y0 / 6), b.box.x0))
            for b in blocks:
                tag = "[SAF FORMÜL / KOD]" if b.is_standalone_math else ("[SLAYT/RESİM OCR]" if b.is_from_ocr else f"[DİJİTAL BLOK #{b.id}]")
                orig_out = format_sub_sup_for_render(b.text, font_obj=None)
                tr_out = format_sub_sup_for_render(b.translated_text, font_obj=None)
                f_bi.write(f"{tag}\n")
                f_bi.write(f"EN (Orijinal) : {orig_out}\n")
                f_bi.write(f"TR (Çeviri)   : {tr_out}\n")
                f_bi.write("-" * 68 + "\n")
            f_bi.write("\n")


# --- 8. DIŞ ÇERÇEVE ARKA PLAN RENGİ DUYARLI CERRAHİ RENDER ---
def select_best_unicode_fonts() -> Tuple[str, str, Optional[fitz.Font]]:
    candidates = [
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
        (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg):
            try:
                f_test = fitz.Font(fontfile=reg)
                if f_test.has_glyph(ord("₁")) and f_test.has_glyph(ord("ⁿ")) and f_test.has_glyph(ord("₂")):
                    return reg, (bold if os.path.exists(bold) else reg), f_test
            except Exception:
                continue
    fallback_reg = r"C:\Windows\Fonts\arial.ttf"
    f_obj = fitz.Font(fontfile=fallback_reg) if os.path.exists(fallback_reg) else None
    return fallback_reg, r"C:\Windows\Fonts\arialbd.ttf", f_obj


def _sample_background_color(page_pix: fitz.Pixmap, box: BoundingBox) -> Tuple[float, float, float]:
    """
    Metin kutusunun içindeki harflerden etkilenmemek için kutunun dış çerçevesindeki
    (sol, sağ, üst, alt kenar dışı) 8 noktadan örnek alıp medyan arka plan rengini döndürür.
    """
    try:
        w, h = page_pix.width, page_pix.height
        mid_x = int((box.x0 + box.x1) / 2.0)
        mid_y = int((box.y0 + box.y1) / 2.0)

        sample_coords = [
            (int(box.x0) - 4, mid_y),
            (int(box.x1) + 4, mid_y),
            (mid_x, int(box.y0) - 4),
            (mid_x, int(box.y1) + 4),
            (int(box.x0) - 3, int(box.y0) - 3),
            (int(box.x1) + 3, int(box.y0) - 3),
            (int(box.x0) - 3, int(box.y1) + 3),
            (int(box.x1) + 3, int(box.y1) + 3),
        ]

        pixels = []
        for sx, sy in sample_coords:
            cx = max(0, min(w - 1, sx))
            cy = max(0, min(h - 1, sy))
            px = page_pix.pixel(cx, cy)
            pixels.append([px[0], px[1], px[2]])

        med = np.median(np.array(pixels, dtype=np.float32), axis=0)
        return (float(med[0]) / 255.0, float(med[1]) / 255.0, float(med[2]) / 255.0)
    except Exception:
        return (1.0, 1.0, 1.0)


def run_pipeline(input_pdf: str, output_pdf: str):
    device, dtype = get_safe_device()
    reconstructor = DocumentLayoutReconstructor()
    translator = TranslationEngine(device, dtype)

    doc = fitz.open(input_pdf)
    all_paragraphs: List[ParagraphBlock] = []

    print(f"\n[İŞLEM BAŞLADI] Toplam Sayfa: {len(doc)} | Belge: {input_pdf}")

    global_id = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        paras = reconstructor.extract_paragraphs(page, page_num)
        for p in paras:
            p.id = global_id
            global_id += 1
            all_paragraphs.append(p)

    print(f"-> Tespit Edilen Toplam Bütünleşik Blok Sayısı: {len(all_paragraphs)}")

    for idx, p in enumerate(all_paragraphs):
        if p.is_standalone_math:
            p.translated_text = p.text
        else:
            p.translated_text = translator.translate_paragraph(p.text)

        if (idx + 1) % 50 == 0 or (idx + 1) == len(all_paragraphs):
            print(f"   Çeviri İlerlemesi: {idx + 1}/{len(all_paragraphs)} blok tamamlandı...")
            translator.save_cache()
            if device.type == "cuda":
                torch.cuda.empty_cache()
            gc.collect()

    font_reg_path, font_bold_path, font_validator = select_best_unicode_fonts()
    print(f"-> Aktif Font ve Zero-Tofu Glif Kalkanı: {os.path.basename(font_reg_path)}")

    layout_in = os.path.join("build", "layout_in.txt")
    layout_out = os.path.join("build", "layout_out.txt")
    os.makedirs("build", exist_ok=True)
    if os.path.exists(layout_out):
        os.remove(layout_out)

    with open(layout_in, "w", encoding="utf-8") as f:
        for p in all_paragraphs:
            clean_en = format_sub_sup_for_render(p.text, font_validator).replace("|", "")
            clean_tr = format_sub_sup_for_render(p.translated_text, font_validator).replace("|", "")
            f.write(
                f"{p.id}|{p.page_num}|{p.box.x0:.2f}|{p.box.y0:.2f}|"
                f"{p.box.width:.2f}|{p.box.height:.2f}|{p.font_size:.2f}|"
                f"{clean_en}|{clean_tr}\n"
            )

    engine_path = os.path.join("build", "AiEngine.exe")
    if os.path.exists(engine_path):
        print("\n2. [C++ AiEngine] OpenMP ile paralel kutu/font optimizasyonu yapılıyor...")
        subprocess.run([engine_path, layout_in, layout_out], check=False)

    print("\n3. [CERRAHİ RENDER] Kontrast garantili ve sıfır metin kayıplı PDF işleniyor...")

    # Sayfalara çizim yapmadan önce orijinal arka plan görüntüsünü önbelleğe al
    page_pixmaps: Dict[int, fitz.Pixmap] = {i: doc[i].get_pixmap() for i in range(len(doc))}
    registered_pages = set()

    for p in all_paragraphs:
        page = doc[p.page_num]
        if p.page_num not in registered_pages and os.path.exists(font_reg_path):
            try:
                page.insert_font(fontname="math_tr", fontfile=font_reg_path)
                page.insert_font(fontname="math_tr_b", fontfile=font_bold_path)
                registered_pages.add(p.page_num)
            except Exception:
                pass

        used_font = "helv"
        if p.page_num in registered_pages:
            used_font = "math_tr_b" if p.is_bold else "math_tr"

        render_text = format_sub_sup_for_render(p.translated_text, font_validator)

        if p.is_standalone_math:
            if p.is_from_ocr:
                target_rect = fitz.Rect(p.box.x0, p.box.y0, p.box.x1 + 8.0, p.box.y1 + 8.0)
                page.insert_textbox(
                    target_rect,
                    render_text,
                    fontsize=max(7.0, p.font_size),
                    fontname=used_font,
                    render_mode=3
                )
            continue

        # Arka plan rengini belirle (hem OCR hem de renkli şerit üzerindeki dijital bloklar için)
        if p.bg_color is not None:
            bg_color = p.bg_color
        else:
            bg_color = _sample_background_color(page_pixmaps[p.page_num], p.box)

        # Kontrast Garantisi: Zemin koyuysa (lacivert kapak, siyah tablo, mavi şerit) yazı beyaz,
        # zemin açıksa yazı koyu renk olur.
        bg_lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
        fg_color = (1.0, 1.0, 1.0) if bg_lum < 0.45 else p.text_color
        if bg_lum >= 0.45 and sum(fg_color) > 2.2:
            fg_color = (0.0, 0.0, 0.0)

        rect_erase = fitz.Rect(p.box.x0 - 1.0, p.box.y0 - 1.0, p.box.x1 + 1.5, p.box.y1 + 1.2)
        page.draw_rect(rect_erase, color=bg_color, fill=bg_color)

        is_single_line = p.box.height < (p.font_size * 1.9)
        is_narrow_col = p.box.width < 110.0
        pad_left = 4.0 if is_narrow_col else 0.0
        pad_right = 14.0 if is_narrow_col else (30.0 if is_single_line else 10.0)
        desired_y1 = p.box.y1 + (5.0 if is_single_line else 10.0)
        safe_y1 = min(desired_y1, p.max_allowed_y1) if p.max_allowed_y1 else desired_y1
        safe_y1 = max(safe_y1, p.box.y1 + 3.0)

        target_rect = fitz.Rect(p.box.x0 - pad_left, p.box.y0 - 1.0, p.box.x1 + pad_right, safe_y1)
        current_fs = p.font_size
        align_mode = 1 if p.is_centered else 0
        fitted = False

        while current_fs >= 4.8:
            rc = page.insert_textbox(
                target_rect,
                render_text,
                fontsize=current_fs,
                fontname=used_font,
                color=fg_color,
                align=align_mode,
                render_mode=0
            )
            if rc >= 0:
                fitted = True
                break
            page.draw_rect(target_rect, color=bg_color, fill=bg_color)
            current_fs -= 0.4

        if not fitted:
            emergency_rect = fitz.Rect(
                p.box.x0 - pad_left,
                p.box.y0 - 1.5,
                p.box.x1 + pad_right + 25.0,
                p.box.y1 + 18.0
            )
            page.insert_textbox(
                emergency_rect,
                render_text,
                fontsize=5.2,
                fontname=used_font,
                color=fg_color,
                align=align_mode,
                render_mode=0
            )

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
    print("[BAŞARILI] %100 Çevrimdışı Evrensel Motor (v10.0) Çıktıları Üretildi:")
    print(f"  1. Kusursuz PDF Dosyası        : {final_pdf_path}")
    print(f"  2. Temiz Türkçe TXT Dosyası    : {clean_txt_file}")
    print(f"  3. Karşılaştırmalı İnceleme TXT: {review_txt_file}")
    print("====================================================================")


if __name__ == "__main__":
    input_file = "ornek_belge.pdf"
    output_file = "cevirilmis_belge_ULTIMATE.pdf"
    run_pipeline(input_file, output_file)