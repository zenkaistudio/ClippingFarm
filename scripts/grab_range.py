"""
Download ONLY a time range of a YouTube stream as 1080p60 mp4 (h264 + aac).
Works on Mac and Windows, and on streams that are still live.

    python scripts/grab_range.py URL 9:51:30 9:59:00 "kai GTA6 skunk ape"

Still live: yt-dlp --download-sections fails on live DASH, so this fetches the
5 second DASH segments directly (url&sq=N, N = seconds / 5) for itag 299 (1080p60
h264) and 140 (aac), appends them, and muxes with ffmpeg -c copy. The start and end
snap to the 5 second segment grid.

Ended (VOD): hands off to yt-dlp --download-sections with the same formats.

Output goes to "yt downloads/<name> <start>-<end>.mp4".

--audio-only grabs just the aac track (small, fast) into "yt downloads/scout/" so a
30 minute section can be transcribed for scouting without pulling 1080p video.
"""
import argparse
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_utils import FFMPEG  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "yt downloads"
VIDEO_FMT = "299"  # 1080p60 h264
AUDIO_FMT = "140"  # aac 128k
SEG_SECONDS = 5


def yt_dlp_cmd() -> list[str]:
    if importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    # Homebrew copy first on Mac (the old Python 3.9 user copy hangs).
    for cand in ("/opt/homebrew/bin/yt-dlp", shutil.which("yt-dlp")):
        if cand and Path(cand).exists():
            return [cand]
    sys.exit("yt-dlp not found. Run: pip install -U yt-dlp (inside the venv)")


def parse_ts(text: str) -> int:
    parts = [int(p) for p in text.split(":")]
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    return secs


def label(secs: int) -> str:
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}" if h else f"{m}m{s:02d}"


def info(url: str, live: bool) -> dict:
    cmd = yt_dlp_cmd() + ["-j", "--no-warnings"]
    if live:
        cmd.append("--live-from-start")
    out = subprocess.run(cmd + [url], capture_output=True, text=True, check=True).stdout
    return json.loads(out.splitlines()[0])


def fetch_segments(fmt_url: str, first: int, last: int, dest: Path) -> None:
    sess = requests.Session()
    with open(dest, "wb") as fh:
        for n in range(first, last + 1):
            for attempt in range(4):
                r = sess.get(f"{fmt_url}&sq={n}", timeout=60, allow_redirects=True)
                if r.status_code == 200 and r.content:
                    fh.write(r.content)
                    break
            else:
                raise RuntimeError(
                    f"Segment {n} failed (HTTP {r.status_code}). The signed URL may have "
                    "expired; just rerun the command to get fresh URLs."
                )
            done = n - first + 1
            print(f"\r  {dest.stem}: {done}/{last - first + 1} segments", end="", flush=True)
    print()


def grab_live(meta: dict, start: int, end: int, out: Path, audio_only: bool = False) -> None:
    fmts = {f["format_id"]: f for f in meta["formats"]}
    first, last = start // SEG_SECONDS, math.ceil(end / SEG_SECONDS) - 1
    if audio_only:
        fetch_segments(fmts[AUDIO_FMT]["url"], first, last, out)
        return
    if VIDEO_FMT not in fmts or AUDIO_FMT not in fmts:
        sys.exit(f"Stream does not offer formats {VIDEO_FMT}+{AUDIO_FMT}. Available: {sorted(fmts)}")
    with tempfile.TemporaryDirectory() as tmp:
        v, a = Path(tmp) / "video.mp4", Path(tmp) / "audio.m4a"
        fetch_segments(fmts[VIDEO_FMT]["url"], first, last, v)
        fetch_segments(fmts[AUDIO_FMT]["url"], first, last, a)
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error", "-i", str(v), "-i", str(a),
             "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", str(out)],
            check=True,
        )


def grab_vod(url: str, start: int, end: int, out: Path, audio_only: bool = False) -> None:
    fmt = f"{AUDIO_FMT}/ba[ext=m4a]" if audio_only else \
        f"{VIDEO_FMT}+{AUDIO_FMT}/bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]"
    subprocess.run(
        yt_dlp_cmd() + [
            "-f", fmt,
            "--download-sections", f"*{start}-{end}",
            "--force-keyframes-at-cuts",
            *([] if audio_only else ["--merge-output-format", "mp4"]),
            "--ffmpeg-location", FFMPEG,
            "-o", str(out), url,
        ],
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("start", help="stream time, e.g. 9:51:30 or 46:35")
    ap.add_argument("end", help="stream time, e.g. 9:59:00")
    ap.add_argument("name", help='short name, e.g. "kai GTA6 skunk ape"')
    ap.add_argument("--audio-only", action="store_true", help="aac only, for scouting transcripts")
    args = ap.parse_args()

    start, end = parse_ts(args.start), parse_ts(args.end)
    if end <= start:
        sys.exit("end must be after start")
    out_dir = OUT_DIR / "scout" if args.audio_only else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "m4a" if args.audio_only else "mp4"
    out = out_dir / f"{args.name} {label(start)}-{label(end)}.{ext}"

    meta = info(args.url, live=False)
    live = meta.get("is_live") or meta.get("live_status") == "is_live"
    print(f"{meta.get('title')}  ({'LIVE' if live else 'VOD'})")
    if live:
        grab_live(info(args.url, live=True), start, end, out, args.audio_only)
    else:
        grab_vod(args.url, start, end, out, args.audio_only)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
