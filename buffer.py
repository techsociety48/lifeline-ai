from collections import deque
from pathlib import Path
from typing import Any

import database

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


class ClipBufferManager:
    def __init__(self, seconds: int = 30, default_fps: int = 20) -> None:
        self.seconds = seconds
        self.default_fps = default_fps
        self._buffers: dict[str, deque[Any]] = {}
        self._fps_map: dict[str, int] = {}
        Path("static/clips").mkdir(parents=True, exist_ok=True)

    def ensure_camera(self, camera_id: str, fps: int | None = None) -> None:
        fps_val = fps or self.default_fps
        if camera_id not in self._buffers:
            self._buffers[camera_id] = deque(maxlen=fps_val * self.seconds)
            self._fps_map[camera_id] = fps_val

    def push_frame(self, camera_id: str, frame: Any, fps: int | None = None) -> None:
        self.ensure_camera(camera_id, fps)
        self._buffers[camera_id].append(frame)

    def save_clip(self, incident_id: str, camera_id: str) -> str | None:
        frames = list(self._buffers.get(camera_id, []))
        if not frames:
            return None
        clip_path = Path("static/clips") / f"{incident_id}.mp4"
        if cv2 is None:
            return None
        h, w = frames[0].shape[:2]
        fps = self._fps_map.get(camera_id, self.default_fps)
        writer = cv2.VideoWriter(str(clip_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        for frame in frames:
            writer.write(frame)
        writer.release()
        return f"/static/clips/{incident_id}.mp4"

    def delete_clip(self, incident_id: str) -> None:
        clip_file = Path("static/clips") / f"{incident_id}.mp4"
        if clip_file.exists():
            clip_file.unlink()
        database.clear_clip_path(incident_id)
