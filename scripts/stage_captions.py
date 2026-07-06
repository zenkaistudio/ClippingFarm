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
Style: Caption,Arial Black,{caption_fontsize},{highlight_color},{base_color},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,2,2,40,40,{caption_margin_v},1
Style: Title,Arial Black,{title_fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,2,8,40,40,{title_margin_v},1
Style: Watermark,Arial Black,{watermark_fontsize},&H99FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,{watermark_alignment},20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

WATERMARK_ALIGNMENTS = {
    "bottom-right": 3,
    "bottom-left": 1,
    "top-right": 9,
    "top-left": 7,
}


def _hex_to_ass_color(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f"&H00{b}{g}{r}".upper()

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


def _strip_emoji(text: str) -> str:
    emoji_re = re.compile(
        "[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002194-\U00002199"
        "\U00002934-\U00002935"
        "\U000025AA-\U000025FE"
        "\U00002614-\U00002615"
        "\U00002648-\U00002653"
        "\U0000267F"
        "\U00002693"
        "\U000026A1"
        "\U000026AA-\U000026AB"
        "\U000026BD-\U000026BE"
        "\U000026C4-\U000026C5"
        "\U000026CE"
        "\U000026D4"
        "\U000026EA"
        "\U000026F2-\U000026F3"
        "\U000026F5"
        "\U000026FA"
        "\U000026FD"
        "\U00002702"
        "\U00002705"
        "\U00002708-\U0000270D"
        "\U0000270F"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_re.sub("", text).strip()


def _render_title_with_emphasis(hook_title: str, highlight_color: str) -> str:
    # Wraps *word* spans from the hook_title (see prompts/moment_detection.md) in bold +
    # highlight-color ASS override tags, matching the karaoke caption highlight color.
    parts = re.split(r"\*(.+?)\*", hook_title)
    rendered = []
    for i, part in enumerate(parts):
        if not part:
            continue
        escaped = _escape(part)
        if i % 2 == 1:
            rendered.append(f"{{\\b1\\c{highlight_color}&}}{escaped}{{\\b0\\c&H00FFFFFF&}}")
        else:
            rendered.append(escaped)
    return "".join(rendered)


def _title_dialogue(hook_title: str, clip_duration: float, highlight_color: str) -> str:
    text = _render_title_with_emphasis(_strip_emoji(hook_title), highlight_color)
    return f"Dialogue: 0,{_ass_time(0)},{_ass_time(clip_duration)},Title,,0,0,0,,{text}"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.replace("*", "")).strip("_").lower()
    return slug[:50]


def _watermark_dialogue(text: str, clip_duration: float) -> str:
    return f"Dialogue: 0,{_ass_time(0)},{_ass_time(clip_duration)},Watermark,,0,0,0,,{_escape(text)}"


def build_ass(words: list[dict], hook_title: str, clip_duration: float, width: int, height: int,
              watermark_text: str = "", highlight_color: str | None = None,
              base_color: str | None = None, watermark_position: str | None = None) -> str:
    caption_fontsize = max(36, width // 14)
    title_fontsize = max(40, width // 12)
    watermark_fontsize = max(24, width // 36)
    highlight_ass = _hex_to_ass_color(highlight_color) if highlight_color else "&H0000FFFF"
    base_ass = _hex_to_ass_color(base_color) if base_color else "&H00FFFFFF"
    watermark_alignment = WATERMARK_ALIGNMENTS.get(watermark_position, 3)
    header = ASS_HEADER.format(
        width=width,
        height=height,
        caption_fontsize=caption_fontsize,
        title_fontsize=title_fontsize,
        watermark_fontsize=watermark_fontsize,
        caption_margin_v=int(height * 0.27),
        title_margin_v=int(height * 0.15),
        highlight_color=highlight_ass,
        base_color=base_ass,
        watermark_alignment=watermark_alignment,
    )
    dialogues = [_title_dialogue(hook_title, clip_duration, highlight_ass)] + _caption_dialogues(words)
    if watermark_text:
        dialogues.append(_watermark_dialogue(watermark_text, clip_duration))
    body = "\n".join(dialogues)
    return header + body + "\n"


def run(video_id: str, transcript: dict, candidates: list[dict], clip_ids: list[str],
        width: int, height: int, watermark_text: str = "", highlight_color: str | None = None,
        base_color: str | None = None, watermark_position: str | None = None,
        force: bool = False) -> list[Path]:
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

        ass_content = build_ass(words, candidate["hook_title"], clip_duration, width, height,
                                watermark_text=watermark_text, highlight_color=highlight_color,
                                base_color=base_color, watermark_position=watermark_position)
        ass_path = clip_dir / "captions.ass"
        ass_path.write_text(ass_content, encoding="utf-8")

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
