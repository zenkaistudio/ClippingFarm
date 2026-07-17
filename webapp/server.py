import json
import os
import queue
import re
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import airtable_client  # noqa: E402
import presets  # noqa: E402
import state  # noqa: E402
import stage_captions  # noqa: E402
import stage_cut_clips  # noqa: E402
import stage_detect_moments  # noqa: E402
import stage_reframe  # noqa: E402
import stage_schedule  # noqa: E402
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
    crop_mode = config.get("crop_mode", "center")
    bg_fill = config.get("bg_fill", "none")

    preset = presets.get(job.get("preset_id", ""))
    watermark_text = preset["watermark_text"] or config.get("watermark_text", "")
    highlight_color = preset["caption_highlight_color"]
    base_color = preset["caption_base_color"]
    watermark_position = preset["watermark_position"]
    title_enabled = job.get("title_enabled", True)

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
        stage_reframe.run(video_id, clip_ids, width, height, offset_x, crop_mode=crop_mode, bg_fill=bg_fill)

        set_stage("captions")
        final_paths = stage_captions.run(video_id, transcript, candidates, clip_ids, width, height,
                                         watermark_text=watermark_text, highlight_color=highlight_color,
                                         base_color=base_color, watermark_position=watermark_position,
                                         title_enabled=title_enabled)

        clips = [
            {
                "filename": path.name,
                "hook_title": candidate.get("hook_title", "").replace("*", ""),
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
    preset_id = request.form.get("preset_id") or ""
    title_enabled = (request.form.get("title_enabled") or "true").lower() != "false"

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
        "preset_id": preset_id,
        "title_enabled": title_enabled,
    }
    with lock:
        dashboard_state["queued"].append({"video_id": video_id, "filename": dest.name})
    job_queue.put(job)

    return jsonify({"video_id": video_id, "position": job_queue.qsize()})


@app.route("/api/presets", methods=["GET"])
def list_presets():
    return jsonify(presets.load_all())


@app.route("/api/presets", methods=["POST"])
def save_preset():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400

    preset_id = data.get("id") or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    preset = {
        "id": preset_id,
        "name": name,
        "watermark_text": data.get("watermark_text", ""),
        "watermark_position": data.get("watermark_position", "bottom-right"),
        "caption_highlight_color": data.get("caption_highlight_color", "#FFCF00"),
        "caption_base_color": data.get("caption_base_color", "#FFFFFF"),
    }
    presets.upsert(preset)
    return jsonify(preset)


@app.route("/api/presets/<preset_id>", methods=["DELETE"])
def delete_preset(preset_id):
    presets.delete(preset_id)
    return jsonify({"success": True})


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


_PLATFORM_FIELDS = {
    "tiktok": ("Post to TikTok", "Buffer Post ID - TikTok"),
    "instagram_reels": ("Post to Instagram Reels", "Buffer Post ID - Instagram"),
    "youtube_shorts": ("Post to YouTube Shorts", "Buffer Post ID - YouTube"),
}


@app.route("/api/ship", methods=["POST"])
def ship_clip():
    """Manual, per-clip action: upload to Cloudinary, post to every configured Buffer
    channel, and log the result to Airtable - all in one click. Never triggered
    automatically by the pipeline."""
    data = request.get_json()
    filename = data.get("filename")
    hook_title = data.get("hook_title", "")
    category = data.get("category", "highlight")
    virality_score = data.get("virality_score", 0)

    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    clip_path = OUTPUT_DIR / filename
    if not clip_path.exists():
        return jsonify({"error": f"Clip not found: {filename}"}), 404

    video_id, clip_id = (filename.rsplit(".", 1)[0].split("__", 2) + ["", ""])[:2]

    config = load_config()
    channel_ids = {p: cid for p, cid in config.get("buffer_channel_ids", {}).items() if cid}
    buffer_token = os.environ.get("BUFFER_ACCESS_TOKEN", "")

    if not channel_ids:
        return jsonify({"error": "No Buffer channels configured in config.json"}), 400
    if not buffer_token:
        return jsonify({"error": "BUFFER_ACCESS_TOKEN not set in .env"}), 400

    try:
        result = stage_schedule.run(
            clip_path=clip_path,
            hook_title=hook_title,
            category=category,
            platform_channel_ids=channel_ids,
            buffer_token=buffer_token,
        )
    except Exception as exc:
        return jsonify({"error": f"Cloudinary/Buffer step failed: {exc}"}), 500

    fields = {
        "Video ID": video_id,
        "Clip ID": clip_id,
        "Clip Filename": filename,
        "Hook Title": hook_title,
        "Category": category,
        "Virality Score": virality_score,
        "Clip Video": [{"url": result["cloudinary_url"]}],
        "Clip URL": result["cloudinary_url"],
    }
    errors = []
    for r in result["buffer_results"]:
        checkbox_field, id_field = _PLATFORM_FIELDS.get(r["platform"], (None, None))
        if checkbox_field:
            fields[checkbox_field] = True
        if "post" in r and id_field:
            fields[id_field] = r["post"]["id"]
        if "error" in r:
            errors.append(f"{r['platform']}: {r['error']}")
    fields["Status"] = "Failed" if errors else "Scheduled"
    if errors:
        fields["Sync Error"] = "; ".join(errors)

    try:
        airtable_client.ensure_clips_table()
        record = airtable_client.create_record(fields)
    except Exception as exc:
        return jsonify({
            "error": f"Posted to Buffer but Airtable logging failed: {exc}",
            "buffer_results": result["buffer_results"],
        }), 500

    return jsonify({
        "success": not errors,
        "buffer_results": result["buffer_results"],
        "airtable_record_id": record.get("id"),
    })


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
    threading.Timer(1.0, lambda: _open_in_chrome("http://127.0.0.1:5050")).start()
    app.run(host="127.0.0.1", port=5050, threaded=True)
