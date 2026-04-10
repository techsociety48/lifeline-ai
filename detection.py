import math
import shutil
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import database
from buffer import ClipBufferManager

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

try:
    import mediapipe as mp
except Exception:
    mp = None

# ─────────────────────────────────────────────
#  VEHICLE class colors (BGR)
# ─────────────────────────────────────────────
_CLASS_COLORS_BGR = {
    0: (255, 212, 0),   # person  – base color (overridden per-identity below)
    1: (0, 184, 255),   # bicycle – amber
    2: (110, 255, 57),  # car     – green
    3: (0, 184, 255),   # motorcycle – amber
    7: (0, 140, 255),   # truck   – orange
}

_CLASS_NAMES = {0: "PERSON", 1: "BIKE", 2: "CAR", 3: "MOTO", 7: "TRUCK"}

_RED_BGR   = (90, 60, 255)
_WHITE_BGR = (255, 255, 255)
_BLACK_BGR = (10, 10, 10)

# ─────────────────────────────────────────────
#  Resolution config
#  DISPLAY_SIZE  → what the browser sees (both streams)
#  DETECT_SIZE   → what YOLO actually processes (smaller = faster)
#  Boxes are drawn on DISPLAY_SIZE frame after scaling coords back up.
# ─────────────────────────────────────────────
_DISPLAY_W, _DISPLAY_H = 640, 360   # shown to browser
_DETECT_W,  _DETECT_H  = 320, 180   # YOLO inference resolution
_SCALE_X = _DISPLAY_W / _DETECT_W   # = 2.0  (used to scale bbox coords back up)
_SCALE_Y = _DISPLAY_H / _DETECT_H   # = 2.0

# ─────────────────────────────────────────────
#  Per-person identity palette  (20 vivid BGR)
# ─────────────────────────────────────────────
_PERSON_PALETTE_BGR: list[tuple[int, int, int]] = []


def _build_person_palette(n: int = 20) -> None:
    if cv2 is None or np is None:
        _PERSON_PALETTE_BGR.extend([
            (255, 212, 0), (0, 200, 255), (0, 255, 128), (255, 0, 200),
            (0, 128, 255), (255, 64, 0),  (200, 0, 255), (0, 255, 200),
            (255, 200, 0), (128, 255, 0), (0, 64, 255),  (255, 0, 64),
            (0, 255, 64),  (64, 0, 255),  (255, 128, 0), (0, 200, 128),
            (200, 255, 0), (64, 255, 255),(255, 0, 128), (128, 0, 255),
        ])
        return
    for i in range(n):
        hue = int(i * 180 / n)
        hsv = np.uint8([[[hue, 230, 255]]])
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0][0]
        _PERSON_PALETTE_BGR.append((int(bgr[0]), int(bgr[1]), int(bgr[2])))


_build_person_palette(20)


def _person_color(display_id: str) -> tuple[int, int, int]:
    try:
        idx = int(display_id.lstrip("X")) - 1
    except (ValueError, AttributeError):
        idx = hash(display_id)
    return _PERSON_PALETTE_BGR[idx % len(_PERSON_PALETTE_BGR)]


# ─────────────────────────────────────────────
#  Tuning knobs
# ─────────────────────────────────────────────
_YOLO_WEIGHTS   = ("yolov10n.pt", "yolov8n.pt")
_YOLO_CONF      = 0.45
_YOLO_IOU       = 0.5
# NOTE: imgsz fed to YOLO matches our small detect frame, not display frame
_YOLO_IMGSZ     = 320

_STREAM_LOOP_SLEEP   = 0.001   # tighter loop for better FPS
_MJPEG_YIELD_SLEEP   = 0.005
_JPEG_ENCODE_PARAMS  = [int(cv2.IMWRITE_JPEG_QUALITY), 70] if cv2 is not None else []
_POSE_EVERY_N        = 3        # run pose estimation every 3rd frame for performance

_ESP_CORNER_FRAC      = 0.22
_ESP_CORNER_THICKNESS = 2
_ESP_BOX_THICKNESS    = 1
_ESP_LABEL_FONT       = cv2.FONT_HERSHEY_DUPLEX if cv2 else None
_ESP_LABEL_SCALE      = 0.42
_ESP_LABEL_THICK      = 1
_ESP_COORD_FONT       = cv2.FONT_HERSHEY_PLAIN if cv2 else None
_ESP_COORD_SCALE      = 0.65


@dataclass
class TrackObject:
    kind:         str
    display_id:   str
    bbox:         tuple[int, int, int, int]   # coords in DISPLAY resolution
    confidence:   float
    yolo_cls:     int
    raw_track_id: int
    is_fallen:    bool = False
    color:        tuple[int, int, int] = field(default_factory=lambda: (255, 212, 0))


