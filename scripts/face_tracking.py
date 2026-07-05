import subprocess
import urllib.request
from pathlib import Path

import cv2

import ffmpeg_utils

MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "face_detector"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
MODEL_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"

CONFIDENCE_THRESHOLD = 0.6
SAMPLE_FPS = 2.0
SMOOTHING_WINDOW = 5

_detector = None
_detector_size = None


def _ensure_model() -> Path | None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if not MODEL_PATH.exists():
            urllib.request.urlretrieve(YUNET_URL, MODEL_PATH)
    except Exception:
        return None
    return MODEL_PATH


def _get_detector(input_size: tuple[int, int]):
    global _detector, _detector_size
    if _detector is None:
        model_path = _ensure_model()
        if model_path is None:
            return None
        _detector = cv2.FaceDetectorYN.create(str(model_path), "", input_size, CONFIDENCE_THRESHOLD, 0.3, 5000)
        _detector_size = input_size
    elif _detector_size != input_size:
        _detector.setInputSize(input_size)
        _detector_size = input_size
    return _detector


def _detect_face_center_x(detector, frame) -> float | None:
    h, w = frame.shape[:2]
    if (w, h) != _detector_size:
        detector.setInputSize((w, h))
    _, faces = detector.detect(frame)
    if faces is None or len(faces) == 0:
        return None

    weighted_sum = 0.0
    total_weight = 0.0
    for face in faces:
        x, y, fw, fh = face[0:4]
        confidence = float(face[-1])
        weight = confidence * max(0.0, float(fw))
        weighted_sum += (x + fw / 2.0) * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else None


def _compute_smoothed_path(video_path: Path, detector) -> list[tuple[float, float]] | None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    frame_interval = max(1, round(fps / SAMPLE_FPS))

    raw_samples: list[tuple[float, float | None]] = []
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_interval == 0:
            raw_samples.append((frame_idx / fps, _detect_face_center_x(detector, frame)))
        frame_idx += 1
    cap.release()

    if not raw_samples or all(cx is None for _, cx in raw_samples):
        return None

    fallback = frame_width / 2.0
    filled = []
    last = fallback
    for t, cx in raw_samples:
        if cx is not None:
            last = cx
        filled.append((t, last))

    values = [v for _, v in filled]
    smoothed = []
    for i, (t, _) in enumerate(filled):
        lo = max(0, i - SMOOTHING_WINDOW)
        hi = min(len(values), i + SMOOTHING_WINDOW + 1)
        smoothed.append((t, sum(values[lo:hi]) / (hi - lo)))
    return smoothed


def _offset_at(path: list[tuple[float, float]], t: float) -> float:
    if t <= path[0][0]:
        return path[0][1]
    if t >= path[-1][0]:
        return path[-1][1]
    for (t0, v0), (t1, v1) in zip(path, path[1:]):
        if t0 <= t <= t1:
            if t1 == t0:
                return v0
            frac = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * frac
    return path[-1][1]


def crop_with_face_tracking(in_path: Path, out_path: Path, width: int, height: int) -> bool:
    probe_cap = cv2.VideoCapture(str(in_path))
    if not probe_cap.isOpened():
        probe_cap.release()
        return False
    probe_w = probe_cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    probe_h = probe_cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    probe_cap.release()

    detector = _get_detector((int(probe_w), int(probe_h)))
    if detector is None:
        return False

    path = _compute_smoothed_path(in_path, detector)
    if path is None:
        return False

    cap = cv2.VideoCapture(str(in_path))
    if not cap.isOpened():
        return False

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    src_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    src_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    scaled_w = round(src_w * (height / src_h))

    # cv2.VideoWriter's bundled codecs are unreliable across platforms/builds (no working
    # H.264 encoder in many opencv-python wheels), so pipe raw cropped frames straight into
    # our own ffmpeg instead, which also mixes the original audio track back in directly.
    cmd = [
        ffmpeg_utils.FFMPEG, "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        "-i", str(in_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        str(out_path),
    ]
    # stderr must not be a PIPE we never drain: ffmpeg writes progress continuously, and once
    # that pipe's OS buffer fills, ffmpeg blocks writing to it, which then blocks our
    # stdin.write() calls forever. DEVNULL avoids that deadlock entirely.
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    frame_idx = 0
    ok = True
    success = True
    try:
        while ok:
            ok, frame = cap.read()
            if not ok:
                break
            t = frame_idx / fps
            face_x_source = _offset_at(path, t)
            face_x_scaled = face_x_source * (height / src_h)

            resized = cv2.resize(frame, (scaled_w, height))
            crop_x = int(round(face_x_scaled - width / 2))
            crop_x = max(0, min(crop_x, scaled_w - width))
            cropped = resized[:, crop_x:crop_x + width]
            proc.stdin.write(cropped.tobytes())
            frame_idx += 1
    except (OSError, BrokenPipeError):
        success = False
    finally:
        cap.release()
        if proc.stdin:
            proc.stdin.close()
        proc.wait()

    return success and proc.returncode == 0 and out_path.exists()
