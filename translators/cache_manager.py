import os
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
            # Kompakt JSON: save her sayfada çağrıldığı için indent gereksiz şişme yaratır.
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            return True
        except Exception:
            return False
