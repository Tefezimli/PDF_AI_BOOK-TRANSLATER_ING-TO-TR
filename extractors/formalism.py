import re
from typing import Tuple, Dict, List, Any
from core.models import BoundingBox
from core.unicode_sanitizer import normalize_unicode_text

MONOSPACE_FONT_KEYWORDS = (
    "courier", "consolas", "inconsolata", "menlo",
    "source code", "sourcecode", "fira code", "firacode",
    "cascadia", "typewriter", "cmtt", "lucida console",
    "dejavusansmono", "liberationsansmono", "txtt", "zi4"
)

ENGLISH_FUNCTION_WORDS = {
    "the", "a", "an", "of", "to", "in", "is", "are", "was", "were", "for", "with",
    "that", "by", "on", "as", "can", "be", "from", "which", "or", "and", "not",
    "this", "these", "those", "have", "has", "had", "but", "at", "their", "its",
    "into", "between", "through", "during", "before", "after", "above", "below",
    "more", "most", "some", "such", "no", "nor", "only", "own", "same", "so",
    "than", "too", "very", "will", "would", "should", "could", "may", "might",
    "must", "when", "where", "how", "why", "who", "whom", "whose", "you", "your",
    "we", "our", "us", "they", "them", "he", "she", "it", "if", "because", "while",
    "although", "though", "since", "until", "unless", "about", "over", "under",
    "again", "further", "then", "once", "here", "there", "all", "any", "both",
    "each", "few", "other", "another", "every", "either", "neither"
}

KNOWN_CODE_EXTENSIONS = {
    "py", "c", "cpp", "h", "hpp", "sh", "bash", "exe", "dll", "so", "dylib",
    "rb", "js", "ts", "java", "cs", "go", "rs", "php", "pl", "sql", "asm",
    "s", "o", "obj", "bin", "dat", "json", "xml", "yaml", "yml", "ini", "cfg",
    "conf", "log", "txt", "pcap", "jar", "war", "ps1", "bat", "cmd", "vbs",
    "vhd", "vhdl", "v", "sv", "all", "std_logic_1164", "numeric_std"
}

INLINE_CODE_EXACT_TOKENS = {
    "target_host", "target_port", "bind_ip", "bind_port", "client_socket",
    "server_loop", "client_handler", "handle_client", "buffer", "argc",
    "argv", "argv[]", "envp", "sys.exit", "stdin", "stdout", "stderr",
    "sockaddr", "sockaddr_in", "AF_INET", "SOCK_STREAM", "SOCK_DGRAM",
    "SOL_SOCKET", "SO_REUSEADDR", "O_RDONLY", "O_WRONLY", "O_RDWR",
    "NULL", "EOF", "TRUE", "FALSE", "None", "True", "False", "self",
    "__init__", "__main__", "__name__", "malloc", "calloc", "realloc",
    "free", "memcpy", "memset", "strcpy", "strncpy", "strcat", "strcmp",
    "strlen", "printf", "sprintf", "snprintf", "fprintf", "scanf", "gets",
    "fgets", "recv", "send", "recvfrom", "sendto", "connect", "bind",
    "listen", "accept", "ioctl", "setsockopt", "execve", "fork",
    "WaitForSingleObject", "VirtualAlloc", "CreateThread",
    "WriteProcessMemory", "ReadProcessMemory", "surgemail.exe",
    "pattern_create", "pattern_offset", "imap_fuzz", "Rex::Text",
    # VHDL / Verilog / FPGA Donanım Sinyalleri ve Anahtar Terimleri
    "std_logic", "std_logic_vector", "std_ulogic", "std_ulogic_vector",
    "posedge", "negedge", "endmodule", "endprimitive", "endtable",
    "clk", "clock", "rst", "reset", "rst_n", "reset_n", "enable", "en",
    "Q_next", "Q_reg", "D_in", "data_in", "data_out", "sel", "downto"
}

