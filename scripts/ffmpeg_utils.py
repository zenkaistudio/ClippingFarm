import json
import shutil
import subprocess
from pathlib import Path

_BUNDLED_DIR = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg" / "bin"
_FFMPEG_BUNDLED = _BUNDLED_DIR / "ffmpeg.exe"
_FFPROBE_BUNDLED = _BUNDLED_DIR / "ffprobe.exe"
_FFMPEG_MACOS_FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
_FFPROBE_MACOS_FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffprobe")

if _FFMPEG_BUNDLED.exists():
    FFMPEG = str(_FFMPEG_BUNDLED)
    FFPROBE = str(_FFPROBE_BUNDLED)
elif _FFMPEG_MACOS_FULL.exists():
    FFMPEG = str(_FFMPEG_MACOS_FULL)
    FFPROBE = str(_FFPROBE_MACOS_FULL)
else:
    FFMPEG = "ffmpeg"
    FFPROBE = "ffprobe"


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


def has_audio_stream(path: Path) -> bool:
    cmd = [
        FFPROBE, "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}\n{result.stderr}")
    return bool(json.loads(result.stdout).get("streams"))


def extract_audio(video_path: Path, out_wav_path: Path) -> None:
    if not has_audio_stream(video_path):
        raise RuntimeError(
            f"'{video_path.name}' has no audio track — nothing to transcribe. "
            "Re-record with your microphone or system/computer audio enabled and re-upload."
        )
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


def crop_vertical_blurred_sides(in_path: Path, out_path: Path, width: int, height: int,
                                offset_x: int = 0) -> None:
    """
    Template A — blurred side bars.
    FG: 9:16 crop at 88% of frame width, centered horizontally.
    BG: same source blurred + zoomed to fill the full 1080x1920 frame.
    Thin blurred bars visible on left and right of the main content.
    """
    fg_w = (int(width * 0.88) // 2) * 2  # must be even
    side = (width - fg_w) // 2
    vf = (
        f"[0:v]scale=-2:{height},"
        f"crop={width}:{height}:(iw-{width})/2+{offset_x}:0,"
        f"boxblur=30:3[bg];"
        f"[0:v]scale=-2:{height},"
        f"crop={fg_w}:{height}:(iw-{fg_w})/2+{offset_x}:0[fg];"
        f"[bg][fg]overlay={side}:0[v]"
    )
    cmd = [
        FFMPEG, "-y", "-i", str(in_path),
        "-filter_complex", vf,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-c:a", "aac",
        str(out_path),
    ]
    _run(cmd)


def crop_vertical_blurred_letterbox(in_path: Path, out_path: Path, width: int, height: int,
                                     zoom: float = 1.15) -> None:
    """
    Template B — blurred top/bottom bars (letterbox).
    FG: full 16:9 source scaled to fit width, centered vertically — entire frame visible.
    BG: same source zoomed 15% beyond frame and blurred to fill the full portrait canvas.
    The blurred zones above and below the main content are available for text overlays.
    """
    bg_h = int(height * zoom)
    vf = (
        f"[0:v]scale=-2:{bg_h},"
        f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2,"
        f"boxblur=30:3[bg];"
        f"[0:v]scale={width}:-2[fg];"
        f"[bg][fg]overlay=0:(H-h)/2[v]"
    )
    cmd = [
        FFMPEG, "-y", "-i", str(in_path),
        "-filter_complex", vf,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-c:a", "aac",
        str(out_path),
    ]
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
