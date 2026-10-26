import json
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