# ══════════════════════════════════════════════════════════════════════════════
class DetectionEngine:
# ══════════════════════════════════════════════════════════════════════════════

    def __init__(self, socketio: Any, clip_buffer: ClipBufferManager) -> None:
        self.socketio    = socketio
        self.clip_buffer = clip_buffer
        self.stop_event  = threading.Event()

        self.feed_threads:   dict[str, threading.Thread] = {}
        self.feed_state:     dict[str, dict[str, Any]]  = {}
        self.clean_jpeg:     dict[str, bytes]            = {}
        self.annotated_jpeg: dict[str, bytes]            = {}
        self.cooldown_until: dict[str, float]            = {}
        self.runtime:        dict[str, dict[str, Any]]  = {}

        self.person_counter:        dict[str, dict[int, str]]                   = defaultdict(dict)
        self.vehicle_counter:       dict[str, dict[int, str]]                   = defaultdict(dict)
        self.fall_frame_counter:    dict[str, dict[str, int]]                   = defaultdict(lambda: defaultdict(int))
        self.fallen_persons:        dict[str, set[str]]                         = defaultdict(set)
        self.prev_center:           dict[str, dict[str, tuple[float, float]]]   = defaultdict(dict)
        self.speed_history:         dict[str, dict[str, deque]]                 = defaultdict(lambda: defaultdict(lambda: deque(maxlen=5)))
        self.vehicle_speeds:        dict[str, dict[str, float]]                 = defaultdict(dict)
        self.pose_landmarks:        dict[str, dict[str, list]]                  = defaultdict(dict)
        self.bbox_fallback_counter: dict[str, dict[str, int]]                   = defaultdict(lambda: defaultdict(int))

        self.fps_history:     dict[str, deque] = defaultdict(lambda: deque(maxlen=30))
        self.last_frame_time: dict[str, float] = {}

        self.prev_iou_dict:  dict[str, dict[tuple[str, str], float]]              = defaultdict(dict)
        self.vehicle_bboxes: dict[str, dict[str, tuple[int, int, int, int]]]      = defaultdict(dict)

        self.demo_alert_cameras  = {"CAM-01", "CAM-04"}
        self.demo_alerts_created = 0

        self.yolo_model        = self._load_yolo()
        self.yolo_weights_name = "none"
        self.pose_model        = None
        self.pose_lock         = threading.Lock()

        if mp is not None:
            try:
                self.pose_model = mp.solutions.pose.Pose(
                    static_image_mode=False,
                    model_complexity=0,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            except Exception:
                self.pose_model = None

        Path("static/thumbnails").mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────
    #  Model loading
    # ──────────────────────────────────────────
    def _load_yolo(self) -> Any:
        if YOLO is None:
            return None
        for weights in _YOLO_WEIGHTS:
            try:
                model = YOLO(weights)
                self.yolo_weights_name = weights
                return model
            except Exception:
                continue
        return None

    def _clamp_xyxy(
        self,
        box: tuple[int, int, int, int],
        w: int,
        h: int,
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        x1 = max(0, min(w - 1, x1))
        x2 = max(0, min(w - 1, x2))
        y1 = max(0, min(h - 1, y1))
        y2 = max(0, min(h - 1, y2))
        if x2 < x1: x1, x2 = x2, x1
        if y2 < y1: y1, y2 = y2, y1
        return x1, y1, x2, y2

    # ──────────────────────────────────────────
    #  Feed lifecycle
    # ──────────────────────────────────────────
    def start(self, camera_id: str, source: str = "video", file_path: str | None = None) -> None:
        if camera_id in self.feed_threads and self.feed_threads[camera_id].is_alive():
            return
        self.feed_state[camera_id] = {"source": source, "file_path": file_path}
        self.runtime[camera_id] = {
            "frame_number": 0,
            "last_results": None,
            "alert_sent":   False,
            "last_emit_at": 0.0,
        }
        thread = threading.Thread(target=self._run_feed, args=(camera_id,), daemon=True)
        self.feed_threads[camera_id] = thread
        thread.start()

    def stop(self, camera_id: str) -> None:
        self.feed_state[camera_id] = {"stopped": True}

    def stop_all(self) -> None:
        self.stop_event.set()

    def _open_capture(self, camera_id: str) -> Any:
        camera = database.get_camera(camera_id)
        if cv2 is None or not camera:
            return None
        if camera["video_file"] == "webcam":
            return cv2.VideoCapture(0)
        video_path = Path("videos") / camera["video_file"]
        if video_path.exists():
            cap = cv2.VideoCapture(str(video_path))
            # Hint: set buffer size small to keep frames fresh
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            return cap
        return None

    def _fake_frame(self, camera_id: str) -> Any:
        if np is None or cv2 is None:
            return None
        img = np.zeros((_DISPLAY_H, _DISPLAY_W, 3), dtype=np.uint8)
        img[:, :] = (15, 8, 4)
        txt = f"{camera_id} | SIMULATED FEED | {datetime.now().strftime('%H:%M:%S')}"
        cv2.putText(img, txt, (22, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 212, 0), 2)
        return img

    # ══════════════════════════════════════════
    #  PART 1 — ESP Bounding Box Drawing
    # ══════════════════════════════════════════
    def _draw_esp_corners(
        self,
        img:   Any,
        x1:    int,
        y1:    int,
        x2:    int,
        y2:    int,
        color: tuple[int, int, int],
        thickness: int = _ESP_CORNER_THICKNESS,
    ) -> None:
        bw = x2 - x1
        bh = y2 - y1
        cx = max(8, int(bw * _ESP_CORNER_FRAC))
        cy = max(8, int(bh * _ESP_CORNER_FRAC))

        cv2.line(img, (x1, y1),      (x1 + cx, y1),      color, thickness)
        cv2.line(img, (x1, y1),      (x1, y1 + cy),      color, thickness)
        cv2.line(img, (x2, y1),      (x2 - cx, y1),      color, thickness)
        cv2.line(img, (x2, y1),      (x2, y1 + cy),      color, thickness)
        cv2.line(img, (x1, y2),      (x1 + cx, y2),      color, thickness)
        cv2.line(img, (x1, y2),      (x1, y2 - cy),      color, thickness)
        cv2.line(img, (x2, y2),      (x2 - cx, y2),      color, thickness)
        cv2.line(img, (x2, y2),      (x2, y2 - cy),      color, thickness)

    def _draw_bounding_box(
        self,
        out:   Any,
        track: TrackObject,
        w:     int,
        h:     int,
        camera_id: str,
    ) -> None:
        if cv2 is None:
            return
        try:
            x1, y1, x2, y2 = self._clamp_xyxy(track.bbox, w, h)
            color = track.color

            if track.is_fallen:
                color = _RED_BGR

            # 1. Simple rectangle (no addWeighted for performance)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, _ESP_BOX_THICKNESS)

            # 2. Bright ESP corner brackets
            self._draw_esp_corners(out, x1, y1, x2, y2, color, _ESP_CORNER_THICKNESS)

            # 3. Label bar above box (simple fill instead of addWeighted)
            label = self._get_label_text(track, camera_id)
            (tw, th), baseline = cv2.getTextSize(
                label, _ESP_LABEL_FONT, _ESP_LABEL_SCALE, _ESP_LABEL_THICK
            )
            bar_h   = th + baseline + 8
            bar_top = max(0, y1 - bar_h)
            bar_bot = y1

            cv2.rectangle(out, (x1, bar_top), (x1 + tw + 8, bar_bot), color, -1)

            cv2.putText(
                out, label,
                (x1 + 4, bar_bot - baseline - 2),
                _ESP_LABEL_FONT, _ESP_LABEL_SCALE,
                _BLACK_BGR, _ESP_LABEL_THICK, cv2.LINE_AA,
            )

            # 4. Coordinate tags
            coord_tl = f"({x1},{y1})"
            coord_br = f"({x2},{y2})"

            cv2.putText(
                out, coord_tl,
                (x1 + 3, min(h - 4, y1 + int(14 * _ESP_COORD_SCALE) + 6)),
                _ESP_COORD_FONT, _ESP_COORD_SCALE, color, 1, cv2.LINE_AA,
            )
            (cw, ch), _ = cv2.getTextSize(coord_br, _ESP_COORD_FONT, _ESP_COORD_SCALE, 1)
            cv2.putText(
                out, coord_br,
                (max(0, x2 - cw - 3), max(y2 - 4, y1 + ch + 4)),
                _ESP_COORD_FONT, _ESP_COORD_SCALE, color, 1, cv2.LINE_AA,
            )

            # 5. Fall glow + text (simplified to single addWeighted for performance)
            if track.is_fallen:
                glow = out.copy()
                cv2.rectangle(glow, (x1, y1), (x2, y2), _RED_BGR, 4)
                cv2.addWeighted(glow, 0.3, out, 0.7, 0, out)

                self._draw_esp_corners(out, x1, y1, x2, y2, _RED_BGR, 3)

                fall_label = "FALL DETECTED"
                (fw, fh), _ = cv2.getTextSize(
                    fall_label, cv2.FONT_HERSHEY_DUPLEX, 0.65, 2
                )
                cx_text = (x1 + x2) // 2 - fw // 2
                cy_text = (y1 + y2) // 2 + fh // 2
                cv2.putText(
                    out, fall_label, (cx_text, cy_text),
                    cv2.FONT_HERSHEY_DUPLEX, 0.65, _RED_BGR, 2, cv2.LINE_AA,
                )

        except Exception:
            pass

    def _get_label_text(self, track: TrackObject, camera_id: str) -> str:
        cls_name = _CLASS_NAMES.get(track.yolo_cls, "OBJ")
        conf_pct = int(track.confidence * 100)

        if track.is_fallen:
            return f"FALL #{track.display_id}  {conf_pct}%  ⚠ DOWN"

        if track.kind == "person":
            return f"PERSON #{track.display_id}  {conf_pct}%"

        speed = self.vehicle_speeds.get(camera_id, {}).get(track.display_id, 0.0)
        if cls_name in ("CAR", "MOTO", "TRUCK"):
            return f"{cls_name} #{track.display_id}  {conf_pct}%  {speed:.1f}km/h"
        return f"{cls_name} #{track.display_id}  {conf_pct}%"

    # ══════════════════════════════════════════
    #  PART 2 — MediaPipe Pose Skeleton
    # ══════════════════════════════════════════
    def _draw_pose_skeleton(
        self,
        out:       Any,
        frame:     Any,
        track:     TrackObject,
        camera_id: str,
    ) -> None:
        try:
            if self.pose_model is None or track.kind != "person":
                return

            x1, y1, x2, y2 = track.bbox
            h, w = frame.shape[:2]
            x1c, y1c = max(0, x1), max(0, y1)
            x2c, y2c = min(w - 1, x2), min(h - 1, y2)

            if x2c <= x1c or y2c <= y1c:
                return

            crop = frame[y1c:y2c, x1c:x2c]
            if crop.size == 0:
                return

            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            with self.pose_lock:
                result = self.pose_model.process(rgb)

            if not result.pose_landmarks:
                return

            lm  = result.pose_landmarks.landmark
            ids = mp.solutions.pose.PoseLandmark

            connections = [
                (ids.LEFT_SHOULDER,  ids.RIGHT_SHOULDER),
                (ids.LEFT_SHOULDER,  ids.LEFT_ELBOW),
                (ids.LEFT_ELBOW,     ids.LEFT_WRIST),
                (ids.RIGHT_SHOULDER, ids.RIGHT_ELBOW),
                (ids.RIGHT_ELBOW,    ids.RIGHT_WRIST),
                (ids.LEFT_SHOULDER,  ids.LEFT_HIP),
                (ids.RIGHT_SHOULDER, ids.RIGHT_HIP),
                (ids.LEFT_HIP,       ids.RIGHT_HIP),
                (ids.LEFT_HIP,       ids.LEFT_KNEE),
                (ids.LEFT_KNEE,      ids.LEFT_ANKLE),
                (ids.RIGHT_HIP,      ids.RIGHT_KNEE),
                (ids.RIGHT_KNEE,     ids.RIGHT_ANKLE),
            ]

            key_landmarks = [
                ids.LEFT_SHOULDER, ids.RIGHT_SHOULDER,
                ids.LEFT_ELBOW,    ids.RIGHT_ELBOW,
                ids.LEFT_WRIST,    ids.RIGHT_WRIST,
                ids.LEFT_HIP,      ids.RIGHT_HIP,
                ids.LEFT_KNEE,     ids.RIGHT_KNEE,
                ids.LEFT_ANKLE,    ids.RIGHT_ANKLE,
            ]

            landmark_coords: dict = {}
            for pid in key_landmarks:
                p  = lm[pid.value]
                px = int(x1c + p.x * (x2c - x1c))
                py = int(y1c + p.y * (y2c - y1c))
                landmark_coords[pid] = (px, py)

            self.pose_landmarks[camera_id][track.display_id] = [
                landmark_coords[ids.LEFT_SHOULDER],
                landmark_coords[ids.RIGHT_SHOULDER],
                landmark_coords[ids.LEFT_HIP],
                landmark_coords[ids.RIGHT_HIP],
                landmark_coords[ids.LEFT_ANKLE],
                landmark_coords[ids.RIGHT_ANKLE],
            ]

            skel_color = track.color

            # Direct line drawing instead of addWeighted for performance
            for ca, cb in connections:
                if ca in landmark_coords and cb in landmark_coords:
                    cv2.line(out, landmark_coords[ca], landmark_coords[cb], skel_color, 1)

            for coord in landmark_coords.values():
                cv2.circle(out, coord, 4, skel_color, 1, cv2.LINE_AA)
                cv2.circle(out, coord, 2, _WHITE_BGR,  -1, cv2.LINE_AA)

        except Exception:
            pass

    # ══════════════════════════════════════════
    #  PART 3 — Fall Detection
    # ══════════════════════════════════════════
    def _update_fall_detection(self, camera_id: str, track: TrackObject) -> bool:
        try:
            if track.kind != "person":
                return False

            if track.display_id in self.pose_landmarks[camera_id]:
                landmarks = self.pose_landmarks[camera_id][track.display_id]
                if len(landmarks) >= 6:
                    l_sh, r_sh, l_hip, r_hip, l_ank, r_ank = landmarks
                    shoulder_mid_y = (l_sh[1] + r_sh[1]) / 2.0
                    hip_mid_y      = (l_hip[1] + r_hip[1]) / 2.0

                    if shoulder_mid_y > hip_mid_y:
                        self.fall_frame_counter[camera_id][track.display_id] += 1
                        if self.fall_frame_counter[camera_id][track.display_id] >= 45:
                            self.fallen_persons[camera_id].add(track.display_id)
                            return True
                    else:
                        self.fall_frame_counter[camera_id][track.display_id] = 0
                        self.fallen_persons[camera_id].discard(track.display_id)
                return track.display_id in self.fallen_persons[camera_id]

            x1, y1, x2, y2 = track.bbox
            bw, bh = x2 - x1, y2 - y1
            if bw > bh * 1.3:
                self.bbox_fallback_counter[camera_id][track.display_id] += 1
                if self.bbox_fallback_counter[camera_id][track.display_id] >= 60:
                    return True
            else:
                self.bbox_fallback_counter[camera_id][track.display_id] = 0

            return False
        except Exception:
            return False

    # ══════════════════════════════════════════
    #  PART 4 — Speed Estimation
    # ══════════════════════════════════════════
    def _update_speed_estimation(self, camera_id: str, track: TrackObject) -> None:
        try:
            if track.kind != "vehicle":
                return
            x1, y1, x2, y2 = track.bbox
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

            if track.display_id in self.prev_center[camera_id]:
                pcx, pcy = self.prev_center[camera_id][track.display_id]
                dist      = math.hypot(cx - pcx, cy - pcy)
                speed_kmh = dist * 0.05 * 30
                self.speed_history[camera_id][track.display_id].append(speed_kmh)
                hist = self.speed_history[camera_id][track.display_id]
                self.vehicle_speeds[camera_id][track.display_id] = round(sum(hist) / len(hist), 1)
            else:
                self.vehicle_speeds[camera_id][track.display_id] = 0.0

            self.prev_center[camera_id][track.display_id] = (cx, cy)
        except Exception:
            pass

    # ══════════════════════════════════════════
    #  PART 5 — HUD Overlays
    # ══════════════════════════════════════════
    def _draw_hud_overlays(
        self,
        out:           Any,
        camera_id:     str,
        fps:           float,
        person_count:  int,
        vehicle_count: int,
    ) -> None:
        try:
            h, w   = out.shape[:2]
            camera = database.get_camera(camera_id)
            if not camera:
                return

            fallen_count = len(self.fallen_persons[camera_id])

            # Direct fill instead of addWeighted for performance
            cv2.rectangle(out, (0, 0), (w, 58), (0, 0, 0), -1)

            gold = (255, 212, 0)

            cv2.putText(out,
                f"MODEL: {self.yolo_weights_name} | TRACKER: ByteTrack",
                (10, 20), cv2.FONT_HERSHEY_PLAIN, 1.0, gold, 1, cv2.LINE_AA)
            cv2.putText(out,
                f"FPS: {fps:.1f} | IMGSZ: {_YOLO_IMGSZ} | CONF: {_YOLO_CONF}",
                (10, 44), cv2.FONT_HERSHEY_PLAIN, 1.0, gold, 1, cv2.LINE_AA)

            for i, (label, val) in enumerate([
                ("PERSONS",  person_count),
                ("VEHICLES", vehicle_count),
                ("FALLEN",   fallen_count),
            ]):
                txt = f"{label}: {val}"
                (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_PLAIN, 1.0, 1)
                y_pos      = 20 + i * 24
                color      = _RED_BGR if (label == "FALLEN" and fallen_count > 0) else gold
                cv2.putText(out, txt, (w - tw - 10, y_pos),
                            cv2.FONT_HERSHEY_PLAIN, 1.0, color, 1, cv2.LINE_AA)

            cv2.putText(out,
                f"GPS: {camera['lat']}, {camera['lng']}",
                (10, h - 40), cv2.FONT_HERSHEY_PLAIN, 0.9, (180, 180, 180), 1)
            cv2.putText(out,
                f"{camera_id} | {camera['location']}",
                (10, h - 22), cv2.FONT_HERSHEY_PLAIN, 0.9, (180, 180, 180), 1)

            center_text = f"{camera_id}  —  {camera['location']}"
            (tw, _), _ = cv2.getTextSize(center_text, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)
            cv2.putText(out, center_text,
                        ((w - tw) // 2, h - 10),
                        cv2.FONT_HERSHEY_DUPLEX, 0.5, gold, 1, cv2.LINE_AA)

            legend_x = w - 160
            legend_y = h - 20 - (min(6, person_count) * 18)
            visible_ids = sorted(self.person_counter.get(camera_id, {}).values())[:6]
            for k, pid in enumerate(visible_ids):
                pc = _person_color(pid)
                cv2.rectangle(out,
                              (legend_x, legend_y + k * 18),
                              (legend_x + 12, legend_y + k * 18 + 12),
                              pc, -1)
                cv2.putText(out, f" {pid}",
                            (legend_x + 14, legend_y + k * 18 + 11),
                            cv2.FONT_HERSHEY_PLAIN, 0.85, pc, 1, cv2.LINE_AA)

        except Exception:
            pass

    def _draw_scanline(self, out: Any, frame_number: int) -> None:
        try:
            h, w = out.shape[:2]
            sy   = (frame_number * 3) % h
            # Single line instead of double with addWeighted for performance
            cv2.line(out, (0, sy), (w, sy), (255, 212, 0), 1)
        except Exception:
            pass

    # ══════════════════════════════════════════
    #  PART 6 — Detection Processing
    #  KEY CHANGE: YOLO runs on detect_frame (320x180).
    #  Bbox coords are scaled back up by _SCALE_X/_SCALE_Y
    #  before drawing on the full display_frame (640x360).
    # ══════════════════════════════════════════
    def _process_detections(
        self,
        results:       Any,
        display_frame: Any,   # 640×360 — drawn on, shown to user
        annotated:     Any,   # 640×360 copy — we draw boxes here
        camera_id:     str,
        frame_number:  int,
        run_pose:      bool = True,
    ) -> tuple[list[TrackObject], int, int]:
        try:
            if cv2 is None or not results or results[0].boxes is None or len(results[0].boxes) == 0:
                return [], 0, 0

            boxes       = results[0].boxes
            xyxy        = boxes.xyxy.cpu().numpy()
            confs       = boxes.conf.cpu().numpy()
            classes_arr = boxes.cls.cpu().numpy().astype(int)
            n           = len(classes_arr)

            if boxes.id is not None:
                ids_raw = boxes.id.cpu().numpy()
                ids_arr = [int(x) for x in ids_raw.reshape(-1).tolist()]
            else:
                ids_arr = [-1] * n

            h, w         = annotated.shape[:2]   # display resolution (640×360)
            tracks       = []
            person_count = 0
            vehicle_count = 0

            for i in range(n):
                cls_id = int(classes_arr[i])
                if cls_id not in _CLASS_COLORS_BGR:
                    continue

                # ── Scale bbox from detect res → display res ──────────────
                # YOLO saw a 320×180 frame; multiply coords by 2 to get 640×360
                x1 = int(round(float(xyxy[i][0]) * _SCALE_X))
                y1 = int(round(float(xyxy[i][1]) * _SCALE_Y))
                x2 = int(round(float(xyxy[i][2]) * _SCALE_X))
                y2 = int(round(float(xyxy[i][3]) * _SCALE_Y))
                x1, y1, x2, y2 = self._clamp_xyxy((x1, y1, x2, y2), w, h)

                if x2 - x1 < 6 or y2 - y1 < 6:
                    continue

                conf      = float(confs[i])
                is_person = (cls_id == 0)
                kind      = "person" if is_person else "vehicle"
                raw_tid   = ids_arr[i] if i < len(ids_arr) else -1

                # Assign stable display ID
                if raw_tid >= 0:
                    if is_person:
                        if raw_tid not in self.person_counter[camera_id]:
                            next_num = len(self.person_counter[camera_id]) + 1
                            self.person_counter[camera_id][raw_tid] = f"X{next_num}"
                        display_id = self.person_counter[camera_id][raw_tid]
                    else:
                        if raw_tid not in self.vehicle_counter[camera_id]:
                            next_num = len(self.vehicle_counter[camera_id]) + 1
                            self.vehicle_counter[camera_id][raw_tid] = f"V{next_num}"
                        display_id = self.vehicle_counter[camera_id][raw_tid]
                else:
                    display_id = (
                        f"X{len(self.person_counter[camera_id]) + 1}"
                        if is_person
                        else f"V{len(self.vehicle_counter[camera_id]) + 1}"
                    )

                esp_color = _person_color(display_id) if is_person else _CLASS_COLORS_BGR[cls_id]

                track = TrackObject(
                    kind=kind,
                    display_id=display_id,
                    bbox=(x1, y1, x2, y2),
                    confidence=conf,
                    yolo_cls=cls_id,
                    raw_track_id=raw_tid,
                    is_fallen=False,
                    color=esp_color,
                )

                track.is_fallen = self._update_fall_detection(camera_id, track)
                if track.is_fallen:
                    track.color = _RED_BGR

                self._update_speed_estimation(camera_id, track)

                if kind == "vehicle":
                    self.vehicle_bboxes[camera_id][display_id] = (x1, y1, x2, y2)

                # Draw on annotated (display resolution frame)
                self._draw_bounding_box(annotated, track, w, h, camera_id)

                if kind == "person" and run_pose:
                    # Skeleton uses display_frame (the full res source) for crop quality
                    self._draw_pose_skeleton(annotated, display_frame, track, camera_id)

                tracks.append(track)
                if kind == "person":
                    person_count += 1
                else:
                    vehicle_count += 1

            return tracks, person_count, vehicle_count
        except Exception:
            return [], 0, 0

    # ══════════════════════════════════════════
    #  PART 7 — Collision Detection
    # ══════════════════════════════════════════
    def _compute_iou(self, b1, b2) -> float:
        try:
            ix1 = max(b1[0], b2[0]); iy1 = max(b1[1], b2[1])
            ix2 = min(b1[2], b2[2]); iy2 = min(b1[3], b2[3])
            iw  = max(0, ix2 - ix1); ih = max(0, iy2 - iy1)
            inter  = iw * ih
            area1  = (b1[2] - b1[0]) * (b1[3] - b1[1])
            area2  = (b2[2] - b2[0]) * (b2[3] - b2[1])
            union  = area1 + area2 - inter
            return inter / union if union > 0 else 0.0
        except Exception:
            return 0.0

    def _check_collision_detection(self, camera_id: str):
        try:
            if time.time() < self.cooldown_until.get(camera_id, 0):
                return None
            vehicle_boxes = self.vehicle_bboxes[camera_id]
            vids = list(vehicle_boxes.keys())
            if len(vids) < 2:
                return None
            for i in range(len(vids)):
                for j in range(i + 1, len(vids)):
                    id_i, id_j = vids[i], vids[j]
                    iou = self._compute_iou(vehicle_boxes[id_i], vehicle_boxes[id_j])
                    if iou > 0.12:
                        prev_iou = self.prev_iou_dict[camera_id].get((id_i, id_j), 0.0)
                        if prev_iou < 0.05:
                            sp_i = self.vehicle_speeds[camera_id].get(id_i, 0.0)
                            sp_j = self.vehicle_speeds[camera_id].get(id_j, 0.0)
                            if sp_i > 8 or sp_j > 8:
                                self.prev_iou_dict[camera_id][(id_i, id_j)] = iou
                                return {"incident_type": "Collision", "confidence": 0.82,
                                        "reason": f"Vehicle collision {id_i} & {id_j}"}
                    self.prev_iou_dict[camera_id][(id_i, id_j)] = iou
            return None
        except Exception:
            return None

    def _check_fall_alert(self, camera_id: str):
        try:
            if time.time() < self.cooldown_until.get(camera_id, 0):
                return None
            if self.fallen_persons[camera_id]:
                fallen_id = next(iter(self.fallen_persons[camera_id]))
                return {"incident_type": "Fall", "confidence": 0.88,
                        "reason": f"Fall detected for person {fallen_id}"}
            return None
        except Exception:
            return None

    def _forced_demo_decision(self, camera_id: str, frame_number: int):
        try:
            if self.demo_alerts_created >= 2:
                return None
            if camera_id not in self.demo_alert_cameras:
                return None
            if self.runtime.get(camera_id, {}).get("alert_sent"):
                return None
            if frame_number < 20:
                return None
            if camera_id == "CAM-01":
                return {"incident_type": "Collision", "confidence": 0.82,
                        "reason": "forced demo alert cam1"}
            return {"incident_type": "Fall", "confidence": 0.88,
                    "reason": "forced demo alert cam4"}
        except Exception:
            return None

    def _trigger_alert(self, camera_id: str, incident: dict, annotated: Any) -> None:
        try:
            if self.demo_alerts_created >= 2:
                return
            camera = database.get_camera(camera_id)
            if not camera:
                return
            now         = time.time()
            incident_id = database.next_incident_id()

            thumb_path_db = None
            if cv2 is not None and annotated is not None:
                thumb_file = Path("static/thumbnails") / f"{incident_id}.jpg"
                cv2.imwrite(str(thumb_file), annotated)
                thumb_path_db = f"/static/thumbnails/{incident_id}.jpg"

            clip_path = None
            if camera["video_file"] != "webcam":
                src = Path("videos") / camera["video_file"]
                dst = Path("static/clips") / f"{incident_id}.mp4"
                if src.exists():
                    try:
                        shutil.copy2(src, dst)
                        clip_path = f"/static/clips/{incident_id}.mp4"
                    except Exception:
                        clip_path = None

            if clip_path is None:
                clip_path = self.clip_buffer.save_clip(incident_id, camera_id)

            db_incident = database.create_incident(
                camera_id=camera_id,
                camera_location=camera["location"],
                incident_type=incident["incident_type"],
                confidence=incident["confidence"],
                thumbnail_path=thumb_path_db,
                clip_path=clip_path,
            )

            self.socketio.emit("new_alert", {
                "incident_id":    db_incident["incident_id"],
                "type":           db_incident["incident_type"],
                "camera_id":      db_incident["camera_id"],
                "location":       db_incident["camera_location"],
                "confidence":     db_incident["confidence"],
                "time":           db_incident["time_of_incident"],
                "thumbnail_path": db_incident["thumbnail_path"],
            })

            self.demo_alerts_created       += 1
            self.cooldown_until[camera_id]  = now + 30
            self.runtime[camera_id]["alert_sent"] = True
        except Exception:
            pass

    # ══════════════════════════════════════════
    #  Main feed loop
    #  KEY CHANGES vs original:
    #  1. clean_jpeg stored IMMEDIATELY after frame read
    #     → dashboard never waits for YOLO
    #  2. YOLO runs on detect_frame (320×180 downscale)
    #     → inference is 4× faster than on display frame
    #  3. Loop sleep reduced to 0.005 s for tighter timing
    # ══════════════════════════════════════════
    def _run_feed(self, camera_id: str) -> None:
        cap             = self._open_capture(camera_id)
        last_frame_time = time.time()
        enc             = _JPEG_ENCODE_PARAMS or []

        while not self.stop_event.is_set():
            try:
                if self.feed_state.get(camera_id, {}).get("stopped"):
                    break

                camera    = database.get_camera(camera_id)
                is_webcam = bool(camera and camera.get("video_file") == "webcam")

                # ── 1. Read raw frame ─────────────────────────────────────
                frame = None
                if cap is not None and cv2 is not None:
                    ok, frame = cap.read()
                    if not ok:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, frame = cap.read()
                        if not ok:
                            frame = self._fake_frame(camera_id)
                    if ok and frame is not None:
                        # Display frame: 640×360
                        frame = cv2.resize(frame, (_DISPLAY_W, _DISPLAY_H))
                else:
                    frame = self._fake_frame(camera_id)

                if frame is None or cv2 is None:
                    time.sleep(_STREAM_LOOP_SLEEP)
                    continue

                # ── 2. STORE CLEAN JPEG IMMEDIATELY ──────────────────────
                #    Dashboard gets this right away — zero AI delay.
                _, clean_jpg = cv2.imencode(".jpg", frame, enc) if enc else cv2.imencode(".jpg", frame)
                self.clean_jpeg[camera_id] = clean_jpg.tobytes()

                # ── 3. Runtime state ─────────────────────────────────────
                if camera_id not in self.runtime:
                    self.runtime[camera_id] = {
                        "frame_number": 0,
                        "last_results": None,
                        "alert_sent":   False,
                        "last_emit_at": 0.0,
                    }

                state        = self.runtime[camera_id]
                state["frame_number"] += 1
                frame_number = state["frame_number"]
                annotated    = frame.copy()

                # ── 4. YOLO on downscaled detect frame ───────────────────
                #    Shrink to 320×180 → YOLO is 4× faster.
                #    Bbox coords scaled back up in _process_detections.
                person_count  = 0
                vehicle_count = 0

                if frame_number % 2 == 0:
                    try:
                        detect_frame = cv2.resize(frame, (_DETECT_W, _DETECT_H))
                        results = self.yolo_model.track(
                            detect_frame,
                            persist=True,
                            tracker="bytetrack.yaml",
                            classes=[0, 1, 2, 3, 7],
                            conf=_YOLO_CONF,
                            iou=_YOLO_IOU,
                            imgsz=_YOLO_IMGSZ,
                            verbose=False,
                        )
                        state["last_results"] = results
                    except Exception:
                        results = None
                        state["last_results"] = None
                else:
                    results = state["last_results"]

                # Only run pose estimation every Nth frame for performance
                run_pose = (frame_number % _POSE_EVERY_N == 0)
                
                if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                    _, person_count, vehicle_count = self._process_detections(
                        results, frame, annotated, camera_id, frame_number, run_pose
                    )

                # ── 5. Clip buffer (push display-res raw frame) ──────────
                self.clip_buffer.push_frame(camera_id, frame, fps=20)

                # ── 6. FPS ───────────────────────────────────────────────
                current_time = time.time()
                elapsed      = current_time - last_frame_time
                fps_inst     = 1.0 / elapsed if elapsed > 0 else 0.0
                self.fps_history[camera_id].append(fps_inst)
                hist = self.fps_history[camera_id]
                fps  = sum(hist) / len(hist) if hist else 0.0
                last_frame_time = current_time

                # ── 7. HUD + scanline on detection stream ─────────────────
                self._draw_hud_overlays(annotated, camera_id, fps, person_count, vehicle_count)
                self._draw_scanline(annotated, frame_number)

                # ── 8. Incident detection every 5 frames ─────────────────
                if frame_number % 5 == 0 and not is_webcam:
                    incident = (
                        self._check_collision_detection(camera_id)
                        or self._check_fall_alert(camera_id)
                        or self._forced_demo_decision(camera_id, frame_number)
                    )
                    if incident and not state["alert_sent"]:
                        self._trigger_alert(camera_id, incident, annotated)

                # ── 9. Store annotated JPEG ───────────────────────────────
                _, ann_jpg = cv2.imencode(".jpg", annotated, enc) if enc else cv2.imencode(".jpg", annotated)
                self.annotated_jpeg[camera_id] = ann_jpg.tobytes()

                # ── 10. Socket emit (max 1 Hz) ────────────────────────────
                if current_time - state.get("last_emit_at", 0.0) >= 1.0:
                    self.socketio.emit("detection_update", {
                        "camera_id":     camera_id,
                        "persons":       person_count,
                        "vehicles":      vehicle_count,
                        "fps":           fps,
                        "active_alerts": database.stats()["pending"],
                        "yolo_conf":     _YOLO_CONF,
                        "yolo_imgsz":    _YOLO_IMGSZ,
                    })
                    state["last_emit_at"] = current_time

                time.sleep(_STREAM_LOOP_SLEEP)

            except Exception:
                time.sleep(_STREAM_LOOP_SLEEP)
                continue

        if cap is not None and cv2 is not None:
            cap.release()

    # ──────────────────────────────────────────
    #  MJPEG stream generator
    # ──────────────────────────────────────────
    def stream_bytes(self, camera_id: str, annotated: bool = False):
        while True:
            frame = (
                self.annotated_jpeg.get(camera_id)
                if annotated
                else self.clean_jpeg.get(camera_id)
            )
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(_MJPEG_YIELD_SLEEP)