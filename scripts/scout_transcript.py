"""
Transcribe a scouting audio file and print it with STREAM timestamps.
Uses the farm's own transcriber (mlx-whisper on Mac, faster-whisper on Windows).

    python scripts/scout_transcript.py "yt downloads/scout/kai 9h00m00-9h30m00.m4a" 9:00:00

The second argument is the stream time the file starts at, so every line reads as
a real stream timestamp. Lines with shouting cues (caps, "bro", "what", "no") are
marked with * to speed up skimming for deaths, fights and cops.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grab_range import parse_ts  # noqa: E402
from stage_transcribe import _transcribe  # noqa: E402

HOT = re.compile(r"\b(no+|what+|bro+|chat|yo+|died|dead|police|cops?|wanted|shot|run+|fight)\b", re.I)


def clock(secs: float) -> str:
    s = int(secs)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("stream_start", help="stream time the file starts at, e.g. 9:00:00")
    ap.add_argument("--model", default="medium")
    args = ap.parse_args()

    offset = parse_ts(args.stream_start)
    _, segments = _transcribe(Path(args.audio), args.model)
    out_lines = []
    for seg in segments:
        text = seg["text"].strip()
        mark = "*" if HOT.search(text) or "!" in text else " "
        out_lines.append(f"{mark} [{clock(offset + seg['start'])}] {text}")
    out = Path(args.audio).with_suffix(".txt")
    out.write_text("\n".join(out_lines), encoding="utf-8")
    print("\n".join(out_lines))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
