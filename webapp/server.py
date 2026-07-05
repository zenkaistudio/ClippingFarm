import json
import queue
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import state  # noqa: E402
import stage_captions  # noqa: E402
import stage_cut_clips  # noqa: E402
import stage_detect_moments  # noqa: E402
import stage_reframe  # noqa: E402
import stage_transcribe  # noqa: E402

ROOT = state.ROOT
UPLOADS_DIR = ROOT / "uploads"
OUTPUT_DIR = ROOT / "output"
UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

STAGES = ["transcribe", "detect_moments", "cut", "reframe", "captions"]

app = Flask(__name__)

job_queue: "queue.Queue[dict]" = queue.Queue()
lock = threading.Lock()
dashboard_state = {"current": None, "queued": [], "completed": []}


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text())


def _process_job(job: dict) -> None:
    video_id = job["video_id"]
    video_path = job["video_path"]
    config = load_config()
    min_len = config["clip_length_seconds"]["min"]
    max_len = config["clip_length_seconds"]["max"]
    width = config["output_resolution"]["width"]
    height = config["output_resolution"]["height"]
    offset_x = config.get("crop_offset_x", 0)

    with lock:
        dashboard_state["current"] = {
            "video_id": video_id,
            "filename": job["filename"],
            "stage": None,
            "status": "in_progress",
            "error": None,
        }

    def set_stage(stage_name: str) -> None:
        with lock:
            dashboard_state["current"]["stage"] = stage_name

    try:
        set_stage("transcribe")
        transcript = stage_transcribe.run(video_id, video_path, config["whisper_model"])

        set_stage("detect_moments")
        candidates = stage_detect_moments.run(
            video_id, transcript, job["num_clips"], min_len, max_len, config["claude_model"]
        )

        set_stage("cut")
        clip_ids = stage_cut_clips.run(video_id, video_path, candidates)

        set_stage("reframe")
        stage_reframe.run(video_id, clip_ids, width, height, offset_x)

        set_stage("captions")
        final_paths = stage_captions.run(video_id, transcript, candidates, clip_ids, width, height)

        clips = [
            {
                "filename": path.name,
                "hook_title": candidate.get("hook_title", ""),
                "category": candidate.get("category", ""),
                "virality_score": candidate.get("virality_score", 0),
            }
            for path, candidate in zip(final_paths, candidates)
        ]

        with lock:
            dashboard_state["current"]["status"] = "done"
            dashboard_state["completed"].insert(
                0, {"video_id": video_id, "filename": job["filename"], "clips": clips, "error": None}
            )
    except Exception as exc:
        with lock:
            dashboard_state["current"]["status"] = "error"
            dashboard_state["current"]["error"] = str(exc)
            dashboard_state["completed"].insert(
                0, {"video_id": video_id, "filename": job["filename"], "clips": [], "error": str(exc)}
            )


def _worker() -> None:
    while True:
        job = job_queue.get()
        with lock:
            dashboard_state["queued"] = [
                j for j in dashboard_state["queued"] if j["video_id"] != job["video_id"]
            ]
        _process_job(job)


threading.Thread(target=_worker, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html", default_num_clips=load_config().get("num_clips", 6))


@app.route("/api/upload", methods=["POST"])
def upload():
    file = request.files.get("video")
    if file is None or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    default_num_clips = load_config().get("num_clips", 6)
    num_clips = int(request.form.get("num_clips") or default_num_clips)

    dest = UPLOADS_DIR / file.filename
    stem, suffix = dest.stem, dest.suffix
    counter = 1
    while dest.exists():
        dest = UPLOADS_DIR / f"{stem}_{counter}{suffix}"
        counter += 1
    file.save(dest)

    video_id = state.video_id_for(dest)
    state.load_status(video_id, source_file=str(dest))

    job = {
        "video_id": video_id,
        "video_path": dest,
        "filename": dest.name,
        "num_clips": num_clips,
    }
    with lock:
        dashboard_state["queued"].append({"video_id": video_id, "filename": dest.name})
    job_queue.put(job)

    return jsonify({"video_id": video_id, "position": job_queue.qsize()})


@app.route("/api/status")
def status():
    with lock:
        return jsonify(
            {
                "stages": STAGES,
                "current": dashboard_state["current"],
                "queued": list(dashboard_state["queued"]),
                "completed": dashboard_state["completed"][:20],
            }
        )


@app.route("/clips/<path:filename>")
def clips(filename):
    return send_from_directory(OUTPUT_DIR, filename)


def _open_in_chrome(url: str) -> None:
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
    ]
    for chrome_path in chrome_paths:
        if Path(chrome_path).exists():
            subprocess.Popen([chrome_path, url])
            return
    webbrowser.open(url)  # fall back only if Chrome isn't found at a known path


if __name__ == "__main__":
    threading.Timer(1.0, lambda: _open_in_chrome("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, threaded=True)
