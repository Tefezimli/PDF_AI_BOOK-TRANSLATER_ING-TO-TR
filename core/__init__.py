from .models import BoundingBox, ParagraphBlock
from .hardware import HAS_TESSERACT, configure_tesseract, get_safe_device, release_memory
from .checkpoint import ExtractionCheckpoint
from .unicode_sanitizer import (
    SUPERSCRIPT_MAP,
    SUBSCRIPT_MAP,
    GLYPH_FALLBACK_MAP,
    DeterministicArtifactPurger,
    normalize_unicode_text,
    format_sub_sup_for_render,
    select_best_unicode_fonts,
)
