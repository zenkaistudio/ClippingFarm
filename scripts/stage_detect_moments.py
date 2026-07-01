import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

import state

PROMPT_PATH = Path(__file__).parent / "prompts" / "moment_detection.md"

CLIP_TOOL = {
    "name": "select_clip_moments",
    "description": "Return the selected short-clip moments from the transcript.",
    "input_schema": {
        "type": "object",
        "properties": {
            "moments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                        "hook_title": {"type": "string"},
                        "rationale": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": [
                                "emotional_peak",
                                "punchline",
                                "controversial_take",
                                "surprising_reveal",
                                "strong_hook",
                                "other",
                            ],
                        },
                        "virality_score": {"type": "number"},
                    },
                    "required": ["start", "end", "hook_title", "rationale", "category", "virality_score"],
                },
            }
        },
        "required": ["moments"],
    },
}


def _format_transcript(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text'].strip()}")
    return "\n".join(lines)


def run(video_id: str, transcript: dict, num_clips: int, min_length: int, max_length: int,
        claude_model: str, force: bool = False) -> list[dict]:
    work_dir = state.work_dir_for(video_id)
    if not force and state.stage_done(video_id, "detect_moments"):
        return json.loads((work_dir / "candidates.json").read_text())

    state.set_stage_status(video_id, "detect_moments", "in_progress")

    load_dotenv(Path(__file__).parent.parent / ".env")
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    segments = transcript["segments"]
    duration = segments[-1]["end"] if segments else 0.0
    prompt = PROMPT_PATH.read_text().format(
        num_clips=num_clips,
        min_length=min_length,
        max_length=max_length,
        transcript=_format_transcript(segments),
    )

    response = client.messages.create(
        model=claude_model,
        max_tokens=4096,
        tools=[CLIP_TOOL],
        tool_choice={"type": "tool", "name": "select_clip_moments"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use = next(b for b in response.content if b.type == "tool_use")
    moments = tool_use.input["moments"]

    # Clamp to transcript bounds, drop invalid ranges, sort by score, truncate.
    cleaned = []
    for m in moments:
        start = max(0.0, min(float(m["start"]), duration))
        end = max(0.0, min(float(m["end"]), duration))
        if end <= start:
            continue
        m["start"], m["end"] = start, end
        cleaned.append(m)

    cleaned.sort(key=lambda m: m["virality_score"], reverse=True)
    cleaned = cleaned[:num_clips]

    (work_dir / "candidates.json").write_text(json.dumps(cleaned, indent=2))
    state.set_stage_status(video_id, "detect_moments", "done", num_candidates=len(cleaned))
    return cleaned


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--num-clips", type=int, default=6)
    parser.add_argument("--min-length", type=int, default=20)
    parser.add_argument("--max-length", type=int, default=60)
    parser.add_argument("--claude-model", default="claude-sonnet-4-6")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    video_id = state.video_id_for(video_path)
    transcript = json.loads((state.work_dir_for(video_id) / "transcript.json").read_text())
    candidates = run(video_id, transcript, args.num_clips, args.min_length, args.max_length,
                      args.claude_model, force=args.force)
    print(f"Found {len(candidates)} candidates")
