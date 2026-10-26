import os
import py_compile

FILES = {}

# 1. TRANSLATORS PAKET BAŞLATICI
FILES["translators/__init__.py"] = r'''from .cache_manager import SelfHealingCache, CACHE_VERSION
from .domain_registry import DynamicAcademicRegistry
from .lmstudio_backend import LMStudioBackend
from .marian_backend import UniversalTranslationEngine
'''

# 2. KENDİ KENDİNİ ONARAN ÖNBELLEK (SELF-HEALING CACHE)
FILES["translators/cache_manager.py"] = r'''import os
import re
import json
from typing import Dict, Optional

CACHE_VERSION = "v18.0_modular_dual_engine"


class SelfHealingCache:
    """
    Eski denemelerden kalan çözülmemiş maskeleri (CODE_0, MTH_0, ⟦, ⟧, ﴾, ﴿)
    otomatik olarak ayıklayan ve temiz çevirileri koruyan JSON önbellek motoru.
    """
    CONTAMINATION_RE = re.compile(r'(?:CODE_\d+|MTH_\d+|\u27e6|\u27e7|\ufd3e|\ufd3f)')

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
            for k, v in loaded.items():
                if k == "__version__" or not isinstance(v, str):
                    continue
                if self.CONTAMINATION_RE.search(v):
                    purged += 1
                else:
                    clean_cache[k] = v

            self.data = clean_cache
            print(
                f"[ONBELLEK] {len(self.data) - 1} temiz ceviri yuklendi "
                f"({purged} kirli maske kaydi otomatik temizlendi)."
            )
            if purged > 0:
                self.save()
        except Exception as exc:
            print(f"[ONBELLEK UYARISI] Onbellek sifirlandi: {exc}")

    def get(self, key: str) -> Optional[str]:
        return self.data.get(key)

    def put(self, key: str, value: str) -> None:
        if not self.CONTAMINATION_RE.search(value):
            self.data[key] = value

    def save(self) -> bool:
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
'''

# 3. DİNAMİK AKADEMİK ALAN KAYITÇISI (DYNAMIC ACADEMIC REGISTRY)
FILES["translators/domain_registry.py"] = r'''import re
from collections import Counter
from typing import List, Tuple
import pymupdf as fitz

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
    (r'\bImmunity\s+Debugger\b', '\u27e6INLCODE:Immunity Debugger\u27e7'),
    (r'\bVisual\s+Studio\s*\.NET\b', '\u27e6INLCODE:Visual Studio .NET\u27e7'),
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
    """
    Kitabın ilk sayfalarını tarayarak baskın akademik disiplini (Sayısal Tasarım,
    Programlama Dilleri, Siber Güvenlik vb.) tespit eder ve çok anlamlı terimleri kilitler.
    """
    DOMAIN_SIGNATURES = {
        "digital_electronics": {
            "label": "Sayısal Tasarım ve Elektronik Mühendisliği",
            "keywords": {
                "vhdl", "verilog", "flip-flop", "karnaugh", "minterm", "maxterm",
                "cmos", "nand", "multiplexer", "implicant", "latch", "boolean"
            },
            "polysemy_locks": [
                (r"\bessential\s+prime\s+implicants\b", "temel asal çarpan terimleri (essential prime implicants)"),
                (r"\bprime\s+implicants\b", "asal çarpan terimleri (prime implicants)"),
                (r"\bprime\s+implicant\b", "asal çarpan terimi (prime implicant)"),
                (r"\bdon't-care\s+conditions?\b", "fark etmez (don't-care) durumları"),
                (r"\bdon't\s+care\s+conditions?\b", "fark etmez (don't-care) durumları"),
                (r"\bdon't-cares?\b", "fark etmez (don't-care) terimleri"),
                (r"\bsum-of-products\b", "çarpımların toplamı (SOP)"),
                (r"\bproduct-of-sums\b", "toplamların çarpımı (POS)"),
                (r"\bproduct\s+terms?\b", "çarpım terimleri"),
                (r"\bsum\s+terms?\b", "toplam terimleri"),
                (r"\bpropagation\s+delay\b", "yayılma gecikmesi"),
                (r"\bfan-out\b", "çıkış yükleme kapasitesi (fan-out)"),
                (r"\bfan-in\b", "giriş kapasitesi (fan-in)"),
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
        self.active_label: str = "Bilgisayar Mühendisliği ve Akademik Bilimler"
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

        print(f"[ALAN PROFILI] Algilanan Kitap Disiplini: {self.active_label} ({len(self.active_locks)} terim kilidi aktif)")

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

# 4. LM STUDIO (YEREL LLM) ÇEVİRİ MOTORU
FILES["translators/lmstudio_backend.py"] = r'''import json
import urllib.request
from typing import Optional


class LMStudioBackend:
    """
    LM Studio (http://localhost:1234/v1) uzerinde calisan yerel LLM modelleriyle
    (Qwen-2.5/3, Gemma-3, DeepSeek, Llama-3 vb.) yuksek dogruluklu akademik ceviri yapar.
    """
    def __init__(self, base_url: str = "http://localhost:1234/v1", domain_label: str = "Bilgisayar Mühendisliği"):
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
            f"Sen kıdemli bir {self.domain_label} profesörü ve teknik kitap çevirmenisin. "
            "Verilen İngilizce metni kusursuz, akıcı ve akademik bir Türkçeye çevir.\n"
            "KESİN KURALLAR:\n"
            "1) Metin içindeki ⟦CODE_0⟧, ⟦CODE_1⟧, ⟦MTH_0⟧ gibi maskeleri ASLA silme, değiştirme veya çevirme; "
            "Türkçe cümlenin doğru yerine aynen koy.\n"
            "2) Sadece çevrilmiş Türkçe metni döndür; hiçbir açıklama veya not ekleme."
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

# 5. ANA ÇEVİRİ ORKESTRATÖRÜ (OPUS-MT + LM STUDIO + SELF-HEALING CACHE)
FILES["translators/marian_backend.py"] = r'''import os
import re
from typing import List, Dict
import torch
import pymupdf as fitz

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

        cached_val = self.cache.get(clean_raw)
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
                restored = self.registry.apply_post_fixes(restored)
                restored = DeterministicArtifactPurger.sanitize_stream(restored)
                result = ("\u2022 " if has_bullet else "") + restored
                result = re.sub(r'\s+', ' ', result).strip()
                self.cache.put(clean_raw, result)
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
        self.cache.put(clean_raw, result)
        return result
'''


def main():
    os.makedirs("translators", exist_ok=True)
    os.makedirs("build", exist_ok=True)

    for rel_path, content in FILES.items():
        with open(rel_path, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))
        if rel_path.endswith(".py"):
            py_compile.compile(rel_path, doraise=True)
        print(f"  [OK] Olusturuldu ve dogrulandi: {rel_path}")

    print("\n========================================================")
    print("[ADIM 2 TAMAMLANDI] Translators (LM Studio + Opus-MT) paketi hazir!")
    print("Simdi bana '2. adim tamam' yaz, son adima (Adim 3) gecelim.")
    print("========================================================")


if __name__ == "__main__":
    main()