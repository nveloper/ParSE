"""Word (.docx) -> normalized Markdown."""

import re

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from .common import to_markdown_table

_HEADING_RE = re.compile(r"(?:heading|제목)\s*(\d+)", re.IGNORECASE)


def _iter_block_items(parent):
    """Yield Paragraph/Table objects from a Document or _Cell in document order.

    python-docx exposes .paragraphs and .tables as separate lists, which
    loses interleaving order; walking the underlying XML body directly is
    the standard way to preserve it.
    """
    parent_elm = parent.element.body if hasattr(parent, "element") else parent._tc
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _heading_level(paragraph: Paragraph) -> int | None:
    style_name = paragraph.style.name if paragraph.style else ""
    m = _HEADING_RE.search(style_name or "")
    if not m:
        return None
    level = int(m.group(1))
    return max(1, min(level, 6))


def _table_to_markdown(table: Table) -> str:
    rows = [[cell.text for cell in row.cells] for row in table.rows]
    return to_markdown_table(rows)


def parse(file_path: str) -> str:
    doc = Document(file_path)
    blocks: list[str] = []

    for item in _iter_block_items(doc):
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            level = _heading_level(item)
            blocks.append(f"{'#' * level} {text}" if level else text)
        elif isinstance(item, Table):
            md = _table_to_markdown(item)
            if md:
                blocks.append(md)

    return "\n\n".join(blocks)
