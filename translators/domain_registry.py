import re
from collections import Counter
from typing import List, Tuple
import pymupdf as fitz

# Çeviri Öncesi (Pre-Normalization) IEEE Donanım ve Bilgisayar Mühendisliği Kilitleri
ENGLISH_PRE_NORMALIZATION = [
    # 1. Don't-Care Conditions -> Farketmez durumlar
    (r"\bdon[\'\u2019`]?t[\-\s]+care\s+conditions\b", "farketmez durumlar (don't-care conditions)"),
    (r"\bdon[\'\u2019`]?t[\-\s]+care\s+condition\b", "farketmez durum (don't-care condition)"),
    (r"\bdon[\'\u2019`]?t[\-\s]+care\s+terms\b", "farketmez terimler"),
    (r"\bdon[\'\u2019`]?t[\-\s]+care\s+minterms\b", "farketmez mintermler"),
    (r"\bdon[\'\u2019`]?t[\-\s]+cares\b", "farketmez durumlar"),
    (r"\bdon[\'\u2019`]?t[\-\s]+care\b", "farketmez (don't-care)"),

    # 2. Prime Implicants -> Asal bileşenler / Asal kapsayanlar
    (r"\bessential\s+prime\s+implicants\b", "temel asal kapsayanlar (essential prime implicants)"),
    (r"\bessential\s+prime\s+implicant\b", "temel asal kapsayan (essential prime implicant)"),
    (r"\bprime\s+implicants\b", "asal kapsayanlar (asal bileşenler)"),
    (r"\bprime\s+implicant\b", "asal kapsayan (asal bileşen)"),
    (r"\bimplicants\b", "kapsayanlar (bileşenler)"),
    (r"\bimplicant\b", "kapsayan (bileşen)"),

    # 3. Sum of Products (SOP) & Product of Sums (POS)
    (r"\bsum[\-\s]+of[\-\s]+products\b", "Çarpımların Toplamı (SOP)"),
    (r"\bproduct[\-\s]+of[\-\s]+sums\b", "Toplamların Çarpımı (POS)"),
    (r"\bsum\s+of\s+minterms\b", "mintermlerin toplamı"),
    (r"\bproduct\s+of\s+maxterms\b", "makstermlerin çarpımı"),
    (r"\bproduct\s+terms\b", "çarpım terimleri"),
    (r"\bproduct\s+term\b", "çarpım terimi"),
    (r"\bsum\s+terms\b", "toplam terimleri"),
    (r"\bsum\s+term\b", "toplam terimi"),

    # 4. Port, Latch, Flip-Flop, MUX, DEMUX, FSM, Timing
    (r"\binput[\-\s]+output\s+ports\b", "giriş-çıkış portları"),
    (r"\binput\s+ports\b", "giriş portları"),
    (r"\binput\s+port\b", "giriş portu"),
    (r"\boutput\s+ports\b", "çıkış portları"),
    (r"\boutput\s+port\b", "çıkış portu"),
    (r"\bSR\s+latch\b", "SR mandal devresi (SR latch)"),
    (r"\bD\s+latch\b", "D mandal devresi (D latch)"),
    (r"\blatches\b", "mandal devreleri (latches)"),
    (r"\blatch\b", "mandal devresi (latch)"),
    (r"\bflip[\-\s]+flops\b", "flip-flop devreleri"),
    (r"\bflip[\-\s]+flop\b", "flip-flop"),
    (r"\btiming\s+diagrams\b", "zamanlama diyagramları"),
    (r"\btiming\s+diagram\b", "zamanlama diyagramı"),
    (r"\bclock\s+skew\b", "saat kayması (clock skew)"),
    (r"\bpropagation\s+delays\b", "yayılım gecikmeleri"),
    (r"\bpropagation\s+delay\b", "yayılım gecikmesi"),
    (r"\bmultiplexers\b", "çoklayıcılar (MUX)"),
    (r"\bmultiplexer\b", "çoklayıcı (MUX)"),
    (r"\bdemultiplexers\b", "ters çoklayıcılar (DEMUX)"),
    (r"\bdemultiplexer\b", "ters çoklayıcı (DEMUX)"),
    (r"\bfinite\s+state\s+machines\b", "Sonlu Durum Makineleri (FSM)"),
    (r"\bfinite\s+state\s+machine\b", "Sonlu Durum Makinesi (FSM)"),
    (r"\bstate\s+machines\b", "durum makineleri (FSM)"),
    (r"\bstate\s+machine\b", "durum makinesi (FSM)"),
    (r"\bstate\s+table\b", "durum tablosu"),
    (r"\bstate\s+diagram\b", "durum diyagramı"),
    (r"\btruth\s+table\b", "doğruluk tablosu"),
    (r"\bexcitation\s+table\b", "uyarım tablosu"),
    (r"\bcharacteristic\s+table\b", "karakteristik tablo"),
    (r"\bKarnaugh\s+map\b", "Karnaugh haritası (K-map)"),
    (r"\bK[\-\s]map\b", "K-haritası (K-map)"),
    (r"\bfan[\-\s]+out\b", "çıkış yükleme kapasitesi (fan-out)"),
    (r"\bfan[\-\s]+in\b", "giriş kapasitesi (fan-in)"),
    (r"\bnoise\s+margin\b", "gürültü payı"),
    (r"\bpower\s+dissipation\b", "güç tüketimi"),
    (r"\bthree[\-\s]+state\s+gates?\b", "üç durumlu (tri-state) kapılar"),
    (r"\btri[\-\s]+state\b", "üç durumlu (tri-state)"),

    # 5. Şekil / Tablo / Örnek / Bölüm Standartlaştırması
    (r"\bFigures?\s+(\d+(?:[\.\-]\d+)*)\b", r"Şekil \1"),
    (r"\bFig\.\s*(\d+(?:[\.\-]\d+)*)\b", r"Şekil \1"),
    (r"\bTables?\s+(\d+(?:[\.\-]\d+)*)\b", r"Tablo \1"),
    (r"\bExamples?\s+(\d+(?:[\.\-]\d+)*)\b", r"Örnek \1"),
    (r"\bSections?\s+(\d+(?:[\.\-]\d+)*)\b", r"Bölüm \1"),

    # 6. Programlama Dilleri & İkilik Aritmetik
    (r"\bContext-Free\s+Grammars\b", "Bağlamdan Bağımsız Dilbilgileri"),
    (r"\bcontext-free\s+grammars\b", "bağlamdan bağımsız dilbilgileri"),
    (r"\bContext-Free\s+Grammar\b", "Bağlamdan Bağımsız Dilbilgisi"),
    (r"\bcontext-free\s+grammar\b", "bağlamdan bağımsız dilbilgisi"),
    (r"\bDenotational\s+Semantics\b", "Gösterimsel Anlambilim"),
    (r"\bOperational\s+Semantics\b", "İşlemsel Anlambilim"),
    (r"\bAxiomatic\s+Semantics\b", "Belitsel Anlambilim"),
    (r"\bStatic\s+Semantics\b", "Statik Anlambilim"),
    (r"\bDynamic\s+Semantics\b", "Dinamik Anlambilim"),
    (r"\bAttribute\s+Grammars\b", "Öznitelik Dilbilgileri"),
    (r"\bAttribute\s+Grammar\b", "Öznitelik Dilbilgisi"),
    (r"\bImmunity\s+Debugger\b", "\u27e6INLCODE:Immunity Debugger\u27e7"),
    (r"\bVisual\s+Studio\s*\.NET\b", "\u27e6INLCODE:Visual Studio .NET\u27e7"),
    (r"\bcost\s+of\s+execution\b", "cost of program runtime"),
    (r"\bexecution\s+costs\b", "program runtime costs"),
    (r"\bfor\s+execution\b", "for running the program"),
    (r"\bat\s+compile\s+time\b", "derleme zamanında"),
    (r"\bat\s+run\s+time\b", "çalışma zamanında"),
    (r"\bsigned-([0-9a-zA-Z]+)'s-complement\b", r"signed \1's complement"),
    (r"\b([0-9a-zA-Z]+)'s-complement\b", r"\1's complement"),
    (r"\bsigned-magnitude\b", "signed magnitude"),
    (r"\bsigned-complement\b", "signed complement"),
    (r"\bend-around carry\b", "end around carry"),
]

