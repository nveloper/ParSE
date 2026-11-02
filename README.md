# ParSE

ParSE is a small MCP (Model Context Protocol) server that gives an AI assistant two tools for working with local files: converting Office and Hwpx documents into clean Markdown, and transcribing audio or video into timestamped text. Everything runs locally. No file content is ever sent to an external API.

## What it does

The server (`server.py`) exposes two tools over MCP.

### parse_document

Converts a Word (.docx), PowerPoint (.pptx), or Hwpx (.hwpx) file into structure-preserving Markdown, instead of having the assistant try to read the raw XML/zip contents directly.

- Word: paragraphs, heading levels, and tables, in original document order.
- PowerPoint: one section per slide, shapes read in approximate on-screen order, tables, and speaker notes.
- Hwpx: paragraphs and tables, with headings recovered from the Part/Chapter/Section/Subsection numbering conventions used in Korean statutes and government documents. This heading detection is a heuristic for that document style, not a general solution for all Hwpx files.

Files are sanity-checked before parsing (each format is a zip archive expected to contain a specific member file), so a mislabeled or corrupted file returns a clear error instead of silently producing garbage. Keynote (.key) is not supported.

### transcribe_video

Transcribes speech in a video or audio file into timestamped lines (`[m:ss] text`). It shells out to a locally built `whisper.cpp` binary (Vulkan backend) instead of calling any cloud speech API. Common video containers (mp4, mov, mkv, and others) and audio files (mp3, wav, m4a, and others) are supported; the audio track is extracted and resampled to 16kHz mono before being handed to whisper.cpp.

The first call on a given server process downloads the speech model from Hugging Face if it is not already cached, which needs internet access once; later calls reuse the loaded model.

## Why whisper.cpp instead of a pip package

The original implementation used faster-whisper/ctranslate2, but ctranslate2's CUDA 12 build no longer ships kernels for older Maxwell-generation GPUs, so it failed at inference time on this machine. whisper.cpp's Vulkan backend runs on the same hardware without that restriction, and Vulkan is not NVIDIA-specific, so this also works on AMD and Intel GPUs. In local testing on a 22.5-minute video, the Vulkan build finished in about 217 seconds versus roughly 1267 seconds on CPU with the previous path.

The trade-off is that `whisper-cli.exe` is a binary compiled from source with `GGML_VULKAN=ON`, not something installable with pip. The source checkout lives under `whisper.cpp/`, and the build output is expected at `whisper.cpp/build2/bin/whisper-cli.exe`. Rebuilding it requires the WinLibs MinGW toolchain and the Vulkan SDK.

## Requirements

- Python (developed against 3.14)
- Packages listed in `requirements.txt`: `mcp`, `python-docx`, `python-pptx`, `av`
- A built `whisper.cpp` binary and a ggml model file for transcription (`whisper.cpp/build2/bin/whisper-cli.exe` and `whisper.cpp/models/ggml-small.bin` in this repository); these are not installed via pip

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

## Setup

ParSE is meant to be registered as an MCP server with an MCP-compatible client (such as Claude Code or Claude Desktop). An example configuration, as used in `.mcp.json`:

```json
{
  "mcpServers": {
    "parse-docs": {
      "command": "python",
      "args": ["path/to/ParSE/server.py"]
    }
  }
}
```

Point `command` at the Python interpreter you installed the dependencies into, and `args` at the full path to `server.py` on your machine.

## Usage

Once the server is registered, the assistant can call the two tools directly:

- Ask it to read or summarize a .docx, .pptx, or .hwpx file, and it will call `parse_document` instead of opening the raw file.
- Ask it to transcribe a video or audio file, and it will call `transcribe_video` and return timestamped text.

Both tools take a single argument, `file_path`, which should be an absolute or otherwise resolvable path to the file.

## Known limitations

- Keynote (.key) files are not supported by `parse_document`.
- Hwpx heading detection is tuned for Korean legal and government document conventions; it will not reliably detect headings in Hwpx files that use a different structure.
- Transcription depends on a machine-specific `whisper.cpp` build; the binary and model in this repository were built and tuned for the original development machine's GPU, and the thread count and process priority are set conservatively so transcription does not interfere with other foreground work on that machine. These may need adjusting on a different machine.

---

# ParSE (한국어)

ParSE는 AI 어시스턴트에게 두 가지 로컬 파일 처리 도구를 제공하는 작은 MCP(Model Context Protocol) 서버입니다. 하나는 오피스 문서와 Hwpx 파일을 깔끔한 마크다운으로 변환하는 도구이고, 다른 하나는 오디오나 비디오를 타임스탬프가 붙은 텍스트로 변환하는 도구입니다. 모든 처리는 로컬에서 이루어지며, 파일 내용이 외부 API로 전송되는 일은 없습니다.

## 주요 기능

서버(`server.py`)는 MCP를 통해 두 가지 도구를 제공합니다.

### parse_document

Word(.docx), PowerPoint(.pptx), Hwpx(.hwpx) 파일을 구조를 보존한 마크다운으로 변환합니다. 어시스턴트가 원본 XML이나 압축 파일 내용을 직접 읽으려 시도하는 대신 이 도구를 사용하게 됩니다.

