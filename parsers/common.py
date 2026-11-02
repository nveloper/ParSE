"""Shared helpers for building the normalized Markdown output."""


def to_markdown_table(rows: list[list[str]]) -> str:
    """Render a list-of-rows table as a GitHub-style Markdown pipe table.

    The first row is treated as the header. Cell text is flattened to a
    single line (newlines/pipes escaped) since Markdown tables can't
    contain raw line breaks.
    """
    if not rows:
        return ""

    def clean(cell: str) -> str:
        cell = (cell or "").replace("\n", " ").replace("|", "\\|")
        return " ".join(cell.split())

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    header = "| " + " | ".join(clean(c) for c in rows[0]) + " |"
    sep = "| " + " | ".join("---" for _ in range(width)) + " |"
    body = "\n".join(
        "| " + " | ".join(clean(c) for c in r) + " |" for r in rows[1:]
    )
    return "\n".join([header, sep, body]) if body else "\n".join([header, sep])


def localname(tag: str) -> str:
    """Strip an XML namespace URI from a Clark-notation tag, e.g.
    '{http://...}p' -> 'p'."""
    return tag.split("}", 1)[1] if "}" in tag else tag
