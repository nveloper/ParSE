"""MCP server exposing document-parsing and transcription tools."""

from mcp.server.mcpserver import MCPServer

import transcribe as _transcribe
from parsers import CorruptDocumentError, UnsupportedFormatError, parse

mcp = MCPServer("parse-docs")


@mcp.tool()
def parse_document(file_path: str) -> str:
    """Convert a Word (.docx), PowerPoint (.pptx), or Hwpx (.hwpx) file into
    token-efficient, structure-preserving Markdown instead of reading the
    raw file. Preserves heading levels, tables, slide boundaries, and
    speaker notes. Keynote (.key) is not supported yet.

    Call this whenever you need to read the contents of one of these file
    types, instead of trying to open the raw file directly.
    """
    try:
        return parse(file_path)
    except (UnsupportedFormatError, CorruptDocumentError, FileNotFoundError) as e:
        return f"Error: {e}"


@mcp.tool()
def transcribe_video(file_path: str) -> str:
    """Transcribe the speech in a video or audio file into timestamped text
    ("[m:ss] ..." per segment) using a local speech-to-text model -- no
    audio/video content is sent to any external API. Works on common video
    containers (mp4, mov, mkv, ...) and audio files (mp3, wav, m4a, ...).

    The first call on a given server process downloads the speech model
    from Hugging Face if it isn't cached yet, which needs internet access
    once and can take a while; later calls reuse the already-loaded model.
    """
    try:
        return _transcribe.transcribe(file_path)
    except FileNotFoundError as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
