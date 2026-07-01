import json
import shutil
import subprocess
from pathlib import Path

_FFMPEG_FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
_FFPROBE_FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffprobe")

FFMPEG = str(_FFMPEG_FULL) if _FFMPEG_FULL.exists() else "ffmpeg"
FFPROBE = str(_FFPROBE_FULL) if _FFPROBE_FULL.exists() else "ffprobe"


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


def burn_ass(in_path: Path, ass_path: Path, out_path: Path) -> None:
    vf = f"ass={ass_path}"
    cmd = [FFMPEG, "-y", "-i", str(in_path), "-vf", vf, "-c:a", "copy", str(out_path)]
    _run(cmd)
