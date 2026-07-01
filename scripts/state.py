import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = ROOT / "work"

STAGES = ["transcribe", "detect_moments", "cut", "reframe", "captions"]


def video_id_for(source_path: Path) -> str:
    stem = source_path.stem
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    sha1 = hashlib.sha1(str(source_path.resolve()).encode()).hexdigest()[:6]
    return f"{slug}_{sha1}"


def work_dir_for(video_id: str) -> Path:
    d = WORK_DIR / video_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "clips").mkdir(exist_ok=True)
    return d


def status_path(video_id: str) -> Path:
    return work_dir_for(video_id) / "status.json"


def load_status(video_id: str, source_file: str | None = None) -> dict:
    path = status_path(video_id)
    if path.exists():
        return json.loads(path.read_text())
    status = {
        "video_id": video_id,
        "source_file": source_file,
        "stages": {stage: {"status": "pending"} for stage in STAGES},
    }
    save_status(video_id, status)
    return status


def save_status(video_id: str, status: dict) -> None:
    status_path(video_id).write_text(json.dumps(status, indent=2))


def stage_done(video_id: str, stage: str) -> bool:
    status = load_status(video_id)
    return status["stages"].get(stage, {}).get("status") == "done"


def set_stage_status(video_id: str, stage: str, status_value: str, **extra) -> None:
    status = load_status(video_id)
    status["stages"].setdefault(stage, {})
    status["stages"][stage]["status"] = status_value
    status["stages"][stage].update(extra)
    save_status(video_id, status)
