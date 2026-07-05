import json
import os
import sys
import tempfile
from pathlib import Path

import ffmpeg_utils
import state

IS_MACOS = sys.platform == "darwin"

if IS_MACOS:
    import mlx_whisper
else:
    if sys.platform == "win32":
        # faster-whisper's CUDA backend (CTranslate2) loads cuBLAS/cuDNN via plain LoadLibrary,
        # which only searches PATH (not os.add_dll_directory-registered dirs). The
        # nvidia-cublas-cu12 / nvidia-cudnn-cu12 pip packages ship those DLLs under site-packages,
        # so put them on PATH for this process before ctranslate2/faster_whisper ever loads.
        _nvidia_pkg_dir = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
        if _nvidia_pkg_dir.is_dir():
            _bin_dirs = [str(p) for p in _nvidia_pkg_dir.glob("*/bin")]
            os.environ["PATH"] = os.pathsep.join(_bin_dirs + [os.environ.get("PATH", "")])

    from faster_whisper import WhisperModel

_model_cache: dict[str, "WhisperModel"] = {}


def _load_faster_whisper_model(model_size: str) -> "WhisperModel":
    if model_size not in _model_cache:
        for device, compute_type in [("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")]:
            try:
                _model_cache[model_size] = WhisperModel(model_size, device=device, compute_type=compute_type)
                break
            except Exception:
                continue
        else:
            raise RuntimeError(f"Could not load faster-whisper model '{model_size}' on any device")
    return _model_cache[model_size]


def _transcribe(video_path: Path, whisper_model: str) -> tuple[str | None, list[dict]]:
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        ffmpeg_utils.extract_audio(video_path, wav_path)

        if IS_MACOS:
            result = mlx_whisper.transcribe(
                str(wav_path),
                path_or_hf_repo=f"mlx-community/whisper-{whisper_model}-mlx",
                word_timestamps=True,
                verbose=False,
            )
            language = result.get("language")
            segments = [
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
            ]
        else:
            model = _load_faster_whisper_model(whisper_model)
            segments_iter, info = model.transcribe(str(wav_path), word_timestamps=True)
            language = info.language
            segments = [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "words": [
                        {"word": w.word, "start": w.start, "end": w.end}
                        for w in (seg.words or [])
                    ],
                }
                for seg in segments_iter
            ]

    return language, segments


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
    out_path.write_text("\n".join(lines), encoding="utf-8")


def run(video_id: str, video_path: Path, whisper_model: str, force: bool = False) -> dict:
    if not force and state.stage_done(video_id, "transcribe"):
        work_dir = state.work_dir_for(video_id)
        return json.loads((work_dir / "transcript.json").read_text())

    state.set_stage_status(video_id, "transcribe", "in_progress")
    work_dir = state.work_dir_for(video_id)

    language, segments = _transcribe(video_path, whisper_model)
    transcript = {"language": language, "segments": segments}

    (work_dir / "transcript.json").write_text(json.dumps(transcript, indent=2))
    _write_srt(transcript["segments"], work_dir / "transcript.srt")

    state.set_stage_status(video_id, "transcribe", "done", model=whisper_model)
    return transcript


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--whisper-model", default="medium")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    video_id = state.video_id_for(video_path)
    state.load_status(video_id, source_file=str(video_path))
    run(video_id, video_path, args.whisper_model, force=args.force)
    print(f"Transcribed {video_id}")
