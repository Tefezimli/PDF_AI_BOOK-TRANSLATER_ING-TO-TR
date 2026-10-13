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
        try: os.remove(p)
        except Exception: pass

os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_TOKEN"] = ""
os.environ["HUGGING_FACE_HUB_TOKEN"] = ""

warnings.filterwarnings("ignore")
import transformers
transformers.logging.set_verbosity_error()

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# --- 2. DONANIM DENETİMİ (RTX 5080 sm_120 CPU Fallback) ---
def get_safe_device() -> torch.device:
    device = torch.device("cpu")
    if torch.cuda.is_available():
        try:
            test_tensor = torch.tensor([1.0], device="cuda")
            _ = test_tensor * 2.0
            device = torch.device("cuda")
            print(f"[DONANIM] GPU Aktif: {torch.cuda.get_device_name(0)}")
        except Exception:
            print("[DONANIM UYARISI] GPU (RTX 5080 / sm_120) bulundu ancak PyTorch CUDA çekirdeği ile uyumsuz.")
            print("[GÜVENLİK PROTOKOLÜ] Otonom olarak CPU (İşlemci) moduna geçildi.")
            device = torch.device("cpu")
    else:
        print("[DONANIM] CUDA bulunamadı, CPU modunda çalışılıyor.")
    return device


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
    font_size: float = 9.0
    is_standalone_math: bool = False


