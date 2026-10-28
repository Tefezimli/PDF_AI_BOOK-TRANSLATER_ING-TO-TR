import json
import os
import urllib.request
from typing import List, Optional

DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_CHECK_TIMEOUT = 2.0
DEFAULT_REQUEST_TIMEOUT = 45.0
DEFAULT_ATTEMPTS = 1


def _resolve_base_url(explicit: Optional[str]) -> str:
    """Öncelik: açık parametre > PDF_AI_LMSTUDIO_URL > PDF_AI_LMSTUDIO_PORT > varsayılan."""
    if explicit:
        return explicit.rstrip("/")
    env_url = os.environ.get("PDF_AI_LMSTUDIO_URL")
    if env_url:
        return env_url.rstrip("/")
    env_port = os.environ.get("PDF_AI_LMSTUDIO_PORT")
    if env_port:
        return f"http://localhost:{env_port}/v1"
    return DEFAULT_BASE_URL


def _env_float(env_key: str, default: float) -> float:
    raw = os.environ.get(env_key)
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError:
        return default


def _env_int(env_key: str, default: int) -> int:
    raw = os.environ.get(env_key)
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


class LMStudioBackend:
    """Yerel LM Studio (OpenAPI uyumlu) sunucusunun istemcisi.

    Ortam değişkenleriyle yapılandırılabilir:
      - PDF_AI_LMSTUDIO_URL     tam adres (örn. http://localhost:1234/v1)
      - PDF_AI_LMSTUDIO_PORT    sadece port (varsayılan 1234)
      - PDF_AI_LMSTUDIO_MODEL   sunucu birden çok model yüklüyse tercih (alt dizi eşleşmesi)
      - PDF_AI_LMSTUDIO_TIMEOUT        üretim (chat) zaman aşımı sn [45]
      - PDF_AI_LMSTUDIO_CHECK_TIMEOUT   sunucu algılama zaman aşımı sn [2]
      - PDF_AI_LMSTUDIO_ATTEMPTS        blok başına deneme sayısı [1]
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        domain_label: str = "Bilgisayar ve Donanım Mühendisliği",
        check_timeout: Optional[float] = None,
        request_timeout: Optional[float] = None,
        max_attempts: Optional[int] = None,
    ):
        self.base_url = _resolve_base_url(base_url)
        self.domain_label = domain_label
        self.preferred_model: Optional[str] = os.environ.get("PDF_AI_LMSTUDIO_MODEL") or None
        self.check_timeout = check_timeout if check_timeout else _env_float("PDF_AI_LMSTUDIO_CHECK_TIMEOUT", DEFAULT_CHECK_TIMEOUT)
        self.request_timeout = request_timeout if request_timeout else _env_float("PDF_AI_LMSTUDIO_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)
        self.max_attempts = max_attempts if max_attempts else _env_int("PDF_AI_LMSTUDIO_ATTEMPTS", DEFAULT_ATTEMPTS)
        self.model_id: Optional[str] = None
        self.available: bool = self._check_server()

    def _pick_model(self, models: List[dict]) -> str:
        if self.preferred_model:
            needle = self.preferred_model.lower()
            for m in models:
                mid = str(m.get("id", ""))
                if needle in mid.lower():
                    return mid
        return models[0].get("id", "local-model")

    def _check_server(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/models", method="GET")
            with urllib.request.urlopen(req, timeout=self.check_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("data", [])
                if models:
                    self.model_id = self._pick_model(models)
                    print(f"[LM STUDIO AKTIF] Yerel LLM Sunucusu Algilandi ({self.base_url})! Aktif Model: {self.model_id}")
                    return True
        except Exception:
            pass
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
            # Girdiye göre ölçekle: uzun paragrafta sabit 1024 token yanıtı ortadan keser.
            "max_tokens": max(1024, min(4096, int(len(masked_text) * 0.6) + 256)),
            "stream": False
        }

        last_error: Optional[Exception | str] = None
        for _ in range(self.max_attempts):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    choice = result["choices"][0]
                    content = choice["message"]["content"].strip()
                    if content:
                        finish = choice.get("finish_reason")
                        if finish == "length":
                            # İçerik dolu olsa bile uzunluk sınırında kesik demektir;
                            # kesik metni geçerli sanma, denemeye devam et.
                            last_error = "yanit uzunluk sinirinda kesildi (finish_reason=length)"
                        else:
                            return content
            except Exception as exc:
                last_error = exc

        print(f"[LM STUDIO UYARISI] Yerel LLM yanit vermedi ({last_error}), Opus-MT yedegine geciliyor...")
        self.available = False
        return None
