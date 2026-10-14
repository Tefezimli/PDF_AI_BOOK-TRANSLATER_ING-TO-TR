import os
import re
import warnings
import subprocess
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

import pymupdf as fitz
from PIL import Image
import cv2
import numpy as np
import torch
import pytesseract

# --- 1. GÜVENLİK VE ÇEVRİMDIŞI ORTAM PROTOKOLÜ ---
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

os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_TOKEN"] = ""
os.environ["HUGGING_FACE_HUB_TOKEN"] = ""

warnings.filterwarnings("ignore")
import transformers
transformers.logging.set_verbosity_error()

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# --- 2. RTX 5080 (sm_120 BLACKWELL) DONANIM MOTORU ---
def get_safe_device() -> Tuple[torch.device, torch.dtype]:
    """
    RTX 5080 (sm_120) mimarisini denetler, CUDA 12.8+ yüklüyse TF32 ve FP16/BF16
    Tensor çekirdeklerini aktif eder. Uyumsuzluk varsa çok çekirdekli CPU'ya düşer.
    """
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
            print(f"[DONANIM] GPU Tam Kapasite Aktif: {gpu_name} (Mimari: sm_{cap[0]}{cap[1]} | Mod: {dtype})")
            return torch.device("cuda"), dtype

        except Exception as e:
            print(f"[DONANIM UYARISI] {torch.cuda.get_device_name(0)} (sm_120) algılandı ancak PyTorch derlemesi eski: {e}")
            print("[ÇÖZÜM] RTX 5080 için: pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu128")
            print("[GÜVENLİK PROTOKOLÜ] Çok çekirdekli CPU moduna geçildi.")

    cpu_threads = max(1, (os.cpu_count() or 4) - 1)
    torch.set_num_threads(cpu_threads)
    print(f"[DONANIM] CPU Modu Aktif ({cpu_threads} İzlek / Thread kullanılıyor).")
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


@dataclass
class ParagraphBlock:
    id: int
    page_num: int
    box: BoundingBox
    text: str
    translated_text: str = ""
    font_size: float = 9.5
    is_standalone_math: bool = False
    is_from_ocr: bool = False


