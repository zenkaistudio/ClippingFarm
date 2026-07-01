from pathlib import Path

import ffmpeg_utils
import state


def run(video_id: str, clip_ids: list[str], width: int, height: int, offset_x: int = 0,
        force: bool = False) -> None:
    if not force and state.stage_done(video_id, "reframe"):
        return

    state.set_stage_status(video_id, "reframe", "in_progress")
    work_dir = state.work_dir_for(video_id)

    for clip_id in clip_ids:
        clip_dir = work_dir / "clips" / clip_id
        ffmpeg_utils.crop_vertical(clip_dir / "raw.mp4", clip_dir / "vertical.mp4", width, height, offset_x)

    state.set_stage_status(video_id, "reframe", "done")


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--offset-x", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    video_id = state.video_id_for(video_path)
    work_dir = state.work_dir_for(video_id)
    candidates = json.loads((work_dir / "candidates.json").read_text())
    clip_ids = [f"clip{i + 1:02d}" for i in range(len(candidates))]
    run(video_id, clip_ids, args.width, args.height, args.offset_x, force=args.force)
    print(f"Reframed {len(clip_ids)} clips")
