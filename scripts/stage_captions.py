import json
import re
import shutil
from pathlib import Path

import ffmpeg_utils
import state

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial Black,{caption_fontsize},&H0000FFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,2,2,40,40,{caption_margin_v},1
Style: Title,Arial Black,{title_fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,2,8,40,40,{title_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

WORDS_PER_CHUNK = 4
PAUSE_BREAK_SECONDS = 0.6


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


def _words_for_clip(transcript: dict, clip_start: float, clip_end: float) -> list[dict]:
    words = []
    for seg in transcript["segments"]:
        for w in seg.get("words", []):
            if w["start"] >= clip_start - 0.05 and w["end"] <= clip_end + 0.05:
                words.append({
                    "word": w["word"],
                    "start": max(0.0, w["start"] - clip_start),
                    "end": max(0.0, w["end"] - clip_start),
                })
    return words


def _chunk_words(words: list[dict]) -> list[list[dict]]:
    chunks = []
    current = []
    for w in words:
        if current and (len(current) >= WORDS_PER_CHUNK or w["start"] - current[-1]["end"] > PAUSE_BREAK_SECONDS):
            chunks.append(current)
            current = []
        current.append(w)
    if current:
        chunks.append(current)
    return chunks


def _caption_dialogues(words: list[dict]) -> list[str]:
    lines = []
    for chunk in _chunk_words(words):
        line_start = chunk[0]["start"]
        line_end = chunk[-1]["end"]
        text_parts = []
        prev_time = line_start
        for w in chunk:
            dur_cs = max(1, int(round((w["end"] - prev_time) * 100)))
            text_parts.append(f"{{\\k{dur_cs}}}{_escape(w['word'].strip())}")
            prev_time = w["end"]
        text = " ".join(text_parts)
        lines.append(f"Dialogue: 0,{_ass_time(line_start)},{_ass_time(line_end)},Caption,,0,0,0,,{text}")
    return lines


def _title_dialogue(hook_title: str, clip_duration: float) -> str:
    return f"Dialogue: 0,{_ass_time(0)},{_ass_time(clip_duration)},Title,,0,0,0,,{_escape(hook_title)}"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug[:50]


def build_ass(words: list[dict], hook_title: str, clip_duration: float, width: int, height: int) -> str:
    caption_fontsize = max(36, width // 14)
    title_fontsize = max(32, width // 16)
    header = ASS_HEADER.format(
        width=width,
        height=height,
        caption_fontsize=caption_fontsize,
        title_fontsize=title_fontsize,
        caption_margin_v=int(height * 0.12),
        title_margin_v=int(height * 0.08),
    )
    body = "\n".join([_title_dialogue(hook_title, clip_duration)] + _caption_dialogues(words))
    return header + body + "\n"


def run(video_id: str, transcript: dict, candidates: list[dict], clip_ids: list[str],
        width: int, height: int, force: bool = False) -> list[Path]:
    work_dir = state.work_dir_for(video_id)
    output_dir = state.ROOT / "output"
    output_dir.mkdir(exist_ok=True)

    if not force and state.stage_done(video_id, "captions"):
        return sorted(output_dir.glob(f"{video_id}__*"))

    state.set_stage_status(video_id, "captions", "in_progress")

    final_paths = []
    for clip_id, candidate in zip(clip_ids, candidates):
        clip_dir = work_dir / "clips" / clip_id
        clip_duration = candidate["end"] - candidate["start"]
        words = _words_for_clip(transcript, candidate["start"], candidate["end"])

        ass_content = build_ass(words, candidate["hook_title"], clip_duration, width, height)
        ass_path = clip_dir / "captions.ass"
        ass_path.write_text(ass_content)

        final_path = clip_dir / "final.mp4"
        ffmpeg_utils.burn_ass(clip_dir / "vertical.mp4", ass_path, final_path)

        slug = _slugify(candidate["hook_title"])
        out_name = f"{video_id}__{clip_id}__{slug}.mp4"
        out_path = output_dir / out_name
        shutil.copyfile(final_path, out_path)
        final_paths.append(out_path)

    state.set_stage_status(video_id, "captions", "done", num_clips=len(final_paths))
    return final_paths


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    video_id = state.video_id_for(video_path)
    work_dir = state.work_dir_for(video_id)
    transcript = json.loads((work_dir / "transcript.json").read_text())
    candidates = json.loads((work_dir / "candidates.json").read_text())
    clip_ids = [f"clip{i + 1:02d}" for i in range(len(candidates))]
    paths = run(video_id, transcript, candidates, clip_ids, args.width, args.height, force=args.force)
    print(f"Wrote {len(paths)} final clips to output/")