- Word: 문단, 제목 수준, 표를 원본 문서 순서 그대로 변환합니다.
- PowerPoint: 슬라이드마다 하나의 섹션으로 나누고, 도형은 화면상 배치 순서에 가깝게 읽으며, 표와 발표자 노트도 포함합니다.
- Hwpx: 문단과 표를 변환하며, 제목은 한국 법령 및 정부 문서에서 관용적으로 쓰이는 편/장/절/관 번호 체계를 이용해 추출합니다. 이 제목 인식 방식은 해당 문서 유형에 맞춘 휴리스틱이며, 모든 Hwpx 파일에 통용되는 일반적인 해법은 아닙니다.

파싱 전에 파일 구조를 먼저 점검합니다. 각 포맷은 특정 구성 파일을 포함해야 하는 압축 파일이므로, 확장자가 잘못 붙었거나 손상된 파일은 조용히 빈 결과를 내는 대신 명확한 오류 메시지를 반환합니다. Keynote(.key) 파일은 지원하지 않습니다.

### transcribe_video

비디오 또는 오디오 파일의 음성을 타임스탬프가 있는 텍스트(`[분:초] 내용`)로 변환합니다. 클라우드 음성 인식 API를 호출하는 대신, 로컬에서 빌드한 `whisper.cpp`(Vulkan 백엔드)를 실행합니다. 일반적인 비디오 컨테이너(mp4, mov, mkv 등)와 오디오 파일(mp3, wav, m4a 등)을 지원하며, whisper.cpp에 전달하기 전에 오디오 트랙을 16kHz 모노로 추출 및 리샘플링합니다.

서버 프로세스에서 처음 호출할 때 음성 모델이 아직 캐시되어 있지 않다면 Hugging Face에서 내려받으며, 이때 한 번 인터넷 연결이 필요합니다. 이후 호출부터는 이미 로드된 모델을 재사용합니다.

## pip 패키지 대신 whisper.cpp를 쓰는 이유

원래 구현은 faster-whisper/ctranslate2를 사용했지만, ctranslate2의 CUDA 12 빌드가 더 이상 구형 Maxwell 세대 GPU용 커널을 포함하지 않아 이 환경에서는 추론 시점에 오류가 발생했습니다. whisper.cpp의 Vulkan 백엔드는 같은 하드웨어에서 그러한 제약 없이 동작하며, Vulkan은 NVIDIA 전용이 아니므로 AMD나 Intel GPU에서도 동일하게 사용할 수 있습니다. 22.5분짜리 영상으로 테스트한 결과, 기존 CPU 경로는 약 1267초가 걸린 반면 이번 Vulkan 빌드는 약 217초 만에 끝났습니다.

다만 `whisper-cli.exe`는 `GGML_VULKAN=ON` 옵션으로 소스에서 직접 빌드한 바이너리이며, pip으로 설치할 수 있는 패키지가 아닙니다. 소스 체크아웃은 `whisper.cpp/` 아래에 있고, 빌드 결과물은 `whisper.cpp/build2/bin/whisper-cli.exe` 경로에 있어야 합니다. 다시 빌드하려면 WinLibs MinGW 툴체인과 Vulkan SDK가 필요합니다.

## 요구 사항

- Python (3.14 기준으로 개발됨)
- `requirements.txt`에 명시된 패키지: `mcp`, `python-docx`, `python-pptx`, `av`
- 음성 변환을 위한 빌드된 `whisper.cpp` 바이너리와 ggml 모델 파일(이 저장소에서는 `whisper.cpp/build2/bin/whisper-cli.exe`와 `whisper.cpp/models/ggml-small.bin`). 이 두 가지는 pip으로 설치되지 않습니다.

Python 의존성 설치:

```bash
pip install -r requirements.txt
```

## 설정 방법

ParSE는 Claude Code나 Claude Desktop 같은 MCP 호환 클라이언트에 MCP 서버로 등록해서 사용하도록 만들어졌습니다. `.mcp.json`에서 사용한 예시 설정은 다음과 같습니다.

```json
{
  "mcpServers": {
    "parse-docs": {
      "command": "python",
      "args": ["path/to/ParSE/server.py"]
    }
  }
}
```

`command`에는 의존성을 설치한 Python 인터프리터 경로를, `args`에는 사용 중인 컴퓨터에서 `server.py`의 전체 경로를 지정하면 됩니다.

## 사용 방법

서버가 등록되고 나면 어시스턴트가 두 도구를 직접 호출할 수 있습니다.

- .docx, .pptx, .hwpx 파일을 읽어달라거나 요약해달라고 요청하면, 원본 파일을 직접 여는 대신 `parse_document`를 호출합니다.
- 비디오나 오디오 파일을 텍스트로 변환해달라고 요청하면 `transcribe_video`를 호출하여 타임스탬프가 있는 텍스트를 반환합니다.

두 도구 모두 `file_path` 하나만 인자로 받으며, 절대 경로 또는 해석 가능한 경로를 전달하면 됩니다.

## 알려진 제한 사항

- `parse_document`는 Keynote(.key) 파일을 지원하지 않습니다.
- Hwpx 제목 인식은 한국 법령 및 정부 문서의 관례에 맞춰져 있으므로, 다른 구조를 사용하는 Hwpx 파일에서는 제목을 안정적으로 인식하지 못할 수 있습니다.
- 음성 변환은 특정 환경에 맞춰 빌드된 `whisper.cpp`에 의존합니다. 이 저장소의 바이너리와 모델은 원래 개발 환경의 GPU에 맞춰 빌드 및 조정된 것이며, 스레드 수와 프로세스 우선순위도 해당 환경에서 다른 포그라운드 작업을 방해하지 않도록 보수적으로 설정되어 있습니다. 다른 환경에서는 이러한 값들을 조정해야 할 수 있습니다.