# Çeviri Sonrası (Post-Translation) Kesin Onarım ve Gaf Temizleme Kuralları
POST_TRANSLATION_FIXES = [
    # 0. Süslü parantez ve bozuk sembol kalıntıları
    # Not: @ kuralları yalnızca boşluklu kalıntılara dokunur; e-posta adresleri
    # (user@example.com) korunur.
    (r'[\ufd3e\u27e6]', '('),
    (r'[\ufd3f\u27e7]', ')'),
    (r'(\w)\s+@\s+(\w)', r'\1-\2'),
    (r'(?<=\s)@|@(?:\s|$)', ''),

    # 1. "Don't-Care Conditions" -> "Bakım Koşulları" Gafının Kesin Onarımı
    (r'\b[Bb]akım\s+koşulları(?:nın|na|nı|ndan|nda)?\b', 'farketmez durumları'),
    (r'\b[Bb]akım\s+koşulu(?:nun|na|nu|ndan|nda)?\b', 'farketmez durumu'),
    (r'\b[Bb]akım\s+şartları(?:nın|na|nı|ndan|nda)?\b', 'farketmez durumları'),
    (r'\b[Bb]akım\s+şartı(?:nın|na|nı|ndan|nda)?\b', 'farketmez durumu'),
    (r'\b[Bb]akım\s+durumları\b', 'farketmez durumları'),
    (r'\bumursamazlık\s+koşulları\b', 'farketmez durumları'),
    (r'\bönemsenmeyen\s+koşullar\b', 'farketmez durumlar'),

    # 2. "Prime Implicants" -> "Asal İmplantlar" Gafının Kesin Onarımı
    (r'\b[Tt]emel\s+asal\s+implantlar(?:ın|a|ı|dan|da)?\b', 'temel asal kapsayanlar'),
    (r'\b[Aa]sal\s+implantlar(?:ın|a|ı|dan|da)?\b', 'asal kapsayanlar (asal bileşenler)'),
    (r'\b[Aa]sal\s+implant(?:ın|a|ı|tan|ta)?\b', 'asal kapsayan (asal bileşen)'),
    (r'\b[Bb]irincil\s+implantlar\b', 'asal kapsayanlar'),
    (r'\b[Bb]irincil\s+implant\b', 'asal kapsayan'),
    (r'\bimplantlar\b', 'kapsayanlar (bileşenler)'),
    (r'\bimplant\b', 'kapsayan (bileşen)'),

    # 3. "Sum of Products (SOP)" -> "Ürünlerin Toplamı" Gafının Kesin Onarımı
    (r'\b[Üü]rünlerin\s+[Tt]oplamı\b', 'Çarpımların Toplamı'),
    (r'\b[Üü]rün\s+toplamı\b', 'Çarpımların toplamı'),
    (r'\b[Tt]oplamların\s+[Üü]rünü\b', 'Toplamların Çarpımı'),
    (r'\b[Üü]rün\s+terimleri(?:nin|ne|ni|nden|nde)?\b', 'çarpım terimleri'),
    (r'\b[Üü]rün\s+terimi(?:nin|ne|ni|nden|nde)?\b', 'çarpım terimi'),

    # 4. "Port" -> "Liman" Gafının Kesin Onarımı
    (r'\bgiriş[\-\s]*çıkış\s+limanları\b', 'giriş-çıkış portları'),
    (r'\bgiriş\s+limanları\b', 'giriş portları'),
    (r'\bgiriş\s+limanı\b', 'giriş portu'),
    (r'\bçıkış\s+limanları\b', 'çıkış portları'),
    (r'\bçıkış\s+limanı\b', 'çıkış portu'),
    (r'\bvarlığın\s+limanı\b', 'varlığın (entity) portu'),
    (r'\b[Ll]imanların\b', 'portların'),
    (r'\b[Ll]imanlara\b', 'portlara'),
    (r'\b[Ll]imanları\b', 'portları'),
    (r'\b[Ll]imanlar\b', 'portlar'),
    (r'\b[Ll]imanın\b', 'portun'),
    (r'\b[Ll]imana\b', 'porta'),
    (r'\b[Ll]imanı\b', 'portu'),
    (r'\b[Ll]imanda\b', 'portta'),
    (r'\b[Ll]imandan\b', 'porttan'),
    (r'\b[Ll]iman\b', 'port'),

    # 5. "Latch" -> "Mandal" & "Figure" -> "Figür" Onarımları
    (r'\bSR\s+mandalı\b', 'SR mandal devresi (SR latch)'),
    (r'\bD\s+mandalı\b', 'D mandal devresi (D latch)'),
    (r'\bmandal\s+devresi\s+\(latch\)\s+devresi\b', 'mandal devresi (latch)'),
    (r'\b[Ff]igür\s+(\d+(?:[\.\-]\d+)*)\b', r'Şekil \1'),
    (r'\b[Bb]ölüm\s+Bölüm\s+(\d+)\b', r'Bölüm \1'),
    (r'\b[Şş]ekil\s+Şekil\s+(\d+)\b', r'Şekil \1'),

    # 6. Diğer Akademik Terim Düzeltmeleri
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

# Maskeli-faz onarımları: yalnızca maskeler (⟦CODE_n⟧/⟦MTH_n⟧) yerindeyken,
# yani unmask'ten ÖNCE uygulanır; geri çözülen gerçek matematik değerlerine
# ("n > s", "x != y" gibi) asla dokunmazlar. Bu yüzden apply_post_fixes'te
# (cache.get yolu dâhil) bulunmazlar.
POST_FIXES_ON_MASKED_TEXT = [
    (r'\b([0-9a-zA-Z]+)\s*>\s*s\b', r"\1'e"),  # "n > s" -> "n'e" (yalnızca maskeli faz)
    (r'!=', '\u2260'),  # "a != b" -> "a ≠ b" (yalnızca maskeli faz)
]


class DynamicAcademicRegistry:
    DOMAIN_SIGNATURES = {
        "digital_electronics": {
            "label": "Sayısal Tasarım ve Donanım Mühendisliği (IEEE)",
            "keywords": {
                "vhdl", "verilog", "flip-flop", "karnaugh", "minterm", "maxterm",
                "cmos", "nand", "multiplexer", "implicant", "latch", "boolean"
            },
            "polysemy_locks": [
                (r"\bessential\s+prime\s+implicants\b", "temel asal kapsayanlar (essential prime implicants)"),
                (r"\bprime\s+implicants\b", "asal kapsayanlar (asal bileşenler)"),
                (r"\bprime\s+implicant\b", "asal kapsayan (asal bileşen)"),
                (r"\bdon[\'\u2019`]?t[\-\s]+care\s+conditions?\b", "farketmez (don't-care) durumları"),
                (r"\bdon[\'\u2019`]?t[\-\s]+cares?\b", "farketmez (don't-care) durumları"),
                (r"\bsum[\-\s]+of[\-\s]+products\b", "Çarpımların Toplamı (SOP)"),
                (r"\bproduct[\-\s]+of[\-\s]+sums\b", "Toplamların Çarpımı (POS)"),
                (r"\bproduct\s+terms?\b", "çarpım terimleri"),
                (r"\bsum\s+terms?\b", "toplam terimleri"),
                (r"\bpropagation\s+delay\b", "yayılım gecikmesi"),
                (r"\bclock\s+skew\b", "saat kayması"),
                (r"\btiming\s+diagram\b", "zamanlama diyagramı"),
                (r"\bfan[\-\s]+out\b", "çıkış yükleme kapasitesi (fan-out)"),
                (r"\bfan[\-\s]+in\b", "giriş kapasitesi (fan-in)"),
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
        },
        "medicine": {
            "label": "Tıp ve Sağlık Bilimleri",
            "keywords": {
                "myocardial", "anatomy", "physiology", "pathology", "diagnosis",
                "symptom", "symptoms", "treatment", "patient", "patients",
                "clinical", "pharmacology", "lesion", "artery", "therapy"
            },
            "polysemy_locks": [
                (r"\bmyocardial\s+infarction\b", "miyokard enfarktüsü (myocardial infarction)"),
                (r"\bheart\s+attack\b", "kalp krizi (heart attack)"),
                (r"\bcerebrovascular\s+accident\b", "serebrovasküler olay / inme (CVA)"),
                (r"\bcommon\s+cold\b", "nezle (soğuk algınlığı)"),
                (r"\bhigh\s+blood\s+pressure\b", "yüksek tansiyon (hipertansiyon)"),
                (r"\bshortness\s+of\s+breath\b", "nefes darlığı"),
                (r"\bside\s+effects\b", "yan etkiler"),
            ]
        },
        "law": {
            "label": "Hukuk",
            "keywords": {
                "plaintiff", "defendant", "jurisdiction", "tort", "statute",
                "precedent", "liability", "negligence", "indemnify", "tortfeasor"
            },
            "polysemy_locks": [
                (r"\bplaintiffs?\b", "davacı (plaintiff)"),
                (r"\bdefendants?\b", "davalı (defendant)"),
                (r"\bburden\s+of\s+proof\b", "ispat yükü (burden of proof)"),
                (r"\bstare\s+decisis\b", "içtihat istikrarı (stare decisis)"),
                (r"\bforce\s+majeure\b", "mücbir sebep (force majeure)"),
                (r"\bintellectual\s+property\b", "fikri mülkiyet (intellectual property)"),
                (r"\bpower\s+of\s+attorney\b", "vekaletname (power of attorney)"),
                (r"\btorts?\b", "haksız fiil (tort)"),
            ]
        },
        "economics": {
            "label": "İktisat ve Finans",
            "keywords": {
                "inflation", "elasticity", "monopoly", "oligopoly", "gdp",
                "macroeconomic", "microeconomic", "fiscal", "monetary",
                "surplus", "utility", "equilibrium"
            },
            "polysemy_locks": [
                (r"\bsupply\s+and\s+demand\b", "arz ve talep (supply and demand)"),
                (r"\bopportunity\s+cost\b", "fırsat maliyeti (opportunity cost)"),
                (r"\bgross\s+domestic\s+product\b", "gayri safi yurtiçi hasıla (GSYH)"),
                (r"\bcomparative\s+advantage\b", "kıyaslı üstünlük (comparative advantage)"),
                (r"\bconsumer\s+surplus\b", "tüketici rantı (consumer surplus)"),
                (r"\belasticity\s+of\s+demand\b", "talebin esnekliği"),
                (r"\bmonetary\s+policy\b", "para politikası (monetary policy)"),
                (r"\bfiscal\s+policy\b", "maliye politikası (fiscal policy)"),
                (r"\blaw\s+of\s+diminishing\s+(?:marginal\s+)?returns\b", "azalan getiri yasası"),
            ]
        },
    }

    def __init__(self):
        self.active_domains: List[str] = []
        self.active_label: str = "Bilgisayar ve Donanım Mühendisliği (IEEE)"
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

        print(f"[ALAN PROFILI] Algilanan Kitap Disiplini: {self.active_label} ({len(self.active_locks)} ozel alan kilidi aktif)")

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

    @staticmethod
    def apply_masked_phase_fixes(text: str) -> str:
        """Maskeli-faz onarımları: yalnızca maskeler (⟦CODE_n⟧/⟦MTH_n⟧) metinde
        yerindeyken, unmask'ten önce çağrılmalı; geri çözülecek gerçek matematik
        değerleri korunur."""
        res = text
        for pat_s, repl_s in POST_FIXES_ON_MASKED_TEXT:
            res = re.sub(pat_s, repl_s, res)
        return res
