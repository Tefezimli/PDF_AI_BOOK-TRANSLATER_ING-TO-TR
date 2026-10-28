from __future__ import annotations

import os
import re
from typing import List, Dict
import pymupdf as fitz

try:
    import torch
except ImportError:
    # Hafif kurulum ([ai] extra'sı yok): --doctor / --eval (offline) çalışsın.
    torch = None

from core.models import ParagraphBlock
from core.unicode_sanitizer import normalize_unicode_text, DeterministicArtifactPurger
from extractors.formalism import FormalismAnalyzer
from translators.cache_manager import SelfHealingCache
from translators.domain_registry import DynamicAcademicRegistry
from translators.lmstudio_backend import LMStudioBackend


class UniversalTranslationEngine:
    """
    Çift Motorlu (LM Studio Yerel LLM + Helsinki-NLP Opus-MT) Çeviri Orkestratörü.
    - Model yerel önbellekte yoksa ilk çalıştırmada otomatik indirir, ardından çevrimdışı çalışır.
    - ﴾ ﴿ (\ufd3e, \ufd3f) gibi bozuk sembolleri logit seviyesinde (bad_words_ids) yasaklar.
    """
    def __init__(self, device: torch.device, dtype: torch.dtype, cache_path: str = "build/translation_cache.json"):
        self.device = device
        self.dtype = dtype
        self.cache = SelfHealingCache(cache_path)
        self.registry = DynamicAcademicRegistry()
        self.lmstudio = LMStudioBackend()

        print("1. [YEREL CEVIRI] Helsinki-NLP/opus-mt-tc-big-en-tr kontrol ediliyor...")
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        model_name = "Helsinki-NLP/opus-mt-tc-big-en-tr"
        target_dtype = self.dtype if self.device.type == "cuda" else torch.float32

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=False, local_files_only=True)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                token=False,
                local_files_only=True,
                torch_dtype=target_dtype
            ).to(self.device)
            print("-> Ceviri Modeli yerel disk onbelleginden (%100 Cevrimdisi) yuklendi.")
        except Exception:
            print("-> Model yerel onbellekte bulunamadi. Ilk kurulum icin HuggingFace uzerinden indiriliyor...")
            os.environ["HF_HUB_OFFLINE"] = "0"
            os.environ["TRANSFORMERS_OFFLINE"] = "0"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=False, local_files_only=False)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                token=False,
                local_files_only=False,
                torch_dtype=target_dtype
            ).to(self.device)
            print("-> Model basariyla indirildi! Bundan sonraki calistirmalarda %100 cevrimdisi calisacak.")

        self.model.eval()
        self.bad_words_ids = DeterministicArtifactPurger.build_forbidden_token_ids(self.tokenizer)
        engine_mode = f"LM Studio ({self.lmstudio.model_id}) + Opus-MT" if self.lmstudio.available else "Opus-MT"
        print(f"-> Aktif Ceviri Motoru: {engine_mode} | Aygit: {self.device} | Hassasiyet: {self.model.dtype}")

    def profile_book_domain(self, doc: fitz.Document) -> None:
        self.registry.profile_document(doc)
        self.lmstudio.set_domain(self.registry.active_label)

    def save_cache(self) -> bool:
        return self.cache.save()

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        protected = re.sub(
            r'\b(e\.g|i\.e|Fig|fig|Figure|Sec|sec|Ch|ch|Dr|Mr|Ms|vs|etc|No|no)\.\s+',
            r'\1<DOT> ',
            text
        )
        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\(\[\u27e6])', protected)
        return [p.replace("<DOT>.", ".").replace("<DOT>", ".").strip() for p in parts if p.strip()]

    def translate_block(self, block: ParagraphBlock) -> str:
        if block.is_protected:
            return block.text

        clean_raw = normalize_unicode_text(block.text)
        if not clean_raw or FormalismAnalyzer.is_formal_expression(clean_raw):
            block.is_standalone_math = True
            return block.text

        # Motor-etiketli anahtar: Opus-MT ile yapılmış çeviriler, LM Studio açılınca
        # kalıcı olarak cache'ten gelmesin. Tag her blokta o anki duruma göre belirlenir
        # (yedek geçişinde available False'a düşebilir).
        engine_tag = "llm" if self.lmstudio.available else "opus"
        cache_key = f"{engine_tag}|{clean_raw}"
        cached_val = self.cache.get(cache_key)
        if cached_val is not None:
            return cached_val

        has_bullet = clean_raw.startswith(("\u2022", "-", "+"))
        body = re.sub(r'^[\u2022\-\+]\s*', '', clean_raw).strip()
        body = self.registry.apply_pre_normalization(body)

        # YÖNTEM A: LM Studio (Yerel LLM) aktifse tüm paragrafı bağlamıyla çevir
        if self.lmstudio.available:
            m_txt, m_dict = FormalismAnalyzer.mask_inline_formal_tokens(body)
            llm_out = self.lmstudio.translate_masked_text(m_txt)
            if llm_out:
                restored = FormalismAnalyzer.unmask_formal_tokens(llm_out, m_dict)
                # Adli denetim: LLM maskeleri sildiyse geri ekle, ciddi eksik
                # çeviride orijinale dön (önceden ölü koddu; artık devrede).
                # Import bilinçli olarak burada: renderers→translators döngüsünü kırmak için.
                from renderers.forensic_auditor import PageForensicAuditor
                restored = PageForensicAuditor.audit_and_repair_translation(body, restored, m_dict)
                restored = self.registry.apply_post_fixes(restored)
                restored = DeterministicArtifactPurger.sanitize_stream(restored)
                result = ("\u2022 " if has_bullet else "") + restored
                result = re.sub(r'\s+', ' ', result).strip()
                self.cache.put(cache_key, result)
                return result

        # YÖNTEM B: Helsinki-NLP Opus-MT (Cümle bazlı hızlı nöral çeviri)
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
        gen_kwargs = {
            "max_length": 512,
            "num_beams": 4,
            "repetition_penalty": 1.15,
            "early_stopping": True,
        }
        if self.bad_words_ids:
            gen_kwargs["bad_words_ids"] = self.bad_words_ids

        try:
            for i in range(0, len(masked_list), batch_size):
                batch = masked_list[i:i + batch_size]
                inputs = self.tokenizer(
                    batch, return_tensors="pt", padding=True, truncation=True, max_length=512
                ).to(self.device)
                with torch.inference_mode():
                    outputs = self.model.generate(**inputs, **gen_kwargs)
                decoded_list.extend(self.tokenizer.batch_decode(outputs, skip_special_tokens=True))
        except Exception as e:
            if self.device.type == "cuda":
                print(f"[DONANIM UYARISI] GPU yurutme hatasi ({e}). Otonom CPU fallback devreye alindi.")
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
            restored = self.registry.apply_post_fixes(restored)
            restored = DeterministicArtifactPurger.sanitize_stream(restored)
            final_sents.append(restored)

        result = ("\u2022 " if has_bullet else "") + " ".join(final_sents)
        result = re.sub(r'\s+', ' ', result).strip()
        self.cache.put(cache_key, result)
        return result