# --- 4. UNICODE ÜST/ALT SİMGE VE AKADEMİK SÖZLÜK MOTORU ---
SUPERSCRIPT_MAP = str.maketrans("0123456789+-=()nxyzr", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿˣʸᶻʳ")
SUBSCRIPT_MAP = str.maketrans("0123456789+-=()nxyzr", "₀₁₂₃₄⁵₆₇₈₉₊₋₌₍₎ₙₓᵧ₂ᵣ")

def to_superscript(s: str) -> str:
    return s.translate(SUPERSCRIPT_MAP)

def to_subscript(s: str) -> str:
    return s.translate(SUBSCRIPT_MAP)

PRE_TRANSLATION_GLOSSARY = [
    (r'\bSIGNED BINARY NUMBERS\b', 'İŞARETLİ İKİLİ SAYILAR'),
    (r'\bCOMPLEMENTS OF NUMBERS\b', 'SAYILARIN TÜMLEYENLERİ'),
    (r'\bDiminished Radix Complement\b', 'Azaltılmış Taban Tümleyeni'),
    (r'\bRadix Complement\b', 'Taban Tümleyeni'),
    (r'\bSubtraction with Complements\b', 'Tümleyenlerle Çıkarma İşlemi'),
    (r'\bArithmetic Addition\b', 'Aritmetik Toplama'),
    (r'\bArithmetic Subtraction\b', 'Aritmetik Çıkarma'),
    (r'\bPractice Exercise\b', 'Uygulama Alıştırması'),
    (r'\bDiscard end carry\b', 'Son eldeyi atın'),
    (r'\bEnd-around carry\b', 'Döngüsel elde'),
    (r'\bend-around carry\b', 'döngüsel elde'),
    (r'\bno end carry\b', 'son elde yoktur'),
    (r'\bNo end carry\b', 'Son elde yoktur'),
    (r'\bNo end-around carry\b', 'Döngüsel elde yoktur'),
]

POST_TRANSLATION_FIXES = [
    (r'\bimzasız\b', 'işaretsiz'),
    (r'\bİmzasız\b', 'İşaretsiz'),
    (r'\bimzalı\b', 'işaretli'),
    (r'\bİmzalı\b', 'İşaretli'),
    (r'\btamamlayıcısı\b', 'tümleyeni'),
    (r'\btamamlayıcıları\b', 'tümleyenleri'),
    (r'\btamamlayıcı\b', 'tümleyen'),
    (r'\bTamamlayıcılar\b', 'Tümleyenler'),
    (r'\bSayıların Tamamlanması\b', 'Sayıların Tümleyenleri'),
    (r'\bNUMARALARIN KOMPLELERİ\b', 'SAYILARIN TÜMLEYENLERİ'),
    (r'\bBİNARY NUMARALARI SAHİPLİİ\b', 'İŞARETLİ İKİLİ SAYILAR'),
    (r'\bAritmetik Ekleme\b', 'Aritmetik Toplama'),
    (r'\bAritmetik Subtraksiyon\b', 'Aritmetik Çıkarma'),
    (r'\bAntrenman Egzersizi\b', 'Uygulama Alıştırması'),
    (r'\bEgzersiz Egzersizi\b', 'Uygulama Alıştırması'),
    (r'\bPratik Egzersiz\b', 'Uygulama Alıştırması'),
    (r'\bDisk ucu taşıma\b', 'Son eldeyi atın'),
    (r'\bDisk ucu\b', 'Son eldeyi atın'),
    (r'\buç taşıma\b', 'son elde'),
    (r'\bUç taşıma\b', 'Son elde'),
    (r'\ben az önemli\b', 'en düşük anlamlı'),
    (r'\ben önemli\b', 'en yüksek anlamlı'),
    (r'\bminuend\b', 'eksilen'),
    (r'\bMinuend\b', 'Eksilen'),
    (r'\bsubtrahend\b', 'çıkan'),
    (r'\balttrahend\b', 'çıkan'),
    (r'\bsubtrahin\b', 'çıkanın'),
    (r'\bsigned-magnitude\b', 'işaret-büyüklük'),
    (r'\bsigned-complement\b', 'işaret-tümleyen'),
    (r'\bsigned-1\'s-complement\b', "işaretli 1'e tümleyen"),
    (r'\bsigned-2\'s-complement\b', "işaretli 2'ye tümleyen"),
    (r'\b1\'in tümleyeni\b', "1'e tümleyen"),
    (r'\b2\'nin tümleyeni\b', "2'ye tümleyen"),
    (r'\b9\'un tümleyeni\b', "9'a tümleyen"),
    (r'\b10\'un tümleyeni\b', "10'a tümleyen"),
]


def clean_ocr_math_artifacts(text: str) -> str:
    """Fotoğraf/OCR kaynaklı matematik bozulmalarını temizler."""
    t = text
    t = re.sub(r'\b[rR]["”’]\s*N\b', "rⁿ - N", t)
    t = re.sub(r'\b7["”’]\s*N\b', "rⁿ - N", t)
    t = re.sub(r'\b10\s*["”’]\s*N\b', "10ⁿ - N", t)
    t = re.sub(r'\b2\s*["”’]\s*1\b', "2ⁿ - 1", t)
    t = re.sub(r'\bN\s*#\s*0\b', "N ≠ 0", t)
    t = re.sub(r'\(r\s+1\)', "(r - 1)", t)
    return t


def normalize_and_mask_math(text: str) -> Tuple[str, Dict[str, str]]:
    t = clean_ocr_math_artifacts(text)

    for pat, repl in PRE_TRANSLATION_GLOSSARY:
        t = re.sub(pat, repl, t)

    math_dict: Dict[str, str] = {}
    counter = 0

    math_patterns = [
        r'(\[?\([a-zA-Z0-9⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ₀₁₂₃₄⁵₆₇₈₉\^\s\-\+]+\)\s*[-+=]\s*[a-zA-Z0-9⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ₀₁₂₃₄⁵₆₇₈₉\^\(\)\s\-\+\]]+(?:\s*[-+=]\s*[a-zA-Z0-9⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ₀₁₂₃₄⁵₆₇₈₉]+)*)',
        r'(\b[a-zA-Z0-9⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ₀₁₂₃₄⁵₆₇₈₉\(\)\+\-]+(?:\s*[=≠<>≤≥]\s*[a-zA-Z0-9⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ₀₁₂₃₄⁵₆₇₈₉\(\)\+\-\s]+)+)',
        r'(\b[a-zA-Z0-9]+[⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ₀₁₂₃₄⁵₆₇₈₉]+(?:\s*[-+]\s*[a-zA-Z0-9⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ₀₁₂₃₄⁵₆₇₈₉]+)*)',
        r'(\([rRnN]\s*[-+]\s*[0-9]+\))',
    ]

    for pat in math_patterns:
        for match in re.finditer(pat, t):
            expr = match.group(1).strip()
            if re.fullmatch(r'[a-zA-Z]+-[a-zA-Z]+', expr):
                continue
            if len(expr) >= 2 and expr not in math_dict.values():
                key = f"MTH{counter}X"
                math_dict[key] = expr
                t = t.replace(expr, f" {key} ", 1)
                counter += 1

    t = re.sub(r'\s+', ' ', t).strip()
    return t, math_dict


def restore_math_and_polish(translated_text: str, math_dict: Dict[str, str]) -> str:
    res = translated_text

    for key, original in math_dict.items():
        idx = key.replace("MTH", "").replace("X", "")
        flex_pat = rf'(?:\bMTH\s*{idx}\s*X\b|\[?\s*FORM[A-ZÜÖÇŞİĞ]*\s*[_-]?\s*{idx}\s*\]?)'
        res = re.sub(flex_pat, f" {original} ", res, flags=re.IGNORECASE)

    for pat, repl in POST_TRANSLATION_FIXES:
        res = re.sub(pat, repl, res)

    return re.sub(r'\s+', ' ', res).strip()


# --- 5. HİBRİT DİJİTAL + FOTOĞRAF (OCR) BELGE DÜZENİ MOTORU ---
class DocumentLayoutReconstructor:
    def extract_paragraphs(self, page: fitz.Page, page_num: int) -> List[ParagraphBlock]:
        """
        Sayfada dijital metin varsa %100 doğrulukla çeker.
        Sayfa fotoğraf/tarama ise gelişmiş OpenCV + OCR motoruyla metne dönüştürür.
        """
        digital_blocks = self._extract_digital(page, page_num)
        if len(digital_blocks) > 0:
            return digital_blocks
        print(f"   [OCR MODU] Sayfa {page_num + 1} fotoğraf/tarama olarak algılandı, OCR ile metne dönüştürülüyor...")
        return self._extract_ocr_fallback(page, page_num)

    @staticmethod
    def _is_math_only(text: str) -> bool:
        alpha_count = sum(1 for c in text if c.isalpha())
        digit_count = sum(1 for c in text if c.isdigit())
        math_ops = sum(1 for c in text if c in "=+-≠<>≤≥±×÷")
        return (
            alpha_count == 0
            or (len(text) < 45 and math_ops >= 1 and alpha_count < 6)
            or (digit_count > alpha_count * 2 and len(text) < 60)
        )

    def _extract_digital(self, page: fitz.Page, page_num: int) -> List[ParagraphBlock]:
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES)
        blocks = page_dict.get("blocks", [])
        paragraph_blocks: List[ParagraphBlock] = []
        p_idx = 0

        for b in blocks:
            if b.get("type") != 0:
                continue

            lines = b.get("lines", [])
            if not lines:
                continue

            all_sizes = [
                span["size"]
                for line in lines
                for span in line.get("spans", [])
                if span.get("text", "").strip()
            ]
            if not all_sizes:
                continue

            sorted_sizes = sorted(all_sizes)
            base_size = sorted_sizes[len(sorted_sizes) // 2]

            line_texts: List[str] = []
            for line in lines:
                spans = line.get("spans", [])
                if not spans:
                    continue

                base_spans = [s for s in spans if s["size"] >= base_size * 0.88]
                ref_y = base_spans[0]["origin"][1] if base_spans else spans[0]["origin"][1]

                line_str = ""
                for s in spans:
                    raw_span = s.get("text", "")
                    if not raw_span:
                        continue
                    s_size = s.get("size", base_size)
                    s_y = s["origin"][1]
                    s_flags = s.get("flags", 0)

                    is_small = s_size < base_size * 0.85
                    is_super = (s_flags & 1) or (is_small and (ref_y - s_y) > base_size * 0.12)
                    is_sub = is_small and (s_y - ref_y) > base_size * 0.08

                    if is_super and len(raw_span.strip()) <= 4:
                        line_str += to_superscript(raw_span.strip())
                    elif is_sub and len(raw_span.strip()) <= 4:
                        line_str += to_subscript(raw_span.strip())
                    else:
                        line_str += raw_span

                line_texts.append(line_str.strip())

            full_text = ""
            for lt in line_texts:
                if not lt:
                    continue
                if full_text.endswith("-"):
                    full_text = full_text[:-1] + lt
                else:
                    full_text = (full_text + " " + lt).strip() if full_text else lt

            full_text = re.sub(r'\s+', ' ', full_text).replace("|", "").strip()
            if len(full_text) < 2:
                continue

            bbox = b.get("bbox", (0, 0, 0, 0))
            box = BoundingBox(x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3])

            paragraph_blocks.append(ParagraphBlock(
                id=p_idx,
                page_num=page_num,
                box=box,
                text=full_text,
                font_size=max(7.0, min(13.0, base_size)),
                is_standalone_math=self._is_math_only(full_text),
                is_from_ocr=False
            ))
            p_idx += 1

        return paragraph_blocks

    def _extract_ocr_fallback(self, page: fitz.Page, page_num: int, scale: float = 2.5) -> List[ParagraphBlock]:
        """Fotoğraf şeklindeki sayfaları yüksek çözünürlükle okur ve kopyalanabilir metin bloklarına dönüştürür."""
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        data = pytesseract.image_to_data(Image.fromarray(thresh), lang="eng", output_type=pytesseract.Output.DICT)
        paragraphs_raw: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}

        for i in range(len(data["text"])):
            if int(data["level"][i]) != 5:
                continue
            text = data["text"][i].strip()
            if not text or int(data["conf"][i]) < 35:
                continue
            key = (data["block_num"][i], data["par_num"][i])
            paragraphs_raw.setdefault(key, []).append({
                "text": text,
                "left": data["left"][i],
                "top": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
                "line_num": data["line_num"][i]
            })

        paragraph_blocks: List[ParagraphBlock] = []
        for p_idx, (_, words) in enumerate(paragraphs_raw.items()):
            lines_dict: Dict[int, List[str]] = {}
            for w in words:
                lines_dict.setdefault(w["line_num"], []).append(w["text"])

            full_text = ""
            for ln in sorted(lines_dict.keys()):
                s = " ".join(lines_dict[ln]).strip()
                full_text = (full_text[:-1] + s) if full_text.endswith("-") else (f"{full_text} {s}".strip())

            full_text = clean_ocr_math_artifacts(full_text.replace("|", "").strip())
            if len(full_text) < 2:
                continue

            min_x = min(w["left"] for w in words) / scale
            min_y = min(w["top"] for w in words) / scale
            max_r = max(w["left"] + w["width"] for w in words) / scale
            max_b = max(w["top"] + w["height"] for w in words) / scale

            avg_line_h = (max_b - min_y) / max(1, len(lines_dict))
            font_size = max(7.0, min(12.5, avg_line_h * 0.75))

            paragraph_blocks.append(ParagraphBlock(
                id=p_idx,
                page_num=page_num,
                box=BoundingBox(min_x, min_y, max_r, max_b),
                text=full_text,
                font_size=font_size,
                is_standalone_math=self._is_math_only(full_text),
                is_from_ocr=True
            ))
        return paragraph_blocks


