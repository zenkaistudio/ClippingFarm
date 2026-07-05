import json
import shutil
import subprocess
from pathlib import Path

_BUNDLED_DIR = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg" / "bin"
_FFMPEG_BUNDLED = _BUNDLED_DIR / "ffmpeg.exe"
_FFPROBE_BUNDLED = _BUNDLED_DIR / "ffprobe.exe"

FFMPEG = str(_FFMPEG_BUNDLED) if _FFMPEG_BUNDLED.exists() else "ffmpeg"
FFPROBE = str(_FFPROBE_BUNDLED) if _FFPROBE_BUNDLED.exists() else "ffprobe"


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")


def probe(path: Path) -> dict:
    cmd = [
        FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}\n{result.stderr}")
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    return {
        "width": stream["width"],
        "height": stream["height"],
        "fps": float(num) / float(den),
        "duration": float(data["format"]["duration"]),
    }


def extract_audio(video_path: Path, out_wav_path: Path) -> None:
    cmd = [
        FFMPEG, "-y", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(out_wav_path),
    ]
    _run(cmd)


def cut_clip(source: Path, start: float, end: float, out_path: Path) -> None:
    cmd = [
        FFMPEG, "-y",
        "-i", str(source),
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
        "-c:v", "libx264", "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        str(out_path),
    ]
    _run(cmd)


def crop_vertical(in_path: Path, out_path: Path, width: int, height: int, offset_x: int = 0) -> None:
    # Source is wider than the target aspect (e.g. 16:9 -> 9:16), so scale to fill
    # the target height (overflowing width), then crop the width down to center it.
    vf = (
        f"scale=-2:{height},"
        f"crop={width}:{height}:(in_w-{width})/2+{offset_x}:0"
    )
    cmd = [FFMPEG, "-y", "-i", str(in_path), "-vf", vf, "-c:a", "copy", str(out_path)]
    _run(cmd)


def _escape_filter_path(path: Path) -> str:
    # ffmpeg's filtergraph parser treats ':' and '\' as special characters, so a raw
    # Windows path like "C:\foo\bar.ass" gets mangled when passed straight into a
    # filter option. Use forward slashes, escape the drive-letter colon, and wrap the
    # whole thing in single quotes via the explicit filename= key (the ass filter's own
    # positional-arg parser otherwise still splits on the escaped colon).
    escaped = str(path).replace("\\", "/").replace(":", "\\:")
    return f"filename='{escaped}'"


def burn_ass(in_path: Path, ass_path: Path, out_path: Path) -> None:
    vf = f"ass={_escape_filter_path(ass_path)}"
    cmd = [FFMPEG, "-y", "-i", str(in_path), "-vf", vf, "-c:a", "copy", str(out_path)]
    _run(cmd)