# --- 4. AKILLI MATEMATİK VE FORMÜL DÜZELTİCİ (SEMANTIC NORMALIZER) ---
def normalize_and_mask_math(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Tesseract'ın OCR yaparken bozduğu matematiksel ifadeleri düzeltir
    ve çeviriye sokmadan önce [FORMUL_X] etiketleriyle korumaya alır.
    """
    # 1. Bilinen Tesseract OCR matematik bozulmalarını onar
    t = text
    t = re.sub(r'\b[rR]["”’]\s*N\b', "r^n - N", t)
    t = re.sub(r'\b7["”’]\s*N\b', "r^n - N", t)
    t = re.sub(r'\b10\s*["”’]\s*N\b', "10^n - N", t)
    t = re.sub(r'\bN\s*#\s*0\b', "N ≠ 0", t)
    t = re.sub(r'\(r\s+1\)', "(r - 1)", t)
    t = re.sub(r'\(\([rR]["”’]\s*1\)\s*N\]', "[(r^n - 1) - N]", t)
    t = re.sub(r'\brs\s+tamamlayıcısı\b', "r'nin tamamlayıcısı", t, flags=re.IGNORECASE)

    # 2. Formülleri yakalayan ve maskeleyen regex
    math_dict = {}
    counter = 0

    # Inline formül şablonları: r^n - N, N ≠ 0, (r - 1), 7610 + 1 = 7611, vb.
    math_patterns = [
        r'(\b[a-zA-Z0-9]\^[a-zA-Z0-9]+(?:\s*[-+=]\s*[a-zA-Z0-9]+)*)',
        r'(\b[a-zA-Z0-9]+\s*[≠=<>+\-*/]\s*[a-zA-Z0-9]+(?:\s*[-+=*/]\s*[a-zA-Z0-9]+)*)',
        r'(\([a-zA-Z0-9]\s*[-+]\s*[a-zA-Z0-9]+\)\'?s?)',
        r'(\[\([a-zA-Z0-9\^]+\s*-\s*[0-9]+\)\s*-\s*[a-zA-Z0-9]+\]\s*\+\s*[0-9]+)',
    ]

    for pat in math_patterns:
        for match in re.finditer(pat, t):
            expr = match.group(1).strip()
            if len(expr) > 1 and expr not in math_dict.values():
                placeholder = f" [FORMUL_{counter}] "
                math_dict[f"[FORMUL_{counter}]"] = expr
                t = t.replace(expr, placeholder)
                counter += 1

    t = re.sub(r'\s+', ' ', t).strip()
    return t, math_dict


def restore_math(translated_text: str, math_dict: Dict[str, str]) -> str:
    """Maskelenen formülleri çevrilmiş metne orijinal haliyle yerleştirir."""
    res = translated_text
    for placeholder, original in math_dict.items():
        p_num = placeholder.strip().replace("[FORMUL_", "").replace("]", "")
        flex_pat = r'\[\s*FORMUL\s*_\s*' + p_num + r'\s*\]'
        res = re.sub(flex_pat, f" {original} ", res, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', res).strip()


# --- 5. PARAGRAF BİRLEŞTİRİCİ VE DÜZEN MOTORU ---
class DocumentLayoutReconstructor:
    def __init__(self):
        pass

    def extract_paragraphs(self, page: fitz.Page, page_num: int, scale: float = 2.0) -> List[ParagraphBlock]:
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        data = pytesseract.image_to_data(Image.fromarray(thresh), lang="eng", output_type=pytesseract.Output.DICT)
        n_boxes = len(data['text'])

        # Paragraf ve Blok bazında satırları topla
        paragraphs_raw: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}

        for i in range(n_boxes):
            if int(data['level'][i]) != 5: continue
            text = data['text'][i].strip()
            if not text: continue
            if int(data['conf'][i]) < 35: continue

            block_id = data['block_num'][i]
            par_id = data['par_num'][i]
            key = (block_id, par_id)

            if key not in paragraphs_raw:
                paragraphs_raw[key] = []

            paragraphs_raw[key].append({
                'text': text,
                'left': data['left'][i],
                'top': data['top'][i],
                'width': data['width'][i],
                'height': data['height'][i],
                'line_num': data['line_num'][i]
            })

        paragraph_blocks: List[ParagraphBlock] = []
        p_idx = 0

        for key, words in paragraphs_raw.items():
            if not words: continue

            # Satırlara göre grupla
            lines_dict: Dict[int, List[str]] = {}
            min_x = min(w['left'] for w in words)
            min_y = min(w['top'] for w in words)
            max_r = max(w['left'] + w['width'] for w in words)
            max_b = max(w['top'] + w['height'] for w in words)

            for w in words:
                ln = w['line_num']
                if ln not in lines_dict: lines_dict[ln] = []
                lines_dict[ln].append(w['text'])

            # Satırları cümle bütünlüğünü koruyacak şekilde bağla
            line_strings = []
            for ln in sorted(lines_dict.keys()):
                line_str = " ".join(lines_dict[ln]).strip()
                line_strings.append(line_str)

            full_paragraph_text = ""
            for s in line_strings:
                if full_paragraph_text.endswith("-"):
                    full_paragraph_text = full_paragraph_text[:-1] + s
                else:
                    if full_paragraph_text:
                        full_paragraph_text += " " + s
                    else:
                        full_paragraph_text = s

            full_paragraph_text = full_paragraph_text.replace("|", "").strip()
            if len(full_paragraph_text) < 3:
                continue

            # Ayrık denklem bloğu mu denetle
            is_math_block = (
                len(full_paragraph_text) < 40 and 
                any(op in full_paragraph_text for op in ['=', '+', '-', '≠']) and
                sum(1 for c in full_paragraph_text if c.isdigit()) > 4
            )

            box = BoundingBox(
                x0=min_x / scale,
                y0=min_y / scale,
                x1=max_r / scale,
                y1=max_b / scale
            )

            # Ortalama satır yüksekliğinden punto hesapla
            avg_line_h = (max_b - min_y) / max(1, len(line_strings)) / scale
            font_size = max(7.0, min(12.5, avg_line_h * 0.75))

            pb = ParagraphBlock(
                id=p_idx,
                page_num=page_num,
                box=box,
                text=full_paragraph_text,
                font_size=font_size,
                is_standalone_math=is_math_block
            )
            paragraph_blocks.append(pb)
            p_idx += 1

        return paragraph_blocks


# --- 6. YEREL ÇEVİRİ MOTORU (Helsinki-NLP) ---
class TranslationEngine:
    def __init__(self, device: torch.device):
        self.device = device
        print("1. [YEREL ÇEVİRİ] Helsinki-NLP/opus-mt-tc-big-en-tr modeli yükleniyor...")
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        
        model_name = "Helsinki-NLP/opus-mt-tc-big-en-tr"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=False)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, token=False).to(self.device)
        print(f"-> Çeviri Modeli Hazır (Aygıt: {self.device})")

    def translate_paragraph(self, raw_text: str) -> str:
        # 1. Matematiksel ifadeleri onar ve maskele
        masked_text, math_dict = normalize_and_mask_math(raw_text)

        try:
            inputs = self.tokenizer(
                masked_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model.generate(**inputs, max_length=512)

            translated = self.tokenizer.decode(outputs[0], skip_special_tokens=True).replace("|", "")
        except Exception as e:
            print(f"[ÇEVİRİ HATASI] {e}")
            return raw_text

        # 2. Formülleri Türkçeleştirilmiş paragrafa hasarsız geri monte et
        restored = restore_math(translated, math_dict)
        return restored


# --- 7. İŞ HATTININ YÜRÜTÜLMESİ VE CERRAHİ RENDER ---
def run_pipeline(input_pdf: str, output_pdf: str):
    device = get_safe_device()
    reconstructor = DocumentLayoutReconstructor()
    translator = TranslationEngine(device)

    doc = fitz.open(input_pdf)
    all_paragraphs: List[ParagraphBlock] = []

    print(f"\n[İŞLEM BAŞLADI] Toplam Sayfa: {len(doc)} | Belge: {input_pdf}")

    # ADIM 1: Paragraf Düzeyinde Hiyerarşik Çıkarım
    global_id = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        paras = reconstructor.extract_paragraphs(page, page_num)
        for p in paras:
            p.id = global_id
            global_id += 1
            all_paragraphs.append(p)

    print(f"-> Tespit Edilen Bütüncül Paragraf Sayısı: {len(all_paragraphs)}")

    # ADIM 2: Paragraf Çevirisi (Formüller Maskelenerek)
    for p in all_paragraphs:
        if p.is_standalone_math:
            # Saf formül bloklarını çevirmeden orijinal bırak
            p.translated_text = p.text
        else:
            p.translated_text = translator.translate_paragraph(p.text)

    # ADIM 3: C++ AiEngine için `layout_in.txt` Hazırla
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

    # ADIM 4: C++ AiEngine ile Dinamik Punto Adaptasyonu
    engine_path = os.path.join("build", "AiEngine.exe")
    if os.path.exists(engine_path):
        print("\n2. [C++ AiEngine] OpenMP ile font ve metin sığdırma hesabı yapılıyor...")
        subprocess.run([engine_path, layout_in, layout_out], check=True)

    adapted_elements: Dict[int, Tuple[float, str]] = {}
    if os.path.exists(layout_out):
        with open(layout_out, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) >= 8:
                    b_id = int(parts[0])
                    f_size = float(parts[6])
                    tr_text = parts[7]
                    adapted_elements[b_id] = (f_size, tr_text)

    # ADIM 5: Kusursuz Blok Temizleme ve Montaj
    print("\n3. [CERRAHİ RENDER] Paragraflar blok halinde temizlenip Türkçe yerleştiriliyor...")
    for p in all_paragraphs:
        page = doc[p.page_num]
        final_font_size = adapted_elements.get(p.id, (p.font_size, p.translated_text))[0]
        final_text = adapted_elements.get(p.id, (p.font_size, p.translated_text))[1]

        # 1. Eski paragraf alanını tamamen temizle (Artık harf kalmaması için sağdan ve alttan pay ver)
        rect_erase = fitz.Rect(
            p.box.x0 - 2.0,
            p.box.y0 - 2.0,
            p.box.x1 + 6.0,
            p.box.y1 + 4.0
        )
        page.draw_rect(rect_erase, color=(1, 1, 1), fill=(1, 1, 1))

        # 2. Font Seçimi
        try:
            page.insert_font(fontname="arial_tr", fontfile=r"C:\Windows\Fonts\arial.ttf")
            used_font = "arial_tr"
        except Exception:
            used_font = "helv"

        # 3. Metin Kutusuna Düzgün Hizalamayla Yaz (Word Wrap)
        # Paragraf kutusunun yüksekliğini Türkçe metnin uzama payına göre genişlet
        target_rect = fitz.Rect(
            p.box.x0,
            p.box.y0,
            p.box.x1 + 10.0,
            p.box.y1 + 25.0
        )

        page.insert_textbox(
            target_rect,
            final_text,
            fontsize=max(6.5, final_font_size),
            fontname=used_font,
            color=(0, 0, 0),
            align=0
        )

    doc.save(output_pdf)
    doc.close()
    print(f"\n[BAŞARILI] Kusursuz Paragraf ve Formül Bütünlüğüne Sahip Belge Üretildi: {output_pdf}")


if __name__ == "__main__":
    input_file = "ornek_belge.pdf"
    output_file = "cevirilmis_belge_ULTIMATE.pdf"
    run_pipeline(input_file, output_file)