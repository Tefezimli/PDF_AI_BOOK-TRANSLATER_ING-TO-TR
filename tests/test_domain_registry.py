"""Yeni alan disiplinlerinin (tıp/hukuk/iktisat) profil ve kilit testleri."""
import pymupdf as fitz

from translators.domain_registry import DynamicAcademicRegistry


def make_pdf(pages_text):
    doc = fitz.open()
    for txt in pages_text:
        page = doc.new_page()
        page.insert_text((72, 100), txt)
    return doc


def test_medicine_domain_profiled_and_locked():
    doc = make_pdf([
        "The patient presents with shortness of breath and clinical symptoms. "
        "Diagnosis confirmed the myocardial infarction. Treatment and therapy follow. "
        "Patient history and pathology of the artery lesion were reviewed."
    ] * 3)
    reg = DynamicAcademicRegistry()
    reg.profile_document(doc)
    doc.close()

    assert reg.active_label.startswith("Tıp")
    out = reg.apply_pre_normalization("The patient suffered a myocardial infarction after a common cold.")
    assert "miyokard enfarktüsü" in out
    assert "nezle" in out


def test_law_domain_profiled_and_locked():
    doc = make_pdf([
        "The plaintiff filed against the defendant in this jurisdiction. "
        "The tort of negligence and statutory liability define the precedent. "
        "Burden of proof rests with the plaintiff; the defendant claims force majeure."
    ] * 3)
    reg = DynamicAcademicRegistry()
    reg.profile_document(doc)
    doc.close()

    assert reg.active_label.startswith("Hukuk")
    out = reg.apply_pre_normalization("The plaintiff proved the tort and the power of attorney.")
    assert "davacı" in out
    assert "haksız fiil" in out
    assert "vekaletname" in out


def test_economics_domain_profiled_and_locked():
    doc = make_pdf([
        "Inflation and the elasticity of demand shape the equilibrium. "
        "Monetary policy versus fiscal policy: the supply and demand of money. "
        "Opportunity cost, consumer surplus and comparative advantage in a monopoly."
    ] * 3)
    reg = DynamicAcademicRegistry()
    reg.profile_document(doc)
    doc.close()

    assert reg.active_label.startswith("İktisat")
    out = reg.apply_pre_normalization("Gross domestic product reflects the opportunity cost of the monetary policy.")
    assert "gayri safi yurtiçi hasıla" in out
    assert "fırsat maliyeti" in out
    assert "para politikası" in out


def test_engineering_book_still_profiles_first():
    doc = make_pdf([
        "The VHDL entity uses std_logic and karnaugh maps. "
        "Flip-flop and minterm minimization with multiplexer circuits. "
        "NAND gate propagation delay and the timing diagram."
    ] * 3)
    reg = DynamicAcademicRegistry()
    reg.profile_document(doc)
    doc.close()
    assert "Sayısal Tasarım" in reg.active_label or "Donanım" in reg.active_label


def test_unprofiled_registry_does_not_apply_domain_locks():
    # Profil çıkarılmadan kilitler devrede olmamalı (mühendislik kitabı yanlışlıkla
    # tıp kilidine girip metni değiştirmemeli).
    reg = DynamicAcademicRegistry()
    out = reg.apply_pre_normalization("The plaintiff appeared in court.")
    assert out == "The plaintiff appeared in court."