# VHDL ve Verilog satır yapılarını tanıyan derleyici düzeyinde (compiler-grade) Regex
HDL_LINE_REGEX = re.compile(
    r'^(?:'
    r'library\s+ieee\b|use\s+ieee\.[a-zA-Z0-9_\.]+\b|'
    r'entity\s+[a-zA-Z_][a-zA-Z0-9_]*\s+is\b|'
    r'architecture\s+[a-zA-Z_][a-zA-Z0-9_]*\s+of\s+[a-zA-Z_][a-zA-Z0-9_]*\s+is\b|'
    r'component\s+[a-zA-Z_][a-zA-Z0-9_]*\b|'
    r'port\s*\(|generic\s*\(|port\s+map\s*\(|generic\s+map\s*\(|'
    r'(?:signal|variable|constant|subtype|type)\s+[a-zA-Z0-9_,\s]+\s*:\s*[a-zA-Z_]|'
    r'[a-zA-Z_][a-zA-Z0-9_,\s]*\s*:\s*(?:in|out|inout|buffer|std_logic|std_logic_vector|bit|integer|unsigned|signed)\b|'
    r'process\s*(?:\([^\)]*\))?\s*(?:is)?\s*$|'
    r'begin\s*$|end\s*(?:process|if|case|loop|architecture|component|[a-zA-Z_][a-zA-Z0-9_]*)?\s*;?\s*$|'
    r'when\s+.+?=>|with\s+[a-zA-Z0-9_]+\s+select\b|'
    r'module\s+[a-zA-Z_][a-zA-Z0-9_]*\s*(?:\(|#|;)|'
    r'endmodule\b|primitive\s+[a-zA-Z_]|endprimitive\b|endtable\b|'
    r'(?:input|output|inout|wire|reg|logic|parameter|localparam|supply0|supply1|tri)\s+(?:wire\s+|reg\s+|signed\s+)?(?:\[[0-9:a-zA-Z_\-\+]+\]\s*)?[a-zA-Z_]|'
    r'always\s*@\s*\(|always_ff\b|always_comb\b|always_latch\b|initial\s+begin\b|initial\b|'
    r'assign\s+[a-zA-Z_][a-zA-Z0-9_\[\]:]*\s*=|'
    r'(?:and|or|nand|nor|xor|xnor|not|buf|bufif0|bufif1)\s+(?:#\s*\([^\)]*\)\s*)?[a-zA-Z0-9_]*\s*\('
    r')',
    re.I
)


PROSE_OPTION_KEYWORDS = {
    "name", "description", "setting", "settings", "default", "required", "optional",
    "option", "options", "summary", "syntax", "usage", "example", "examples", "note",
    "warning", "tip", "author", "platform", "arch", "rank", "disclosed", "available",
    "target", "targets", "payload", "exploit", "auxiliary", "post", "encoder", "nop",
    "evasion", "handler", "session", "sessions", "server", "client", "host", "port",
    "address", "network", "system", "user", "username", "password", "file", "path",
    "directory", "command", "commands", "output", "input", "value", "values", "type",
    "status", "result", "results", "service", "services", "version", "database",
    "vulnerability", "attack", "penetration", "testing", "guide", "chapter", "section",
    "figure", "table", "listing", "page", "current", "yes", "no", "true", "false"
}

PROSE_COLON_LABEL_RE = re.compile(
    r'^(?:[\u2022\-\*]\s*)?(?:Name|Description|Setting|Settings|Default|Required|Optional|'
    r'Option|Options|Summary|Syntax|Usage|Example|Note|Warning|Tip|Author|Platform|Arch|Rank|'
    r'Disclosed|Available\s+targets|Basic\s+options|Payload\s+options|Module\s+options|'
    r'Target|Payload|Exploit|Auxiliary|Server|Client|Host|Port|Address|User|Password|File|Path|'
    r'Command|Output|Input|Value|Type|Status|Result|Service|Version|[A-Z][a-z]+(?:\s+[a-z]+){0,3})\s*:\s+\S+',
    re.I
)

# Terminal istemcileri ve konsol çıktı imzaları ($, #, msf>, root@, [*] ...)
TERMINAL_PROMPT_RE = re.compile(
    r'^(?:\$\s+|#\s+|>>>\s+|\.{3}\s+|msf\s+|msf\s*>|msf\d?\s*>|msf\s+auxiliary\(|'
    r'\[\*\]\s*|\[\+\]\s*|\[\-\]\s*|\[!\]\s*|C:\\>|root@|kali@)'
)


