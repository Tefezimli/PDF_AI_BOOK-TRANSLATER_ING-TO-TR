from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2.0

    def overlaps(self, other: "BoundingBox", margin: float = 1.5) -> bool:
        return not (
            self.x1 + margin < other.x0
            or self.x0 - margin > other.x1
            or self.y1 + margin < other.y0
            or self.y0 - margin > other.y1
        )


@dataclass
class ParagraphBlock:
    id: int
    page_num: int
    box: BoundingBox
    text: str
    translated_text: str = ""
    font_size: float = 10.0
    is_standalone_math: bool = False
    is_code_block: bool = False
    is_header_footer: bool = False
    is_from_ocr: bool = False
    is_bold: bool = False
    is_centered: bool = False
    is_table_or_diagram_cell: bool = False
    text_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    bg_color: Optional[Tuple[float, float, float]] = None
    max_allowed_y1: Optional[float] = None
    max_allowed_x1: Optional[float] = None

    @property
    def is_protected(self) -> bool:
        return self.is_standalone_math or self.is_code_block or self.is_header_footer
