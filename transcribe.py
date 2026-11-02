"""Video/audio -> transcript via a locally-built whisper.cpp (Vulkan backend).

Why whisper.cpp instead of faster-whisper/ctranslate2 (the original
implementation): ctranslate2's CUDA-12 build no longer ships kernels for
this machine's GPU (GTX 960, Maxwell, compute capability 5.2) -- confirmed
by testing (cudaErrorInvalidDevice at inference time), not assumed.
whisper.cpp's Vulkan backend runs on the same card fine, since Vulkan
compute isn't gated by CUDA's per-architecture kernel embedding, and Vulkan
also covers AMD/Intel GPUs, so this isn't an NVIDIA-only path going
forward. Measured on the same 22.5-minute video: CPU (previous
faster-whisper path) took 1267s; this Vulkan build takes 217s (~5.8x).

Trade-off: whisper-cli.exe is a compiled binary built from source
(GGML_VULKAN=ON), not a pip package -- see whisper.cpp/ under this project
for the source checkout and build2/ for the build output. Rebuilding it
needs the WinLibs MinGW toolchain and the Vulkan SDK; see the cmake
invocation used to produce build2/ in project history if it needs redoing.

No audio/video is sent to any external API -- this shells out to a local
binary only.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

import av

_ROOT = Path(__file__).parent
_WHISPER_CLI = _ROOT / "whisper.cpp" / "build2" / "bin" / "whisper-cli.exe"
_MODEL = _ROOT / "whisper.cpp" / "models" / "ggml-small.bin"

# whisper-cli.exe needs these directories to find its own runtime DLLs and
# the Vulkan loader. Git Bash's bundled /mingw64/bin ships a different,
# ABI-incompatible libstdc++-6.dll; if that shadows the WinLibs one the
# binary was actually built with, it fails to launch at all
# (STATUS_ENTRYPOINT_NOT_FOUND) -- so the WinLibs dir must come first.
_WINLIBS_BIN = (
    r"C:\Users\Base\AppData\Local\Microsoft\WinGet\Packages"
    r"\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\mingw64\bin"
)
_VULKAN_BIN = r"C:\VulkanSDK\1.4.357.0\Bin"

_SEGMENT_RE = re.compile(
    r"^\[(\d{2}):(\d{2}):(\d{2})\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]\s*(.*)$"
)


def _subprocess_env() -> dict:
    env = dict(os.environ)
    env["PATH"] = _WINLIBS_BIN + os.pathsep + _VULKAN_BIN + os.pathsep + env.get("PATH", "")
    return env


def _extract_audio(src: Path, dst: Path) -> None:
    """Decode any container's audio track to 16kHz mono PCM WAV via PyAV --
    whisper-cli only reads flac/mp3/ogg/wav directly, not video containers,
    and normalizing every input through one path avoids format-specific
    surprises."""
    inp = av.open(str(src))
    out = av.open(str(dst), "w")
    out_stream = out.add_stream("pcm_s16le", rate=16000)
    out_stream.layout = "mono"
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

    for frame in inp.decode(inp.streams.audio[0]):
        for rframe in resampler.resample(frame):
            for packet in out_stream.encode(rframe):
                out.mux(packet)
    for packet in out_stream.encode(None):
        out.mux(packet)
    out.close()
    inp.close()


def _format_timestamp(h: str, m: str, s: str) -> str:
    h, m, s = int(h), int(m), int(s)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def transcribe(file_path: str) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"No such file: {file_path}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    try:
        _extract_audio(path, wav_path)

        # Capped to half the cores and launched at IDLE priority so this
        # doesn't compete with latency-sensitive foreground work (this
        # machine also runs Sunshine for remote desktop/streaming, which
        # visibly stutters if this runs at full priority -- confirmed by
        # the stutter clearing once a full-priority run was killed).
        # IDLE_PRIORITY_CLASS lowers CPU scheduling priority; Windows'
        # WDDM GPU scheduler takes process priority into account too, so
        # it should also yield GPU time to the streaming encoder, though
        # that part isn't directly measurable from here.
        threads = max(1, (os.cpu_count() or 4) // 2)
        result = subprocess.run(
            [
                str(_WHISPER_CLI),
                "-m", str(_MODEL),
                "-f", str(wav_path),
                "-t", str(threads),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_subprocess_env(),
            creationflags=subprocess.IDLE_PRIORITY_CLASS,
        )
        if result.returncode != 0:
            raise RuntimeError(f"whisper-cli failed: {result.stderr[-2000:]}")

        combined = result.stdout + result.stderr
        lines = []
        for line in combined.splitlines():
            m = _SEGMENT_RE.match(line)
            if m:
                h, mi, s, text = m.groups()
                text = text.strip()
                if text:
                    lines.append(f"[{_format_timestamp(h, mi, s)}] {text}")
        return "\n".join(lines)
    finally:
        wav_path.unlink(missing_ok=True)
