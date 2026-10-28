"""extractors/formalism.py kod/formül karantinası testleri."""
from extractors.formalism import FormalismAnalyzer, UniversalFormalismQuarantine

CLEARLY_CODE_LINES = [
    "library ieee;",
    "use ieee.std_logic_1164.all;",
    "entity counter is",
    "architecture behavioral of counter is",
    "signal q_reg : std_logic_vector(7 downto 0);",
    "process(clk, rst_n)",
    "end process;",
    "module alu(input [7:0] a, output reg [7:0] y);",
    "always @(posedge clk) begin",
    "assign y = a & b;",
    "endmodule",
    "$ nmap -sS target_host",
    "[*] Sending payload to target_port 4444",
    "#define BUFFER_SIZE 1024",
    "int main(int argc, char *argv[]) {",
    "mov eax, 0x10",
    "push ebp",
    "Q_next <= D_in;",
]

CLEARLY_PROSE_LINES = [
    "The multiplexer selects one of the four data inputs based on the select signal.",
    "Prime implicants cover all the minterms of the function.",
    "out of the in the to the is a such as",
]


def test_code_lines_are_quarantined():
    for line in CLEARLY_CODE_LINES:
        assert FormalismAnalyzer.is_code_line_syntax(line), f"kod sayılmalı: {line!r}"


def test_prose_lines_are_never_quarantined():
    for line in CLEARLY_PROSE_LINES:
        assert not FormalismAnalyzer.is_code_line_syntax(line), f"prose sayılmalı: {line!r}"


def test_prose_lock_detects_option_lines():
    assert UniversalFormalismQuarantine.is_natural_prose_or_option_line(
        "Description : Connects back to the handler"
    )
    assert UniversalFormalismQuarantine.is_natural_prose_or_option_line("Name : reverse_tcp")


def test_monospace_font_detection():
    assert FormalismAnalyzer.is_monospace_span("Courier", 0)
    assert FormalismAnalyzer.is_monospace_span("Arial", 8)  # flags & 8
    assert not FormalismAnalyzer.is_monospace_span("Times New Roman", 0)


def test_header_footer_zones():
    from extractors.formalism import FormalismAnalyzer as FA
    from core.models import BoundingBox

    top_chapter = BoundingBox(40.0, 20.0, 300.0, 34.0)
    assert FA.is_header_or_footer("Chapter 3", top_chapter, 792.0)
    page_number = BoundingBox(500.0, 740.0, 540.0, 754.0)
    assert FA.is_header_or_footer("42", page_number, 792.0)
    copyright_line = BoundingBox(40.0, 750.0, 400.0, 764.0)
    assert FA.is_header_or_footer("Copyright © 2015 Elsevier Inc. All rights reserved.", copyright_line, 792.0)
    body_line = BoundingBox(40.0, 400.0, 500.0, 414.0)
    assert not FA.is_header_or_footer("random long body line that sits in the middle", body_line, 792.0)


def test_mask_unmask_roundtrip_restores_code_tokens():
    sentence = "The buffer uses std_logic_vector(7 downto 0) port."
    masked, masks = FormalismAnalyzer.mask_inline_formal_tokens(sentence)
    assert "CODE_" in masked and "std_logic_vector" not in masked

    fake_translation = "çeviri " + masked + " son"
    restored = FormalismAnalyzer.unmask_formal_tokens(fake_translation, masks)
    assert "std_logic_vector(7 downto 0)" in restored
    assert "buffer" in restored
    assert "CODE_" not in restored


def test_markov_quarantine_keeps_prose_locked():
    lines = [
        {"text": "signal q : std_logic;", "bbox": (60.0, 100.0, 300.0, 112.0), "is_code": True, "is_hdr_ftr": False},
        {"text": "q <= d;", "bbox": (70.0, 116.0, 200.0, 128.0), "is_code": False, "is_hdr_ftr": False},
        {
            "text": "The counter increments on each rising edge of the clock signal.",
            "bbox": (60.0, 160.0, 480.0, 196.0),
            "is_code": False,
            "is_hdr_ftr": False,
        },
    ]
    result = UniversalFormalismQuarantine.apply_spatial_markov_quarantine(lines, 50.0, 545.0)
    prose_line = result[2]
    assert not prose_line["is_code"]


def test_formal_expression_classification():
    assert FormalismAnalyzer.is_formal_expression("F = A + B*C")
    assert not FormalismAnalyzer.is_formal_expression(
        "This section describes the propagation delay of the circuit."
    )
