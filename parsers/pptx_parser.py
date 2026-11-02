"""PowerPoint (.pptx) -> normalized Markdown."""

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from .common import to_markdown_table


def _flatten_shapes(shapes):
    """Yield (top, left, shape) recursing into group shapes.

    Shape XML order in a .pptx doesn't reliably match on-screen reading
    order, so callers sort by position instead of trusting iteration order.
    Coordinates inside a group are local to that group, not slide-absolute;
    for our purposes (approximate reading order) that's close enough.
    """
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _flatten_shapes(shape.shapes)
        else:
            yield (shape.top or 0, shape.left or 0, shape)


def _shape_to_blocks(shape) -> list[str]:
    blocks = []
    if shape.has_table:
        rows = [[cell.text for cell in row.cells] for row in shape.table.rows]
        md = to_markdown_table(rows)
        if md:
            blocks.append(md)
    elif shape.has_text_frame:
        text = shape.text_frame.text.strip()
        if text:
            blocks.append(text)
    elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        blocks.append("*(image)*")
    return blocks


def parse(file_path: str) -> str:
    prs = Presentation(file_path)
    sections: list[str] = []

    for i, slide in enumerate(prs.slides, start=1):
        blocks = [f"## Slide {i}"]

        ordered_shapes = sorted(_flatten_shapes(slide.shapes), key=lambda t: (t[0], t[1]))
        for _, _, shape in ordered_shapes:
            blocks.extend(_shape_to_blocks(shape))

        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                blocks.append("> Speaker notes: " + notes.replace("\n", "\n> "))

        sections.append("\n\n".join(blocks))

    return "\n\n".join(sections)