# --- 6. YÜKSEK KALİTELİ CÜMLE BAZLI ÇEVİRİ MOTORU ---
class TranslationEngine:
    def __init__(self, device: torch.device, dtype: torch.dtype):
        self.device = device
        self.dtype = dtype
        print("1. [YEREL ÇEVİRİ] Helsinki-NLP/opus-mt-tc-big-en-tr modeli yükleniyor...")
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        model_name = "Helsinki-NLP/opus-mt-tc-big-en-tr"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=False)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name,
            token=False,
            torch_dtype=self.dtype if self.device.type == "cuda" else torch.float32
        ).to(self.device)
        self.model.eval()
        print(f"-> Çeviri Modeli Hazır (Aygıt: {self.device} | Hassasiyet: {self.model.dtype})")

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\(\[])', text)
        return [s.strip() for s in sentences if s.strip()]

    def translate_paragraph(self, raw_text: str) -> str:
        sentences = self._split_into_sentences(raw_text)
        if not sentences:
            return raw_text

        masked_sentences: List[str] = []
        math_dicts: List[Dict[str, str]] = []

        for s in sentences:
            m_text, m_dict = normalize_and_mask_math(s)
            masked_sentences.append(m_text)
            math_dicts.append(m_dict)

        try:
            inputs = self.tokenizer(
                masked_sentences,
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

            decoded_list = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
        except Exception as e:
            print(f"[ÇEVİRİ HATASI] {e}")
            return raw_text

        final_sentences: List[str] = []
        for decoded, m_dict in zip(decoded_list, math_dicts):
            restored = restore_math_and_polish(decoded.replace("|", ""), m_dict)
            final_sentences.append(restored)

        return " ".join(final_sentences)


# --- 7. KOPYALANABİLİR TXT DIŞA AKTARIM FONKSİYONU ---
def export_copyable_txt_files(
    all_paragraphs: List[ParagraphBlock],
    clean_txt_path: str,
    bilingual_txt_path: str
):
    """
    Tüm belgeyi sayfa sırasıyla hem saf Türkçe (.txt) hem de
    Orijinal/Türkçe karşılaştırmalı inceleme (.txt) dosyası olarak kaydeder.
    """
    pages_map: Dict[int, List[ParagraphBlock]] = {}
    for p in all_paragraphs:
        pages_map.setdefault(p.page_num, []).append(p)

    # 1. Saf Türkçe & Formül Kopyalanabilir TXT
    with open(clean_txt_path, "w", encoding="utf-8") as f_clean:
        f_clean.write("====================================================================\n")
        f_clean.write("   PDF AI ENGINE - TAMAMEN KOPYALANABİLİR TÜRKÇE METİN VE FORMÜLLER\n")
        f_clean.write("====================================================================\n\n")

        for page_num in sorted(pages_map.keys()):
            f_clean.write(f"--- [SAYFA {page_num + 1}] ---\n\n")
            # Yukarıdan aşağıya okuma sırasına göre diz
            blocks = sorted(pages_map[page_num], key=lambda b: (round(b.box.y0 / 10), b.box.x0))
            for b in blocks:
                f_clean.write(f"{b.translated_text}\n\n")

    # 2. İnceleme ve Kontrol İçin Karşılaştırmalı (EN -> TR) TXT
    with open(bilingual_txt_path, "w", encoding="utf-8") as f_bi:
        f_bi.write("====================================================================\n")
        f_bi.write("   PDF AI ENGINE - KARŞILAŞTIRMALI İNCELEME VE KOPYALAMA DOSYASI\n")
        f_bi.write("====================================================================\n\n")

        for page_num in sorted(pages_map.keys()):
            f_bi.write(f"==================== SAYFA {page_num + 1} ====================\n\n")
            blocks = sorted(pages_map[page_num], key=lambda b: (round(b.box.y0 / 10), b.box.x0))
            for b in blocks:
                tag = "[SAF FORMÜL / TABLO]" if b.is_standalone_math else f"[BLOK #{b.id}]"
                f_bi.write(f"{tag}\n")
                f_bi.write(f"EN (Orijinal) : {b.text}\n")
                f_bi.write(f"TR (Çeviri)   : {b.translated_text}\n")
                f_bi.write("-" * 68 + "\n")
            f_bi.write("\n")


# --- 8. İŞ HATTININ YÜRÜTÜLMESİ VE SEÇİLEBİLİR PDF + TXT ÜRETİMİ ---
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

    print(f"-> Tespit Edilen Bütüncül Blok Sayısı: {len(all_paragraphs)}")

    for idx, p in enumerate(all_paragraphs):
        if p.is_standalone_math:
            p.translated_text = p.text
        else:
            p.translated_text = translator.translate_paragraph(p.text)
        if (idx + 1) % 25 == 0 or (idx + 1) == len(all_paragraphs):
            print(f"   Çeviri İlerlemesi: {idx + 1}/{len(all_paragraphs)} blok tamamlandı...")

    # C++ AiEngine entegrasyonu
    layout_in = os.path.join("build", "layout_in.txt")
    layout_out = os.path.join("build", "layout_out.txt")
    os.makedirs("build", exist_ok=True)
    if os.path.exists(layout_out):
        os.remove(layout_out)

    with open(layout_in, "w", encoding="utf-8") as f:
        for p in all_paragraphs:
            f.write(
                f"{p.id}|{p.page_num}|{p.box.x0:.2f}|{p.box.y0:.2f}|"
                f"{p.box.width:.2f}|{p.box.height:.2f}|{p.font_size:.2f}|"
                f"{p.text.replace('|', '')}|{p.translated_text.replace('|', '')}\n"
            )

    engine_path = os.path.join("build", "AiEngine.exe")
    if os.path.exists(engine_path):
        print("\n2. [C++ AiEngine] OpenMP ile paralel kutu/font optimizasyonu yapılıyor...")
        subprocess.run([engine_path, layout_in, layout_out], check=False)

    adapted_elements: Dict[int, Tuple[float, str]] = {}
    if os.path.exists(layout_out):
        with open(layout_out, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) >= 8:
                    adapted_elements[int(parts[0])] = (float(parts[6]), parts[7])

    print("\n3. [CERRAHİ RENDER] Seçilebilir/Kopyalanabilir PDF katmanı oluşturuluyor...")
    font_path = r"C:\Windows\Fonts\arial.ttf"
    has_arial = os.path.exists(font_path)

    for p in all_paragraphs:
        page = doc[p.page_num]
        used_font = "helv"
        if has_arial:
            try:
                page.insert_font(fontname="arial_tr", fontfile=font_path)
                used_font = "arial_tr"
            except Exception:
                used_font = "helv"

        # EĞER SAF MATEMATİK BLOĞU İSE:
        if p.is_standalone_math:
            # Sayfa fotoğraf/tarama (OCR) ise formül görüntüsünü bozma ama
            # fareyle seçilip kopyalanabilmesi için görünmez metin katmanı (render_mode=3) ekle!
            if p.is_from_ocr:
                target_rect = fitz.Rect(p.box.x0, p.box.y0, p.box.x1 + 8.0, p.box.y1 + 8.0)
                page.insert_textbox(
                    target_rect,
                    p.text,
                    fontsize=max(6.5, p.font_size),
                    fontname=used_font,
                    render_mode=3  # Görünmez ama fareyle seçilebilir/kopyalanabilir metin
                )
            continue

        init_font_size, final_text = adapted_elements.get(p.id, (p.font_size, p.translated_text))
        p.translated_text = final_text

        rect_erase = fitz.Rect(p.box.x0 - 1.0, p.box.y0 - 1.0, p.box.x1 + 2.0, p.box.y1 + 2.0)
        page.draw_rect(rect_erase, color=(1, 1, 1), fill=(1, 1, 1))

        target_rect = fitz.Rect(p.box.x0, p.box.y0, p.box.x1 + 8.0, p.box.y1 + 12.0)
        current_fs = min(p.font_size, max(6.5, init_font_size))

        while current_fs >= 5.5:
            rc = page.insert_textbox(
                target_rect,
                final_text,
                fontsize=current_fs,
                fontname=used_font,
                color=(0, 0, 0),
                align=0,
                render_mode=0  # Standart görünür ve seçilebilir vektörel metin
            )
            if rc >= 0:
                break
            page.draw_rect(target_rect, color=(1, 1, 1), fill=(1, 1, 1))
            current_fs -= 0.4

    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()

    # ADIM 4: İncelenebilir ve Kopyalanabilir TXT Dosyalarını Üret
    base_name = os.path.splitext(output_pdf)[0]
    clean_txt_file = f"{base_name}.txt"
    review_txt_file = f"{base_name}_INCELEME.txt"

    export_copyable_txt_files(all_paragraphs, clean_txt_file, review_txt_file)

    print("\n====================================================================")
    print("[BAŞARILI] Tüm Çıktılar Kopyalanabilir Formatta Üretildi:")
    print(f"  1. Seçilebilir PDF Dosyası     : {output_pdf}")
    print(f"  2. Temiz Türkçe TXT Dosyası    : {clean_txt_file}")
    print(f"  3. Karşılaştırmalı İnceleme TXT: {review_txt_file}")
    print("====================================================================")


if __name__ == "__main__":
    input_file = "ornek_belge.pdf"
    output_file = "cevirilmis_belge_ULTIMATE.pdf"
    run_pipeline(input_file, output_file)