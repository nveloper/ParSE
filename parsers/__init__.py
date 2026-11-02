"""Format-agnostic entry point: parse(file_path) -> Markdown.

Dispatches by extension to the right adapter, after a structural sanity
check (docx/pptx/hwpx are all zip containers with a known member file) so a
mislabeled or corrupt file fails loudly instead of silently returning junk
or an empty string.
"""

import zipfile
from pathlib import Path

from . import docx_parser, hwpx_parser, pptx_parser

_PARSERS = {
    ".docx": docx_parser,
    ".pptx": pptx_parser,
    ".hwpx": hwpx_parser,
}

# A member every valid file of that type must contain; used to catch
# mislabeled/corrupt files before handing them to the format-specific parser.
_EXPECTED_MEMBER = {
    ".docx": "word/document.xml",
    ".pptx": "ppt/presentation.xml",
    ".hwpx": "Contents/content.hpf",
}


class UnsupportedFormatError(ValueError):
    pass


class CorruptDocumentError(ValueError):
    pass


def parse(file_path: str) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"No such file: {file_path}")

    ext = path.suffix.lower()
    module = _PARSERS.get(ext)
    if module is None:
        raise UnsupportedFormatError(
            f"Unsupported extension '{ext}'. Supported: {', '.join(sorted(_PARSERS))}"
        )

    expected_member = _EXPECTED_MEMBER[ext]
    try:
        with zipfile.ZipFile(path) as z:
            if expected_member not in z.namelist():
                raise CorruptDocumentError(
                    f"'{path.name}' has a {ext} extension but is missing "
                    f"'{expected_member}' — likely mislabeled or corrupt."
                )
    except zipfile.BadZipFile as e:
        raise CorruptDocumentError(
            f"'{path.name}' has a {ext} extension but isn't a valid zip container."
        ) from e

    return module.parse(str(path))
