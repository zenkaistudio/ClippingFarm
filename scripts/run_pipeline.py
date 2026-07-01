import argparse
import json
from pathlib import Path

import state
import stage_transcribe
import stage_detect_moments
import stage_cut_clips
import stage_reframe
import stage_captions

ROOT = state.ROOT


def load_config() -> dict:
    config_path = ROOT / "config.json"
    return json.loads(config_path.read_text())


def resolve_input(input_arg: str) -> Path:
    path = Path(input_arg)
    if path.exists():
        return path.resolve()
    candidate = ROOT / "input" / input_arg
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(f"Could not find input video: {input_arg}")


def main():
    parser = argparse.ArgumentParser(description="Run the clipping pipeline on a VOD.")
    parser.add_argument("--input", required=True, help="Path to video, or filename within input/")
    parser.add_argument("--stage", default="all",
                         choices=["all", "transcribe", "detect_moments", "cut", "reframe", "captions"])
    parser.add_argument("--num-clips", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config = load_config()
    num_clips = args.num_clips or config["num_clips"]
    min_len = config["clip_length_seconds"]["min"]
    max_len = config["clip_length_seconds"]["max"]
    width = config["output_resolution"]["width"]
    height = config["output_resolution"]["height"]
    offset_x = config.get("crop_offset_x", 0)

    video_path = resolve_input(args.input)
    video_id = state.video_id_for(video_path)
    state.load_status(video_id, source_file=str(video_path))
    work_dir = state.work_dir_for(video_id)

    stages_to_run = (
        ["transcribe", "detect_moments", "cut", "reframe", "captions"]
        if args.stage == "all" else [args.stage]
    )

    transcript = None
    candidates = None
    clip_ids = None

    if "transcribe" in stages_to_run:
        transcript = stage_transcribe.run(video_id, video_path, config["whisper_model"], force=args.force)
        print(f"[transcribe] done -> {work_dir / 'transcript.json'}")

    if "detect_moments" in stages_to_run:
        if transcript is None:
            transcript = json.loads((work_dir / "transcript.json").read_text())
        candidates = stage_detect_moments.run(
            video_id, transcript, num_clips, min_len, max_len, config["claude_model"], force=args.force
        )
        print(f"[detect_moments] found {len(candidates)} candidates")

    if "cut" in stages_to_run:
        if candidates is None:
            candidates = json.loads((work_dir / "candidates.json").read_text())
        clip_ids = stage_cut_clips.run(video_id, video_path, candidates, force=args.force)
        print(f"[cut] cut {len(clip_ids)} clips")

    if "reframe" in stages_to_run:
        if candidates is None:
            candidates = json.loads((work_dir / "candidates.json").read_text())
        if clip_ids is None:
            clip_ids = [f"clip{i + 1:02d}" for i in range(len(candidates))]
        stage_reframe.run(video_id, clip_ids, width, height, offset_x, force=args.force)
        print(f"[reframe] reframed {len(clip_ids)} clips")

    if "captions" in stages_to_run:
        if transcript is None:
            transcript = json.loads((work_dir / "transcript.json").read_text())
        if candidates is None:
            candidates = json.loads((work_dir / "candidates.json").read_text())
        if clip_ids is None:
            clip_ids = [f"clip{i + 1:02d}" for i in range(len(candidates))]
        final_paths = stage_captions.run(video_id, transcript, candidates, clip_ids, width, height, force=args.force)
        print(f"[captions] wrote {len(final_paths)} final clips:")
        for p in final_paths:
            print(f"  {p}")


if __name__ == "__main__":
    main()
