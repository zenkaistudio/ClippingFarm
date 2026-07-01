import json
from pathlib import Path

import ffmpeg_utils
import state


def clip_id_for(index: int) -> str:
    return f"clip{index + 1:02d}"


def run(video_id: str, video_path: Path, candidates: list[dict], force: bool = False) -> list[str]:
    work_dir = state.work_dir_for(video_id)
    if not force and state.stage_done(video_id, "cut"):
        return [clip_id_for(i) for i in range(len(candidates))]

    state.set_stage_status(video_id, "cut", "in_progress")

    clip_ids = []
    for i, candidate in enumerate(candidates):
        clip_id = clip_id_for(i)
        clip_dir = work_dir / "clips" / clip_id
        clip_dir.mkdir(parents=True, exist_ok=True)
        (clip_dir / "meta.json").write_text(json.dumps(candidate, indent=2))
        ffmpeg_utils.cut_clip(video_path, candidate["start"], candidate["end"], clip_dir / "raw.mp4")
        clip_ids.append(clip_id)

    state.set_stage_status(video_id, "cut", "done", num_clips=len(clip_ids))
    return clip_ids


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    video_id = state.video_id_for(video_path)
    work_dir = state.work_dir_for(video_id)
    candidates = json.loads((work_dir / "candidates.json").read_text())
    clip_ids = run(video_id, video_path, candidates, force=args.force)
    print(f"Cut {len(clip_ids)} clips: {clip_ids}")