class UniversalFormalismQuarantine:
    NATURAL_COLLOCATIONS = {
        "the", "of the", "in the", "to the", "for the", "on the", "with the",
        "is a", "are the", "can be", "that is", "such as", "which is", "from the",
        "by the", "as a", "into the", "between the", "through the", "this is"
    }
    FORMAL_OPERATORS = set("=<>+-*/|{}[]()^_~\\@#$%&;:!")

    @staticmethod
    def _char_class(ch: str) -> int:
        if ch.islower(): return 1
        if ch.isupper(): return 2
        if ch.isdigit(): return 3
        if ch.isspace(): return 4
        if ch in UniversalFormalismQuarantine.FORMAL_OPERATORS: return 5
        return 6

    @classmethod
    def is_natural_prose_or_option_line(cls, text: str) -> bool:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean = re.sub(r'\u27e6(?:CODE|MTH|INLCODE)[^\u27e7]*\u27e7', ' word ', clean).strip()
        if not clean:
            return False
        # VHDL/Verilog yapı bildirimleri ("architecture rtl of counter is" gibi)
        # doğal dil kilidine takılmamalı; derleyici düzeyindeki HDL regex'i yalnızca
        # bu iskeletlerle eşleşir, İngilizce cümlelerle asla eşleşmez.
        if HDL_LINE_REGEX.match(clean):
            return False
        # Terminal istemiyle başlayan satırlar ($, #, msf>...) asla doğal dil değildir;
        # aksi halde "target"/"host" gibi ağ terimleri oranlı prose kilidini tetikler.
        if TERMINAL_PROMPT_RE.match(clean):
            return False
        if re.match(
            r'^(?:[\u2022\-\*]\s*)?(?:Name|Description|Setting|Settings|Current\s+Setting|'
            r'Default|Required|Optional|Option|Options|Payload|Module|Summary|Usage|Syntax)\b',
            clean,
            re.I
        ):
            return True
        if re.search(
            r'\b(?:Name|Description|Setting|Default|Required)\s*:\s*\S+',
            clean,
            re.I
        ):
            return True
        if re.search(r'(?:;\s*$|\{[^{}]*$|\}[^{}]*$|<=|=>|:=|::=|==|!=|&&|\|\||0x[0-9a-fA-F]{4,})', clean):
            return False
        words = re.findall(r'[a-zA-Z]{2,}', clean)
        if not words:
            return False
        func_hits = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
        opt_vocab = {
            "name", "description", "setting", "settings", "default", "required",
            "optional", "option", "options", "target", "payload", "exploit",
            "handler", "server", "client", "host", "port", "address", "session"
        }
        opt_hits = sum(1 for w in words if w.lower() in opt_vocab)
        if ":" in clean and (func_hits >= 1 or opt_hits >= 1) and not re.search(r'[\{\};]', clean):
            return True
        if len(words) >= 4 and (func_hits + opt_hits) / len(words) >= 0.25:
            return True
        return False

    @classmethod
    def compute_line_formal_probability(
        cls, text: str, x0: float, x1: float, col_left: float, col_right: float, is_mono: bool
    ) -> float:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        if not clean:
            return 1.0
        if cls.is_natural_prose_or_option_line(clean):
            return 0.0
        if is_mono:
            return 1.0
        if HDL_LINE_REGEX.match(clean):
            return 1.0

        n = len(clean)
        transitions = 0
        classes = [cls._char_class(c) for c in clean]
        for i in range(n - 1):
            c1, c2 = classes[i], classes[i + 1]
            if c1 != c2 and not ((c1 == 2 and c2 == 1) or (c1 == 1 and c2 == 4) or (c1 == 4 and c2 in (1, 2))):
                transitions += 1
        trans_score = min(1.0, (transitions / max(1, n)) * 3.0)

        op_count = sum(1 for c in clean if c in cls.FORMAL_OPERATORS and c != ":")
        multi_ops = len(re.findall(
            r'(?:<=|=>|:=|::|->|==|!=|>>|<<|\|\||&&|;\s*$|\b(?:downto|posedge|negedge|std_logic)\b)',
            clean, re.I
        ))
        op_score = min(1.0, (op_count / max(1, n)) * 3.8 + multi_ops * 0.42)

        low_text = f" {clean.lower()} "
        colloc_hits = sum(1 for col in cls.NATURAL_COLLOCATIONS if f" {col} " in low_text)
        words = re.findall(r'[a-zA-Z]{2,}', clean)
        prose_hits = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS or w.lower() in PROSE_OPTION_KEYWORDS)
        prose_brake = min(0.95, colloc_hits * 0.30 + prose_hits * 0.18)

        col_width = max(50.0, col_right - col_left)
        indent_ratio = max(0.0, (x0 - col_left) / col_width)
        short_line_ratio = max(0.0, (col_right - x1) / col_width)
        lacks_prose_end = not clean.endswith((".", "!", "?", '"', "\u201d"))

        geo_score = 0.0
        if lacks_prose_end and prose_hits <= 1:
            if 0.03 < indent_ratio < 0.50:
                geo_score += 0.22
            if short_line_ratio > 0.22:
                geo_score += 0.18

        raw_prob = (0.35 * trans_score) + (0.45 * op_score) + geo_score - prose_brake
        return max(0.0, min(1.0, raw_prob))

    @classmethod
    def apply_spatial_markov_quarantine(
        cls, lines: List[Dict[str, Any]], col_left: float, col_right: float
    ) -> List[Dict[str, Any]]:
        locked_prose = [cls.is_natural_prose_or_option_line(l["text"]) for l in lines]
        probs = []
        for idx, l in enumerate(lines):
            if locked_prose[idx]:
                l["is_code"] = False
                l["is_formal"] = False
                probs.append(0.0)
            elif l.get("is_code", False):
                probs.append(1.0)
            else:
                probs.append(
                    cls.compute_line_formal_probability(
                        l["text"], l["bbox"][0], l["bbox"][2], col_left, col_right, False
                    )
                )

        smoothed = list(probs)
        n = len(lines)
        for _ in range(2):
            new_p = list(smoothed)
            for i in range(n):
                if locked_prose[i] or smoothed[i] >= 0.85 or lines[i].get("is_hdr_ftr", False):
                    continue
                prev_p = smoothed[i - 1] if i > 0 and (lines[i]["bbox"][1] - lines[i - 1]["bbox"][3]) < 20.0 else 0.0
                next_p = smoothed[i + 1] if i < n - 1 and (lines[i + 1]["bbox"][1] - lines[i]["bbox"][3]) < 20.0 else 0.0
                if prev_p > 0.65 and next_p > 0.65:
                    new_p[i] = max(smoothed[i], 0.82)
                elif (prev_p > 0.75 or next_p > 0.75) and len(lines[i]["text"].split()) <= 5:
                    if not lines[i]["text"].endswith("."):
                        new_p[i] = max(smoothed[i], 0.64)
            smoothed = new_p

        for i, l in enumerate(lines):
            if locked_prose[i]:
                l["is_code"] = False
                l["is_formal"] = False
            elif smoothed[i] >= 0.58:
                l["is_code"] = True
                l["is_formal"] = True
        return lines

