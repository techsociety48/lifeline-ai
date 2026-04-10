from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for
from flask_socketio import SocketIO, emit

import database
from buffer import ClipBufferManager
from detection import DetectionEngine


Path("static/thumbnails").mkdir(parents=True, exist_ok=True)
Path("static/clips").mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "lifeline-dev"
# Use threading mode for Windows stability under heavy MJPEG streams.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

database.init_db()
# Demo-clean start to avoid huge alert history and keep exactly fresh run behavior.
database.reset_incidents()
for folder in [Path("static/clips"), Path("static/thumbnails")]:
    for file in folder.glob("*"):
        if file.is_file():
            try:
                file.unlink()
            except OSError:
                pass
clip_buffer = ClipBufferManager()
engine = DetectionEngine(socketio=socketio, clip_buffer=clip_buffer)
for cam in database.list_cameras():
    if cam["status"] in {"active", "idle", "webcam"}:
        engine.start(cam["id"])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/camera")
def camera():
    camera_id = request.args.get("id", "CAM-01")
    camera_row = database.get_camera(camera_id)
    return render_template("camera.html", camera_id=camera_id, camera=camera_row)


@app.route("/alerts")
def alerts():
    return render_template("alerts.html")


@app.route("/dispatch")
def dispatch():
    incident_id = request.args.get("id", "INC-0001")
    return render_template("dispatch.html", incident_id=incident_id)


@app.route("/index.html")
def index_html():
    return redirect(url_for("index"))


@app.route("/camera.html")
def camera_html():
    return redirect(url_for("camera", id=request.args.get("id", "CAM-01")))


@app.route("/alerts.html")
def alerts_html():
    return redirect(url_for("alerts"))


@app.route("/dispatch.html")
def dispatch_html():
    return redirect(url_for("dispatch", id=request.args.get("id", "INC-0001")))


@app.route("/video_feed/<camera_id>")
def video_feed(camera_id: str):
    return Response(engine.stream_bytes(camera_id, annotated=False), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed_detection/<camera_id>")
def video_feed_detection(camera_id: str):
    return Response(engine.stream_bytes(camera_id, annotated=True), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.post("/api/start_feed")
def start_feed():
    payload = request.get_json(force=True, silent=True) or {}
    camera_id = payload.get("camera_id")
    if not camera_id:
        return jsonify({"error": "camera_id required"}), 400
    engine.start(camera_id, source=payload.get("source", "video"), file_path=payload.get("file_path"))
    return jsonify({"ok": True, "camera_id": camera_id})


@app.post("/api/stop_feed")
def stop_feed():
    payload = request.get_json(force=True, silent=True) or {}
    camera_id = payload.get("camera_id")
    if not camera_id:
        return jsonify({"error": "camera_id required"}), 400
    engine.stop(camera_id)
    return jsonify({"ok": True, "camera_id": camera_id})


@app.get("/api/incidents")
def incidents_api():
    return jsonify(database.list_incidents())


@app.get("/api/incident/<incident_id>")
def incident_api(incident_id: str):
    incident = database.get_incident(incident_id)
    if not incident:
        return jsonify({"error": "not found"}), 404
    return jsonify(incident)


@app.get("/api/stats")
def stats_api():
    return jsonify(database.stats())


@app.get("/api/hospitals")
def hospitals_api():
    return jsonify(database.list_hospitals())


@app.get("/api/police")
def police_api():
    return jsonify(database.list_police())


@app.get("/api/cameras")
def cameras_api():
    return jsonify(database.list_cameras())


@app.post("/api/review/<incident_id>")
def review_api(incident_id: str):
    incident = database.mark_reviewed(incident_id)
    if not incident:
        return jsonify({"error": "not found"}), 404
    return jsonify(incident)


@app.post("/api/decision/<incident_id>")
def decision_api(incident_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    decision = payload.get("decision")
    if decision not in {"accept", "ignore"}:
        return jsonify({"error": "decision must be accept|ignore"}), 400
    incident = database.apply_decision(incident_id, decision)
    if not incident:
        return jsonify({"error": "not found"}), 404
    clip_buffer.delete_clip(incident_id)
    updated = database.get_incident(incident_id)
    return jsonify(updated)


@app.post("/api/manual_flag/<camera_id>")
def manual_flag(camera_id: str):
    camera = database.get_camera(camera_id)
    if not camera:
        return jsonify({"error": "camera not found"}), 404
    incident = database.create_incident(
        camera_id=camera_id,
        camera_location=camera["location"],
        incident_type="Manual Flag",
        confidence=100,
        thumbnail_path=None,
        clip_path=None,
    )
    clip_path = clip_buffer.save_clip(incident["incident_id"], camera_id)
    if clip_path:
        with database.get_conn() as conn:
            conn.execute("UPDATE incidents SET clip_path = ? WHERE incident_id = ?", (clip_path, incident["incident_id"]))
        incident = database.get_incident(incident["incident_id"])
    socketio.emit(
        "new_alert",
        {
            "incident_id": incident["incident_id"],
            "type": incident["incident_type"],
            "camera_id": incident["camera_id"],
            "location": incident["camera_location"],
            "confidence": incident["confidence"],
            "time": incident["time_of_incident"],
            "thumbnail_path": incident["thumbnail_path"],
        },
    )
    return jsonify(incident), 201


@socketio.on("connect")
def on_connect():
    emit("stats", database.stats())


@socketio.on("request_stats")
def on_request_stats():
    emit("stats", database.stats())


if __name__ == "__main__":
    # Disable reloader to prevent duplicate server instances/port conflicts.
    socketio.run(app, debug=False, use_reloader=False, host="127.0.0.1", port=5000)
