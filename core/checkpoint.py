"""Sayfa bazlı mizanpaj-analiz checkpoint sistemi.

Uzun kitaplarda (700+ sayfa) işlem çökerse yeniden başlatmada pahalı
PyMuPDF/OCR analizini atlamak için sayfa bloklarını JSONL dosyasına yazar.
Çeviri devam etme zaten SelfHealingCache üzerinden olur; buradaki amaç
analiz aşamasını atlamak ve önbellek floş sıklığını sayfa bazına indirmek.

Dosya düzeni (build/checkpoints/<ad>_<parmakizi>.jsonl):
  1. satır : header {version, fingerprint, allow_ocr, total_pages, input}
  sonraki  : sayfa başına {"page": n, "blocks": [ParagraphBlock, ...]}
Satır bazlı JSON sayesinde çökme anında yarım kalan son satır yüklenirken
sessizce yok sayılır (JSONL append güvenliği).
"""
import dataclasses
import hashlib
import json
import os
from typing import Any, Dict, List

from core.models import BoundingBox, ParagraphBlock

CHECKPOINT_VERSION = 1
CHECKPOINT_DIR = os.path.join("build", "checkpoints")


def document_fingerprint(input_pdf: str) -> Dict[str, Any]:
    """Girdi PDF'nin değişmediğini doğrulayan hızlı parmak izi
    (boyut + mtime + ilk 64 KB özeti; tüm dosyayı hash'lemeye gerek yok)."""
    st = os.stat(input_pdf)
    with open(input_pdf, "rb") as f:
        head = f.read(65536)
    return {
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "head_md5": hashlib.md5(head).hexdigest(),
    }


def block_to_dict(p: ParagraphBlock) -> Dict[str, Any]:
    return dataclasses.asdict(p)


def block_from_dict(d: Dict[str, Any]) -> ParagraphBlock:
    box = BoundingBox(**d["box"])
    kwargs = {k: v for k, v in d.items() if k != "box"}
    if isinstance(kwargs.get("text_color"), list):
        kwargs["text_color"] = tuple(kwargs["text_color"])
    if isinstance(kwargs.get("bg_color"), list):
        kwargs["bg_color"] = tuple(kwargs["bg_color"])
    return ParagraphBlock(box=box, **kwargs)


class ExtractionCheckpoint:
    """Mizanpaj analizinin sayfa sayfa kalıcı hali.

    Kullanım akışı:
        ckpt = ExtractionCheckpoint.create_or_load(girdi.pdf, allow_ocr=..., total_pages=...)
        for n in range(total_pages):
            if ckpt.has_page(n): paras = ckpt.get_page(n)
            else: paras = motor.extract(...); ckpt.add_page(n, paras)
        ...  # başarılı işin sonunda ckpt.discard()
    """

    def __init__(self, path: str, header: Dict[str, Any]):
        self.path = path
        self.header = header
        self.pages: Dict[int, List[ParagraphBlock]] = {}

    @classmethod
    def create_or_load(
        cls,
        input_pdf: str,
        *,
        allow_ocr: bool,
        total_pages: int,
        resume: bool = True,
        checkpoint_dir: str = CHECKPOINT_DIR,
    ) -> "ExtractionCheckpoint":
        fp = document_fingerprint(input_pdf)
        os.makedirs(checkpoint_dir, exist_ok=True)
        digest = hashlib.md5(f"{fp}|{allow_ocr}".encode("utf-8")).hexdigest()[:10]
        base = os.path.splitext(os.path.basename(input_pdf))[0]
        path = os.path.join(checkpoint_dir, f"{base}_{digest}.jsonl")
        header = {
            "version": CHECKPOINT_VERSION,
            "fingerprint": fp,
            "allow_ocr": allow_ocr,
            "total_pages": total_pages,
            "input": os.path.abspath(input_pdf),
        }

        ckpt = cls(path, header)
        resumed_pages = 0
        if resume and os.path.exists(path):
            resumed_pages = ckpt._load_existing()
        ckpt._rewrite()  # yarım satırları budadıktan sonra tutarlı tek kaynak
        if resumed_pages:
            print(f"[CHECKPOINT] {resumed_pages} sayfanin mizanpaj analizi onceki calismadan geri yuklendi.")
        return ckpt

    def _load_existing(self) -> int:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return 0
        if not lines:
            return 0
        try:
            old_header = json.loads(lines[0])
        except json.JSONDecodeError:
            return 0
        if old_header.get("fingerprint") != self.header["fingerprint"]:
            return 0  # girdi değişmiş: eski checkpoint geçersiz

        for ln in lines[1:]:
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue  # çökme anında yarım kalan satır
            try:
                self.pages[int(rec["page"])] = [block_from_dict(b) for b in rec.get("blocks", [])]
            except (KeyError, TypeError, ValueError):
                continue  # bozuk kayıt: o sayfa yeniden analiz edilir
        return len(self.pages)

    def _rewrite(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.header, ensure_ascii=False) + "\n")
            for n in sorted(self.pages):
                rec = {"page": n, "blocks": [block_to_dict(b) for b in self.pages[n]]}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def has_page(self, page_num: int) -> bool:
        return page_num in self.pages

    def get_page(self, page_num: int) -> List[ParagraphBlock]:
        return self.pages[page_num]

    def add_page(self, page_num: int, blocks: List[ParagraphBlock]) -> None:
        self.pages[page_num] = list(blocks)
        rec = {"page": page_num, "blocks": [block_to_dict(b) for b in blocks]}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def discard(self) -> None:
        """Başarılı işin sonunda çağrılır; checkpoint dosyasını kaldırır."""
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except OSError:
            pass