class FormalismAnalyzer:
    @staticmethod
    def is_monospace_span(font_name: str, flags: int) -> bool:
        if (flags & 8) != 0:
            return True
        fn = font_name.lower().replace("unicode", "")
        if "mono" in fn and "monotype" not in fn:
            return True
        if "code" in fn and not any(x in fn for x in ("unicode", "encode", "barcode")):
            return True
        return any(k in fn for k in MONOSPACE_FONT_KEYWORDS)

    @staticmethod
    def is_code_line_syntax(text: str, leading_indent: float = 0.0) -> bool:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean = re.sub(r'\u27e6(?:CODE|MTH|INLCODE)[^\u27e7]*\u27e7', '', clean).strip()
        clean_no_step = re.sub(r'^[\u2776-\u2793\u2460-\u2473]\s*', '', clean).strip()
        if not clean_no_step:
            return False
        if UniversalFormalismQuarantine.is_natural_prose_or_option_line(clean_no_step):
            return False

        # 1. VHDL ve Verilog Donanım Tanımlama Dili (HDL) Kontrolü
        if HDL_LINE_REGEX.match(clean_no_step):
            return True

        # VHDL/Verilog yorum satırları (-- veya //) ve sinyal atamaları (<=, :=, =>)
        if re.match(r'^(?:--\s*|//\s*)', clean_no_step):
            return True
        if re.search(r'(?:<=|:=|=>)', clean_no_step) and (
            re.search(r';\s*$', clean_no_step) or len(clean_no_step.split()) <= 9
        ):
            return True
        if re.search(r'\b(?:std_logic_vector|std_logic|downto|posedge|negedge|endmodule|port\s+map)\b', clean_no_step, re.I):
            words = re.findall(r'[a-zA-Z]{2,}', clean_no_step)
            func_cnt = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
            if func_cnt / max(1, len(words)) <= 0.18 or len(words) <= 8:
                return True

        # 2. Terminal istemcileri ve konsol çıktıları
        if TERMINAL_PROMPT_RE.match(clean_no_step):
            return True

        # 3. Genel Programlama Dilleri (C/C++, Python, Java, Assembly)
        if re.match(
            r'^(?:#include\s+|#define\s+|#ifdef\s+|#ifndef\s+|#endif\b|#pragma\s+|'
            r'import\s+[a-zA-Z0-9_\.]+|from\s+[a-zA-Z0-9_\.]+\s+import\b|'
            r'def\s+[a-zA-Z_][a-zA-Z0-9_]*|class\s+[a-zA-Z_][a-zA-Z0-9_]*|'
            r'return\b|const\s+|void\s+|int\s+|char\s+|float\s+|double\s+|'
            r'unsigned\s+|struct\s+|typedef\s+|static\s+|extern\s+|public\s+|private\s+|protected\s+|'
            r'printf\b|fprintf\b|sprintf\b|snprintf\b|print_status\b|print_good\b|'
            r'print_error\b|print_line\b|print\s+["\'\(]|'
            r'mov\s+|push\s+|pop\s+|xor\s+|lea\s+|jmp\s+|call\s+|ret\b|'
            r'cmp\s+|test\s+|je\s+|jne\s+|jz\s+|jnz\s+|nop\b|db\s+|dd\s+|dw\s+|'
            r'while\s+True\s*:|while\s*\(|for\s+[a-zA-Z_][a-zA-Z0-9_,\s]*\s+in\s+|for\s*\(|'
            r'if\s+__name__\s*==|if\s*\(|elif\s+|else\s*:|try\s*:|except\b|finally\s*:|with\s+open\()',
            clean_no_step
        ):
            return True

        if re.search(r'(?:Rex::Text|pattern_create|pattern_offset)', clean_no_step):
            words = re.findall(r'[a-zA-Z]{2,}', clean_no_step)
            func_cnt = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
            if func_cnt / max(1, len(words)) <= 0.12 or len(words) < 6:
                return True

        if re.search(r';\s*$', clean_no_step) and (
            re.search(r'[=\(\)\[\]\{\}:]', clean_no_step)
            or leading_indent > 10.0
            or len(clean_no_step.split()) <= 8
        ):
            return True

        if re.search(r'[A-Za-z0-9+/=]{28,}', clean_no_step):
            return True

        if re.match(r'^(?:\.\s*){3}SNIP(?:\s*\.)*$', clean_no_step, re.I):
            return True

        if re.match(
            r'^[a-zA-Z_][a-zA-Z0-9_,\s]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?\s*(?:=|\+=|\-=|:=|<=)\s*[^\s]+',
            clean_no_step
        ):
            words = re.findall(r'[a-zA-Z]{2,}', clean_no_step)
            func_cnt = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
            if func_cnt <= 1:
                return True

        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\s*\([^\)]*\)\s*$', clean_no_step):
            return True

        if re.search(r'\b0x[0-9a-fA-F]+\b', clean_no_step) and len(clean_no_step.split()) <= 8:
            return True
        if re.match(r'^\[\*\]\s*000\d\s+(?:LIST|OK|LOGIN|CAPABILITY)\b', clean_no_step):
            return True

        return False

    @staticmethod
    def is_header_or_footer(text: str, box: BoundingBox, page_height: float) -> bool:
        clean = text.strip()
        if not clean:
            return True

        is_single_line = box.height <= 24.0 and len(clean) <= 115
        in_top_zone = box.y0 <= page_height * 0.055 or box.y1 <= page_height * 0.070
        in_bottom_zone = box.y1 >= page_height * 0.940 or box.y0 >= page_height * 0.925

        if is_single_line and (in_top_zone or in_bottom_zone):
            if re.search(
                r'(?:All\s+rights\s+reserved|All\s+rghts\s+reserved|Copyright|Addison-?Wesley|'
                r'\bChapter\s+\d+\b|\bSection\s+\d+(?:\.\d+)*\b|^\d+\s*[-–]\s*\d+$|^\d{1,4}$)',
                clean,
                re.I
            ):
                return True
            if re.match(r'^(?:\d+\s+.+|\S.+?\s+\d+)$', clean) and len(clean.split()) <= 7:
                return True

        if is_single_line and re.search(
            r'(?:Copyright\s*©?\s*\d{4}|All\s+rights\s+reserved|All\s+rghts\s+reserved|\bAddison-?Wesley\b)',
            clean,
            re.I
        ):
            return True

        if re.fullmatch(r'\d{1,3}\s*[-–]\s*\d{1,3}|\d{1,4}', clean):
            return True

        return False

    @staticmethod
    def is_formal_expression(text: str) -> bool:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean = re.sub(r'\u27e6(?:CODE|MTH|INLCODE)[^\u27e7]*\u27e7', ' codevar ', clean).strip()
        clean = re.sub(r'^[\u2022\-\+\*]\s*', '', clean).strip()
        if not clean:
            return True

        if UniversalFormalismQuarantine.is_natural_prose_or_option_line(clean):
            return False
        if FormalismAnalyzer.is_code_line_syntax(clean):
            return True

        words = re.findall(r'[a-zA-Z]{2,}', clean)
        word_count = len(words)
        func_word_count = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
        func_ratio = func_word_count / max(1, word_count)

        if word_count >= 4 and func_ratio > 0.12:
            if not re.search(r'(?:->|\u2192|\u2190|::=|<=|=>)', clean):
                return False

        total_len = len(clean)
        alpha_chars = sum(1 for c in clean if c.isalpha())
        digit_chars = sum(1 for c in clean if c.isdigit())
        formal_ops = set("=<>+-*/|{}[]()^_~\\@#$%&")
        sym_chars = sum(1 for c in clean if c in formal_ops)

        if alpha_chars == 0:
            return True

        has_bnf_or_arrow = bool(re.search(r'(?:->|\u2192|\u2190|::=|=>|==|!=|<=|>=|:=|<[a-zA-Z_][a-zA-Z0-9_]*>)', clean))
        has_equation = bool(re.search(r'(?:^|\s)[a-zA-Z0-9_\']+\s*[=<>\u2264\u2265\u2260\u2295]\s*[a-zA-Z0-9_\'\(\[\+\-\u03a3\u03a0]', clean))

        has_strict_dot_code = False
        for m_dot in re.finditer(r'\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)(\s*\()?', clean):
            left_p, right_p, has_paren = m_dot.group(1), m_dot.group(2), m_dot.group(3)
            if left_p.lower() in {
                "www", "http", "https", "ftp", "e", "i", "fig", "figure", "sec", "section",
                "ch", "chapter", "dr", "mr", "ms", "vs", "etc", "al", "no", "vol", "p", "pp"
            }:
                continue
            if right_p.lower() in KNOWN_CODE_EXTENSIONS:
                has_strict_dot_code = True
                break
            if has_paren or "_" in left_p or "_" in right_p:
                has_strict_dot_code = True
                break

        if (has_bnf_or_arrow or has_equation or has_strict_dot_code) and func_ratio <= 0.12:
            return True

        if (sym_chars + digit_chars) / max(1, total_len) > 0.36 and func_word_count == 0:
            return True

        if word_count <= 2 and clean.isupper() and func_word_count == 0 and len(clean) <= 20:
            return True
        if re.fullmatch(r'[A-Z]+\s+[A-Z]\.\s+[A-Z]+', clean):
            return True

        return False

    @staticmethod
    def _is_valid_inline_code_token(token: str) -> bool:
        t = token.strip()
        if not t:
            return False
        if re.match(r'^(?:CODE|MTH|INLCODE)_\d+$', t, re.I):
            return False
        if t.startswith(("CODE_", "MTH_", "INLCODE_", "\u27e6")) or t.endswith("\u27e7"):
            return False
        if re.fullmatch(r'[\u2776-\u2793\u2460-\u2473]', t):
            return True
        if len(t) < 2:
            return False
        if t in INLINE_CODE_EXACT_TOKENS:
            return True
        if re.match(r'^(?:www\.|http|e\.g\.|i\.e\.|fig\.|vs\.|[A-Z][a-z]+\.)', t, re.I):
            return False
        if "_" in t and re.search(r'[a-zA-Z]', t):
            return True
        if re.search(r'\[[0-9:a-zA-Z_\-\+]+\]$|\[\]$|\(\)$', t):
            return True
        if re.match(r'^(?:0x[0-9a-fA-F]+|\d+\'[bBhHdDoO][0-9a-fA-F_xXzZ]+)$', t):
            return True
        if re.fullmatch(r'[0-9A-Fa-f]{8}', t) and re.search(r'[A-Fa-f]', t) and re.search(r'[0-9]', t):
            return True
        if "::" in t:
            return True
        if "." in t:
            parts = t.split(".")
            if len(parts) == 2 and parts[1].lower() in KNOWN_CODE_EXTENSIONS:
                return True
            if len(parts) >= 2 and all(re.fullmatch(r'[a-z_][a-zA-Z0-9_]*', p) for p in parts):
                return True
        return False

    @staticmethod
    def mask_inline_formal_tokens(sentence: str) -> Tuple[str, Dict[str, str]]:
        t = normalize_unicode_text(sentence)
        masks: Dict[str, str] = {}
        code_idx = 0
        math_idx = 0

        def add_code_mask(val: str) -> str:
            nonlocal code_idx
            key = f"\u27e6CODE_{code_idx}\u27e7"
            masks[key] = val
            code_idx += 1
            return f" {key} "

        def add_math_mask(m) -> str:
            nonlocal math_idx
            val = m.group(0).strip()
            if (
                val.startswith(("CODE_", "MTH_", "INLCODE_", "\u27e6"))
                or val.endswith("\u27e7")
                or re.search(r'(?:CODE|MTH|INLCODE)_\d+', val, re.I)
            ):
                return val
            if val.startswith("(") and val.endswith(")"):
                inner_words = re.findall(r'[a-zA-Z]{2,}', re.sub(r'<(?:sub|sup):[^>]+>', '', val))
                if len(inner_words) >= 1 and not any(c in val for c in "=+-*/<>^_'"):
                    return val
            key = f"\u27e6MTH_{math_idx}\u27e7"
            masks[key] = val
            math_idx += 1
            return f" {key} "

        def repl_premarked(m) -> str:
            inner_val = m.group(1).strip()
            if re.match(r'^(?:CODE|MTH|INLCODE)_\d+$', inner_val, re.I):
                return inner_val
            return add_code_mask(inner_val)

        t = re.sub(r'\u27e6INLCODE:(.*?)\u27e7', repl_premarked, t)

        inline_code_pattern = (
            r'(?:'
            r'[\u2776-\u2793\u2460-\u2473]'
            r'|\b\d+\'[bBhHdDoO][0-9a-fA-F_xXzZ]+\b'
            r'|\b0x[0-9a-fA-F]+\b'
            r'|\b[0-9A-Fa-f]{8}\b'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_][a-zA-Z0-9_]*)+(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*(?:\([^\)]*\))?'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*\[[0-9:a-zA-Z_\-\+]*\]'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*\(\d+\s+(?:downto|to)\s+\d+\)'
            r'|\b(?!(?:CODE|MTH|INLCODE)_\d+\b)[a-zA-Z_][a-zA-Z0-9_]*_[a-zA-Z0-9_]+(?:\([^\)]*\))?'
            r'|\b[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*(?:\([^\)]*\))?'
            r'|\b(?:target_port|target_host|buffer|argc|argv|stdin|stdout|stderr|malloc|free|printf|recv|send|fork|execve|surgemail\.exe|pattern_create|std_logic_vector|std_logic|posedge|negedge|rst_n|clk)\b'
            r')'
        )

        def repl_inline_code(m) -> str:
            cand = m.group(0).strip()
            if (
                cand.startswith("CODE_")
                or cand.startswith("MTH_")
                or cand.startswith("INLCODE_")
                or cand.startswith("\u27e6")
                or cand.endswith("\u27e7")
                or re.match(r'^(?:CODE|MTH|INLCODE)_\d+$', cand, re.I)
            ):
                return cand
            if FormalismAnalyzer._is_valid_inline_code_token(cand):
                return add_code_mask(cand)
            return cand

        t = re.sub(inline_code_pattern, repl_inline_code, t)

        # Boolean minterm/maxterm ifadeleri: Σ(0, 2, 5), Π(1, 3, 4), F(A, B, C) = ...
        t = re.sub(
            r'(?:[\u03a3\u03a0]\s*\([0-9,\s]+\)|<[a-zA-Z_][a-zA-Z0-9_\s]*>|\{[^{}]+\}|\bC\+\+|\bC#|\.NET\b|#include\b|#define\b)',
            add_math_mask,
            t
        )

        math_atom = (
            r'(?:'
            r'\([0-9\s\+\-\*\/\^\<\>\:\_\u00b1NXYMrnABxy\']+?\)(?:<(?:sub|sup):[^>]+>)?'
            r'|[+\-]?\b(?:[0-9]+(?:\s+[0-9]{4})*|[a-zA-Z])(?:<(?:sub|sup):[^>]+>)+[a-zA-Z0-9\']*'
            r'|[+\-]?\b[0-9]+(?:\s+[0-9]{4})*\b'
            r'|[+\-]?\b[a-zA-Z]\'?(?=\s*(?:[=\u2260<>\u2264\u2265\+\*\/\u2295]|-\s*(?:[0-9\(]|[a-zA-Z]\b)))'
            r'|[+\-]?(?<=[=\u2260<>\u2264\u2265\+\-\*\/\u2295]\s)\b[a-zA-Z]\'?\b'
            r')'
        )
        t = re.sub(
            rf'{math_atom}(?:\s*(?:!=|==|<=|>=|[=\u2260<>\u2264\u2265\+\*\/\u2295]|-(?!\s*[a-zA-Z]{{2,}}))\s*{math_atom})+',
            add_math_mask,
            t
        )
        t = re.sub(r'(?:\([0-9a-zA-Z\s\+\-]+\)|[+\-]?\b[0-9a-zA-Z]+)?<(?:sub|sup):[^>]+>', add_math_mask, t)
        t = re.sub(r'\(\s*[\u00b1\+\-]?\s*[a-zA-Z0-9]\s*(?:[\-\+\|]\s*[a-zA-Z0-9]\s*)+\)', add_math_mask, t)

        return re.sub(r'\s+', ' ', t).strip(), masks

    @staticmethod
    def unmask_formal_tokens(translated: str, masks: Dict[str, str]) -> str:
        res = translated
        for key, orig in masks.items():
            m_type = "CODE" if "CODE" in key else "MTH"
            num = re.sub(r'\D', '', key)
            val = orig.strip()
            pat_bracket = rf'[\u27e6\u0028\u005b\u007b\u003c\ufd3e\u003f]\s*{m_type}[_\-]?{num}\s*[\u27e7\u0029\u005d\u007d\u003e\ufd3f\u003f]'
            res = re.sub(pat_bracket, lambda _, v=val: f" {v} ", res, flags=re.I)
            pat_bare = rf'\b{m_type}[_\-]?{num}\b'
            res = re.sub(pat_bare, lambda _, v=val: v, res, flags=re.I)
        return re.sub(r'\s+', ' ', res).strip()
