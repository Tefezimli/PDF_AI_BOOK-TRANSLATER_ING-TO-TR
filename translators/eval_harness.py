"""Çeviri kalitesi değerlendirme seti (`pdfai-translate --eval`).

İki mod:
- Offline (varsayılan): deterministik zinciri sınar — ön-normalizasyon →
  maskele → (LLM yerine birebir dönüş) → maske çöz → son-onarım → temizle.
  Terminoloji kilitleri, gaf onarımları ve maske sadakati burada kanıtlanır;
  LLM gerekmez.
- Canlı (LM Studio erişilebilirse): aynı altın cümleler gerçek yerel LLM'e
  gönderilir; maske kalıntısı, yasak terim ve uzunluk oranı denetlenir.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from core.unicode_sanitizer import DeterministicArtifactPurger
from extractors.formalism import FormalismAnalyzer
from translators.domain_registry import DynamicAcademicRegistry

# Altın durumlar: boru hattından geçtikten sonra beklenen içerik/yasaklar.
# "gaf" tipi vakalar girdi olarak bilinen YANLIŞ Türkçeyi taşır ve son-onarım
# kurallarının bunu iyileştirdiğini kanıtlar.
GOLDEN_CASES = [
    {
        "id": "dont-care",
        "input": "The don't-care conditions simplify the Karnaugh map.",
        "must_contain": ["farketmez"],
        "forbidden": ["bakım", "Bakım"],
    },
    {
        "id": "prime-implicant",
        "input": "Essential prime implicants cover every minterm of the function.",
        "must_contain": ["asal kapsayan"],
        "forbidden": ["implant"],
    },
    {
        "id": "sop",
        "input": "The sum of products form is implemented with AND-OR gates.",
        "must_contain": ["Çarpımların Toplamı"],
        "forbidden": ["Ürünlerin"],
    },
    {
        "id": "pos",
        "input": "A product of sums expression uses OR gates followed by an AND gate.",
        "must_contain": ["Toplamların Çarpımı"],
        "forbidden": ["Ürünü"],
    },
    {
        "id": "gaf-bakim",
        "input": "Bakım koşulları tabloda X ile gösterilir.",
        "must_contain": ["farketmez"],
        "forbidden": ["Bakım"],
    },
    {
        "id": "gaf-liman",
        "input": "Varlığın limanı giriş yönünde tanımlıdır.",
        "must_contain": ["port"],
        "forbidden": ["liman"],
    },
    {
        "id": "figure",
        "input": "Fig. 3.2 shows the timing diagram of the SR latch.",
        "must_contain": ["Şekil 3.2", "mandal"],
        "forbidden": ["Figür"],
    },
    {
        "id": "flipflop",
        "input": "Edge-triggered flip-flops sample the input on the clock edge.",
        "must_contain": ["flip-flop"],
        "forbidden": [],
    },
    {
        "id": "mask-roundtrip",
        "input": "The buffer uses std_logic_vector(7 downto 0) at the output port.",
        "must_contain": ["std_logic_vector(7 downto 0)", "buffer"],
        "forbidden": ["CODE_", "MTH_"],
    },
    {
        "id": "complement-heal",
        "input": "İşaret-büyüklük ve 2's complement gösterimleri karşılaştırılır.",
        "must_contain": ["tümleyen"],
        "forbidden": ["tamamlayıcı"],
    },
    {
        "id": "complement-stability",
        "input": "The two's complement of 0101 is 1011.",
        "must_contain": ["two's complement"],
        "forbidden": ["tamamlayıcı", "tamamlama"],
    },
    {
        "id": "sanitize-brackets",
        "input": "Değer ﴾x﴿ parantez içinde kalmalı.",
        "must_contain": ["(x)"],
        "forbidden": ["﴾", "﴿"],
    },
]


def offline_transform(text: str) -> str:
    """Deterministik zincir: LLM adımı birebir dönüş olarak simüle edilir."""
    registry = DynamicAcademicRegistry()
    body = registry.apply_pre_normalization(text)
    masked, masks = FormalismAnalyzer.mask_inline_formal_tokens(body)
    # Gerçek boru hattı gibi: maskeli-faz onarımları unmask'ten ÖNCE uygulanır.
    masked = DynamicAcademicRegistry.apply_masked_phase_fixes(masked)
    restored = FormalismAnalyzer.unmask_formal_tokens(masked, masks)
    restored = DynamicAcademicRegistry.apply_post_fixes(restored)
    return DeterministicArtifactPurger.sanitize_stream(restored)


def _check_case(case: dict, output: str) -> List[str]:
    problems = []
    for needle in case.get("must_contain", []):
        if needle not in output:
            problems.append(f"beklenen bulunamadi: {needle!r}")
    for banned in case.get("forbidden", []):
        if banned in output:
            problems.append(f"yasak terim ortaya cikti: {banned!r}")
    return problems


def run_eval(
    live: bool = False,
    print_fn: Callable[[str], None] = print,
    cases: Optional[List[dict]] = None,
) -> Tuple[int, int]:
    """(geçen, toplam) döner. live=True ve LM Studio açıksa canlı LLM sınanır."""
    cases = cases if cases is not None else GOLDEN_CASES
    registry = DynamicAcademicRegistry()
    llm = None
    if live:
        from translators.lmstudio_backend import LMStudioBackend
        llm = LMStudioBackend()
        if not llm.available:
            llm = None
            print_fn("[EVAL] LM Studio erisilemiyor; yalnizca cevrimdisi zincir sinanacak.")

    passed = 0
    mode = "CANLI LLM" if llm else "OFFLINE"
    print_fn(f"==================== CEVIRI KALITE EVALUASYONU ({mode}) ====================")
    for case in cases:
        try:
            if llm is not None:
                body = registry.apply_pre_normalization(case["input"])
                masked, masks = FormalismAnalyzer.mask_inline_formal_tokens(body)
                llm_out = llm.translate_masked_text(masked)
                if not llm_out:
                    print_fn(f"  [FAIL] {case['id']}: LLM bos yanit dondu")
                    continue
                # Gerçek motor gibi: maskeli-faz onarımları unmask'ten önce.
                llm_out = DynamicAcademicRegistry.apply_masked_phase_fixes(llm_out)
                output = DeterministicArtifactPurger.sanitize_stream(
                    DynamicAcademicRegistry.apply_post_fixes(
                        FormalismAnalyzer.unmask_formal_tokens(llm_out, masks)
                    )
                )
                ratio = len(output) / max(1, len(case["input"]))
                if not (0.4 <= ratio <= 3.0):
                    print_fn(f"  [FAIL] {case['id']}: uzunluk orani bozuk ({ratio:.2f})")
                    continue
            else:
                output = offline_transform(case["input"])
            problems = _check_case(case, output)
            if problems:
                print_fn(f"  [FAIL] {case['id']}: {'; '.join(problems)}")
                print_fn(f"         cikti: {output[:160]}")
            else:
                passed += 1
                print_fn(f"  [ OK ] {case['id']}")
        except Exception as exc:
            print_fn(f"  [FAIL] {case['id']}: istisna: {exc}")

    total = len(cases)
    print_fn("===========================================================================")
    print_fn(f"  SONUC: {passed}/{total} vaka gecti")
    return passed, total
