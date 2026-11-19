"""
Print the top Most Replayed peaks of a YouTube video or ENDED stream.
(Live streams have no heatmap yet; YouTube adds it after the stream ends.)

    python scripts/scout_heatmap.py URL            # top 15 peaks
    python scripts/scout_heatmap.py URL --top 25 --after 9:00:00 --before 9:30:00

Each peak is merged with its neighbours into one window, so you get moments,
not 30 rows from the same scene. Pair this with the transcript of each window
to write the ranked list for Mal.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grab_range import label, parse_ts, yt_dlp_cmd  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--after", default="0:00")
    ap.add_argument("--before", default="99:00:00")
    args = ap.parse_args()

    out = subprocess.run(yt_dlp_cmd() + ["-j", "--no-warnings", args.url],
                         capture_output=True, text=True, check=True).stdout
    meta = json.loads(out.splitlines()[0])
    heat = meta.get("heatmap") or []
    if not heat:
        sys.exit("No Most Replayed data (stream still live, too new, or too few views).")

    lo, hi = parse_ts(args.after), parse_ts(args.before)
    heat = [h for h in heat if lo <= h["start_time"] < hi]
    avg = sum(h["value"] for h in heat) / max(len(heat), 1)

    # Merge adjacent above-average buckets into windows, score by peak value.
    windows, cur = [], None
    for h in heat:
        if h["value"] >= avg * 1.3:
            if cur and h["start_time"] <= cur["end"] + 1:
                cur["end"] = h["end_time"]
                cur["peak"] = max(cur["peak"], h["value"])
            else:
                cur = {"start": h["start_time"], "end": h["end_time"], "peak": h["value"]}
                windows.append(cur)
        else:
            cur = None

    windows.sort(key=lambda w: w["peak"], reverse=True)
    print(f"{meta.get('title')}\n")
    for i, w in enumerate(windows[: args.top], 1):
        print(f"{i:>2}. {label(int(w['start'])):>9} to {label(int(w['end'])):<9}  peak {w['peak']:.2f}")


if __name__ == "__main__":
    main()
