"""Hwpx (Hangul/HWPX) -> normalized Markdown.

HWPX namespace URIs differ across Hancom's own schema
(http://www.hancom.co.kr/hwpml/2011/*) and the newer OWPML/KS X 6101
standard (http://www.owpml.org/owpml/2021/*), and third-party writers may
vary further. Rather than pin one URI, elements are matched by local tag
name only (see common.localname), which is stable across versions.

Known limitation: heading levels aren't resolved from header.xml's style
table. Checked against a real government-notice .hwpx, chapter/section
titles turned out to share the exact same paraPrIDRef/styleIDRef as
ordinary body paragraphs -- they're set apart by manual formatting (bold,
centering), not a named style, which is common in older hwpx documents.
So a style lookup wouldn't have found them either.

Instead, headings are recovered from the 편/장/절/관 (Part/Chapter/
Section/Subsection) and 부칙 (Addendum) numbering that Korean statutes and
government documents use by convention (a KLIC-standard structure, not
specific to this one file). This is a Korean-legal/government-document
heuristic, not a general hwpx solution -- 조 (Article) numbers are left as
plain text since the label and body share one paragraph (e.g. "제1조(목적)
이 영은..."), so promoting them would header-ize nearly every paragraph.
"""

import re
import zipfile
from xml.etree import ElementTree as ET

from .common import localname, to_markdown_table

_SECTION_RE = re.compile(r"Contents/section(\d+)\.xml$")

_CHAPTER_RE = re.compile(r"^제\s*\d+\s*(편|장|절|관)(\s|$)")
_ADDENDUM_RE = re.compile(r"^부칙(\s|$|<)")
_LEVEL_BY_UNIT = {"편": 1, "장": 2, "절": 3, "관": 4}


def _heading_level(text: str) -> int | None:
    m = _CHAPTER_RE.match(text)
    if m:
        return _LEVEL_BY_UNIT[m.group(1)]
    if _ADDENDUM_RE.match(text):
        return 2
    return None


def _format_text_block(text: str) -> str:
    level = _heading_level(text)
    return f"{'#' * level} {text}" if level else text


def _section_files(z: zipfile.ZipFile) -> list[str]:
    matches = [(n, _SECTION_RE.search(n)) for n in z.namelist()]
    matches = [(n, m) for n, m in matches if m]
    matches.sort(key=lambda nm: int(nm[1].group(1)))
    return [n for n, _ in matches]


def _render_table(tbl) -> str:
    rows = []
    for tr in tbl:
        if localname(tr.tag) != "tr":
            continue
        cells = []
        for tc in tr:
            if localname(tc.tag) != "tc":
                continue
            texts = [c.text or "" for c in tc.iter() if localname(c.tag) == "t"]
            cells.append(" ".join("".join(texts).split()))
        rows.append(cells)
    return to_markdown_table(rows)


def _render_paragraph(p) -> list[str]:
    blocks: list[str] = []
    text_parts: list[str] = []

    for run in p:
        if localname(run.tag) != "run":
            continue
        for child in run:
            local = localname(child.tag)
            if local == "t":
                text_parts.append(child.text or "")
            elif local == "lineBreak":
                text_parts.append("\n")
            elif local == "tbl":
                if text_parts:
                    joined = "".join(text_parts).strip()
                    if joined:
                        blocks.append(_format_text_block(joined))
                    text_parts = []
                md = _render_table(child)
                if md:
                    blocks.append(md)

    if text_parts:
        joined = "".join(text_parts).strip()
        if joined:
            blocks.append(_format_text_block(joined))

    return blocks


def parse(file_path: str) -> str:
    blocks: list[str] = []
    with zipfile.ZipFile(file_path) as z:
        for name in _section_files(z):
            root = ET.fromstring(z.read(name))
            for p in root:
                if localname(p.tag) != "p":
                    continue
                blocks.extend(_render_paragraph(p))

    return "\n\n".join(blocks)
