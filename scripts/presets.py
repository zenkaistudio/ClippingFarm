import json
from pathlib import Path

import state

PRESETS_PATH = state.ROOT / "presets.json"

DEFAULT_PRESET = {
    "id": "",
    "name": "Default (config.json)",
    "watermark_text": "",
    "watermark_position": "bottom-right",
    "caption_highlight_color": "#FFCF00",
    "caption_base_color": "#FFFFFF",
}


def load_all() -> list[dict]:
    if not PRESETS_PATH.exists():
        return []
    return json.loads(PRESETS_PATH.read_text())


def save_all(presets: list[dict]) -> None:
    PRESETS_PATH.write_text(json.dumps(presets, indent=2))


def get(preset_id: str) -> dict:
    if not preset_id:
        return DEFAULT_PRESET
    for p in load_all():
        if p["id"] == preset_id:
            return p
    return DEFAULT_PRESET


def upsert(preset: dict) -> dict:
    presets = [p for p in load_all() if p["id"] != preset["id"]]
    presets.append(preset)
    save_all(presets)
    return preset


def delete(preset_id: str) -> None:
    save_all([p for p in load_all() if p["id"] != preset_id])
