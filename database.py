import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("lifeline.db")


SEED_CAMERAS = [
    ("CAM-01", "CAM-01", "cat road", 28.6139, 77.2090, "active", "cam1.mp4", "low"),
    ("CAM-02", "CAM-02", "rajwada", 28.6200, 77.2150, "active", "cam2.mp4", "medium"),
    ("CAM-03", "CAM-03", "rangwasa", 28.6050, 77.1980, "active", "cam3.mp4", "high"),
    ("CAM-04", "CAM-04", "NH 47 ab road", 28.6300, 77.2250, "idle", "cam4.mp4", "low"),
    ("CAM-05", "CAM-05", "WEBCAM", 28.6139, 77.2090, "webcam", "webcam", "medium"),
]

SEED_HOSPITALS = [
    ("Varun's hospital", 28.6200, 77.2100, 12, "+91-11-2345-6789", "Sector 1"),
    ("appolo hospital", 28.6150, 77.2300, 5, "+91-11-2345-6790", "Sector 2"),
    ("Myh hospital", 28.6050, 77.2050, 20, "+91-11-2345-6791", "Sector 3"),
    ("emegengy gov hospital", 28.5672, 77.2100, 8, "+91-11-2345-6792", "Sector 4"),
    ("apple hospital", 28.6400, 77.2200, 3, "+91-11-2345-6793", "Sector 5"),
]

SEED_POLICE = [
    ("rajendra nagar police station", 28.6310, 77.2260, "+91-1234567890", "HQ 1"),
    ("NH-47 Highway Patrol", 28.6100, 77.2000, "+91-1234567890", "HQ 2"),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                status TEXT NOT NULL,
                video_file TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'low'
            );
            CREATE TABLE IF NOT EXISTS hospitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                empty_beds INTEGER NOT NULL,
                contact TEXT NOT NULL,
                address TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS police_stations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                contact TEXT NOT NULL,
                address TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE NOT NULL,
                camera_id TEXT NOT NULL,
                camera_location TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                time_of_incident TEXT NOT NULL,
                time_of_review TEXT,
                response_time_seconds INTEGER,
                decision TEXT NOT NULL DEFAULT 'Pending',
                reviewed INTEGER NOT NULL DEFAULT 0,
                thumbnail_path TEXT,
                hospital_dispatched TEXT,
                clip_path TEXT
            );
            """
        )
        try:
            conn.execute("ALTER TABLE cameras ADD COLUMN severity TEXT NOT NULL DEFAULT 'low'")
        except sqlite3.OperationalError:
            pass  # column already exists
        if conn.execute("SELECT COUNT(*) c FROM cameras").fetchone()["c"] == 0:
            conn.executemany("INSERT INTO cameras VALUES (?, ?, ?, ?, ?, ?, ?, ?)", SEED_CAMERAS)
        if conn.execute("SELECT COUNT(*) c FROM hospitals").fetchone()["c"] == 0:
            conn.executemany(
                "INSERT INTO hospitals(name,lat,lng,empty_beds,contact,address) VALUES (?,?,?,?,?,?)",
                SEED_HOSPITALS,
            )
        if conn.execute("SELECT COUNT(*) c FROM police_stations").fetchone()["c"] == 0:
            conn.executemany(
                "INSERT INTO police_stations(name,lat,lng,contact,address) VALUES (?,?,?,?,?)",
                SEED_POLICE,
            )


def _rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def list_cameras() -> list[dict[str, Any]]:
    return _rows("SELECT * FROM cameras ORDER BY id")


def get_camera(camera_id: str) -> dict[str, Any] | None:
    rows = _rows("SELECT * FROM cameras WHERE id = ?", (camera_id,))
    return rows[0] if rows else None


def list_hospitals() -> list[dict[str, Any]]:
    return _rows("SELECT * FROM hospitals ORDER BY id")


def list_police() -> list[dict[str, Any]]:
    return _rows("SELECT * FROM police_stations ORDER BY id")


def list_incidents() -> list[dict[str, Any]]:
    return _rows("SELECT * FROM incidents ORDER BY id DESC")


def get_incident(incident_id: str) -> dict[str, Any] | None:
    rows = _rows("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
    return rows[0] if rows else None


def next_incident_id() -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT MAX(id) m FROM incidents").fetchone()
    n = (row["m"] or 0) + 1
    return f"INC-{n:04d}"


def create_incident(
    camera_id: str,
    camera_location: str,
    incident_type: str,
    confidence: float,
    thumbnail_path: str | None,
    clip_path: str | None,
) -> dict[str, Any]:
    incident_id = next_incident_id()
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO incidents(
                incident_id,camera_id,camera_location,incident_type,confidence,time_of_incident,thumbnail_path,clip_path
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (incident_id, camera_id, camera_location, incident_type, confidence, now, thumbnail_path, clip_path),
        )
    return get_incident(incident_id)  # type: ignore[return-value]


def mark_reviewed(incident_id: str) -> dict[str, Any] | None:
    reviewed_at = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            "UPDATE incidents SET reviewed = 1, time_of_review = COALESCE(time_of_review, ?) WHERE incident_id = ?",
            (reviewed_at, incident_id),
        )
    return get_incident(incident_id)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def nearest_hospital_for_camera(camera_id: str) -> dict[str, Any] | None:
    camera = get_camera(camera_id)
    if not camera:
        return None
    best = None
    for h in list_hospitals():
        d = _haversine_km(camera["lat"], camera["lng"], h["lat"], h["lng"])
        if best is None or d < best["distance_km"]:
            best = {**h, "distance_km": round(d, 2)}
    return best


def apply_decision(incident_id: str, decision: str) -> dict[str, Any] | None:
    existing = get_incident(incident_id)
    if not existing:
        return None
    now = datetime.now()
    t0 = datetime.fromisoformat(existing["time_of_incident"])
    response = int((now - t0).total_seconds())
    hospital_name = None
    if decision == "accept":
        nearest = nearest_hospital_for_camera(existing["camera_id"])
        hospital_name = nearest["name"] if nearest else None
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE incidents
            SET decision = ?, response_time_seconds = ?, reviewed = 1,
                time_of_review = COALESCE(time_of_review, ?),
                hospital_dispatched = COALESCE(?, hospital_dispatched)
            WHERE incident_id = ?
            """,
            (decision, response, now.isoformat(timespec="seconds"), hospital_name, incident_id),
        )
    return get_incident(incident_id)


def clear_clip_path(incident_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE incidents SET clip_path = NULL WHERE incident_id = ?", (incident_id,))


def stats() -> dict[str, Any]:
    incidents = list_incidents()
    total = len(incidents)
    accepted = len([i for i in incidents if i["decision"] == "accept"])
    ignored = len([i for i in incidents if i["decision"] == "ignore"])
    pending = len([i for i in incidents if i["decision"] == "Pending"])
    response_values = [i["response_time_seconds"] for i in incidents if i["response_time_seconds"] is not None]
    avg_response_time = int(sum(response_values) / len(response_values)) if response_values else 0
    return {
        "total": total,
        "accepted": accepted,
        "ignored": ignored,
        "pending": pending,
        "avg_response_time": avg_response_time,
    }


def reset_incidents() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM incidents")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'incidents'")
