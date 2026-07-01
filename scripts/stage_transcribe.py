import json
import tempfile
from pathlib import Path

import mlx_whisper

import ffmpeg_utils
import state


def _seconds_to_srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(segments: list[dict], out_path: Path) -> None:
    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_seconds_to_srt_time(seg['start'])} --> {_seconds_to_srt_time(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    out_path.write_text("\n".join(lines))


def run(video_id: str, video_path: Path, whisper_model: str, force: bool = False) -> dict:
    if not force and state.stage_done(video_id, "transcribe"):
        work_dir = state.work_dir_for(video_id)
        return json.loads((work_dir / "transcript.json").read_text())

    state.set_stage_status(video_id, "transcribe", "in_progress")
    work_dir = state.work_dir_for(video_id)

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        ffmpeg_utils.extract_audio(video_path, wav_path)
        result = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=whisper_model,
            word_timestamps=True,
            verbose=False,
        )

    transcript = {
        "language": result.get("language"),
        "segments": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "words": [
                    {"word": w["word"], "start": w["start"], "end": w["end"]}
                    for w in seg.get("words", [])
                ],
            }
            for seg in result["segments"]
        ],
    }

    (work_dir / "transcript.json").write_text(json.dumps(transcript, indent=2))
    _write_srt(transcript["segments"], work_dir / "transcript.srt")

    state.set_stage_status(video_id, "transcribe", "done", model=whisper_model)
    return transcript


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--whisper-model", default="mlx-community/whisper-medium-mlx")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    video_id = state.video_id_for(video_path)
    state.load_status(video_id, source_file=str(video_path))
    run(video_id, video_path, args.whisper_model, force=args.force)
    print(f"Transcribed {video_id}")
