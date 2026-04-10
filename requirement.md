You are now fully briefed on my hackathon project called
"Lifeline AI – Smart Surveillance & Emergency Response System".
This is a 36-hour hackathon prototype. Read everything below
carefully before responding to anything.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — WHAT THIS PROJECT IS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lifeline AI is a local smart city surveillance system that:

Monitors multiple camera feeds simultaneously

Uses AI computer vision to detect accidents and emergencies

Automatically cuts a 30-second evidence clip when incident detected

Routes the clip to the correct responder (ambulance or police)

Responder reviews clip and accepts or ignores the alert

On accept: shows full emergency dispatch workflow

On ignore: logs as false alarm

Runs entirely on localhost, no real APIs needed

Built for judges to see a convincing smart city prototype


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — THE PITCH (memorize this)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"A smart city camera system where AI detects accidents
automatically, cuts a 30-second clip, and pushes it to an
ambulance operator — who reviews and dispatches without
anyone at the camera end doing anything. Full automation.
Zero human dependency on the surveillance side. The AI flags,
humans decide."

This is positioned as public safety infrastructure, not a
home security app. The accept/ignore decision happens on the
RESPONDER side, not the camera owner side.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3 — HARDWARE / ENVIRONMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Laptop: Acer with AMD Ryzen 7, 16GB RAM

No dedicated GPU — CPU only

Running on localhost

Python environment

No cloud deployment needed


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — TECH STACK (FINAL, DO NOT CHANGE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Backend:

Python 3.10+

Flask + Flask-SocketIO (with eventlet)

OpenCV (cv2) for video reading and frame processing

Ultralytics YOLOv8n — nano model for CPU speed

ByteTrack — built into Ultralytics, do NOT use DeepSORT

MediaPipe Pose — for human pose estimation and fall detection

SQLite3 — database, no ORM needed

collections.deque — circular frame buffer


Frontend:

Pure HTML5 + CSS3 + Vanilla JavaScript

Socket.IO client (CDN)

Google Fonts: Orbitron (headings/IDs) + Rajdhani (UI) +
Share Tech Mono (data/coordinates)

NO React, NO Node.js, NO Tailwind, NO Bootstrap

MJPEG streaming via Flask for live video with boxes


Why these choices:

YOLOv8n: fastest YOLO model, runs on CPU at 15-20 FPS

ByteTrack: built-in, no extra install, one line to enable

MediaPipe Pose: lightweight, CPU-friendly, gives 33 body
landmarks for accurate fall and pose detection

MJPEG: simplest way to stream processed video to browser

No React: reduces complexity, easier to debug in 36 hours


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5 — PROJECT FOLDER STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

lifeline-ai/
├── app.py                  # Flask app, routes, SocketIO events
├── detection.py            # YOLO + MediaPipe + ByteTrack pipeline
├── buffer.py               # Circular frame buffer, clip saving
├── database.py             # SQLite setup, queries, seed data
├── lifeline.db             # Auto-created on first run
├── requirements.txt
├── /static
│   ├── /css/style.css
│   ├── /js/main.js
│   ├── /sounds/alert.mp3
│   ├── /thumbnails/        # Auto-created, stores incident thumbnails
│   └── /clips/             # Auto-created, TEMPORARY clip storage
├── /templates
│   ├── index.html          # Page 1: Dashboard
│   ├── camera.html         # Page 2: Camera Detail overlay
│   ├── alerts.html         # Page 3: Review Alert
│   └── dispatch.html       # Page 4: Dispatch workflow
└── /videos
└── (user places 4 sample .mp4 CCTV/accident footage here)
cam1.mp4, cam2.mp4, cam3.mp4, cam4.mp4

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6 — DATABASE SCHEMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Table: cameras
id, name, location, lat, lng, status, video_file

Table: hospitals
id, name, lat, lng, empty_beds, contact, address

Table: police_stations
id, name, lat, lng, contact, address

Table: incidents
id, incident_id, camera_id, camera_location, incident_type,
confidence, time_of_incident, time_of_review,
response_time_seconds, decision, thumbnail_path,
hospital_dispatched, clip_path

SEED DATA:

Cameras:
CAM-01 | NH-48 Main Junction      | 28.6139 | 77.2090 | active | cam1.mp4
CAM-02 | Market Street Crossing   | 28.6200 | 77.2150 | active | cam2.mp4
CAM-03 | Highway Overpass KM-12   | 28.6050 | 77.1980 | active | cam3.mp4
CAM-04 | School Zone Sector-7     | 28.6300 | 77.2250 | idle   | cam4.mp4
CAM-05 | WEBCAM                   | 28.6139 | 77.2090 | webcam | webcam

Hospitals:
City General Hospital     | 28.6200 | 77.2100 | 12 beds | +91-11-2345-6789
St. Mary Medical Center   | 28.6150 | 77.2300 | 5 beds  | +91-11-2345-6790
Apollo Trauma Center      | 28.6050 | 77.2050 | 20 beds | +91-11-2345-6791
AIIMS Emergency Ward      | 28.5672 | 77.2100 | 8 beds  | +91-11-2345-6792
Fortis Critical Care      | 28.6400 | 77.2200 | 3 beds  | +91-11-2345-6793

Police Stations:
Sector-7 Police Station | 28.6310 | 77.2260 | +91-11-9876-5432
NH-48 Highway Patrol    | 28.6100 | 77.2000 | +91-11-9876-5433

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 7 — THE 4 PAGES (FRONTEND STRUCTURE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAGE 1 — DASHBOARD (index.html)

Top bar:

Left: LIFELINE AI logo (Orbitron, cyan) + pulsing green dot

Center: Live clock and date updating every second

Right: Notification bell with red badge count, clicking
goes to alerts.html


Stats row (4 cards):

Cameras Active, Incidents Today, Avg Response Time,
System Status


Camera grid (2x3 layout — 4 video feeds + 1 webcam +
1 manual flag button):

IMPORTANT: Dashboard camera panels show NORMAL VIDEO
FOOTAGE only. No bounding boxes here.

Each camera tile has:

Top bar: Camera ID, location, status dot (green/gray)

Main area: Normal MJPEG video stream (clean, no boxes)

Bottom bar: last detected event label

"CAMERA DETAIL" button on each tile

Clicking CAMERA DETAIL opens camera.html for that camera


CAM-05 tile has Start/Stop webcam button

6th tile is manual flag button (red dashed border)


Bottom section (two panels):

Left: NEARBY HOSPITALS table
Columns: Name | Distance | Empty Beds | GPS Coords | Status
Beds >5 = green, 1-5 = yellow, 0 = red FULL

Right: POLICE STATIONS table
Columns: Name | Distance | Contact | GPS | Status


Incident log strip at very bottom:

Last 5 incidents as horizontal scrolling cards

Each card: type, ID, time, status badge


PAGE 2 — CAMERA DETAIL (camera.html?id=CAM-01)

This page/overlay shows the full detection view for
one camera. Opens when user clicks CAMERA DETAIL button.

Layout:

Back button to return to dashboard

Large video feed area (takes up 70% of width)

This feed shows MJPEG stream WITH all bounding boxes drawn

Side panel (30% width) showing detection info


Video feed with ESP-style bounding boxes:

Full solid rectangle bounding box (NOT corner brackets)

Person boxes: cyan (#00D4FF)

Car boxes: green (#39FF6E)

Bike boxes: amber (#FFB800)

Truck boxes: orange (#FF8C00)

Each box has label bar at top: "PERSON #X1" or "CAR #V1"

Tracking ID format: X1, X2, X3 for persons (X = person)
V1, V2, V3 for vehicles (V = vehicle)

Coordinates shown at top-left and bottom-right corners
of each box (pixel coords)

Confidence % shown on label

Speed shown on vehicle boxes (km/h estimate)

When fall detected: box rotates ~80 degrees to show
person lying horizontal, box glows red, "FALL" text inside


MediaPipe Pose overlay on persons:

Skeleton drawn on each detected person

Key landmarks shown: shoulders, elbows, wrists, hips,
knees, ankles

Skeleton color: cyan with lower opacity than box

Used for fall detection accuracy


HUD overlays on video:

Top left: MODEL: YOLOv8n | TRACKER: ByteTrack | FPS: XX

Top right: PERSONS: X | VEHICLES: X | CONF: 0.45

Bottom left: GPS coordinates of this camera

Bottom center: Camera ID and location name

Scanline animation over the feed


Side panel shows:

Camera info (ID, location, GPS, status, resolution)

Active alert box (red, blinking) if incident detected

Live detection log (last 10 events with timestamp)

Tracked objects list with their IDs and types


PAGE 3 — REVIEW ALERT (alerts.html)

Top bar same as dashboard.
Back button to dashboard.
Title: INCIDENT REVIEW QUEUE

Pending incidents section:
Each pending incident shown as a card with:

Left: Thumbnail image (frame from when incident detected,
with bounding boxes frozen)

Middle: Incident ID, type badge (color by type),
camera location, GPS coords, time of incident,
confidence %, duration

Right: Three buttons in strict order:

1. REVIEW FOOTAGE (cyan) — always active


2. ACCEPT (green) — DISABLED until footage reviewed


3. IGNORE (red) — DISABLED until footage reviewed
Small text: "Review required before action"




Video review modal (opens on REVIEW FOOTAGE click):

Overlay with backdrop blur

HTML5 video player showing the 30-second clip

Incident details panel beside video

Progress bar below video

MARK AS REVIEWED button — closes modal AND enables
Accept/Ignore buttons

Cannot close modal without clicking MARK AS REVIEWED


On ACCEPT:

POST to /api/decision/<incident_id> with decision=accept

Redirect to dispatch.html?id=<incident_id>

Clip file deleted automatically after this call


On IGNORE:

Confirmation dialog: "Confirm: Mark as False Alarm?"

On confirm: POST to /api/decision/<incident_id>
with decision=ignore

Clip file deleted automatically

Card gets "FALSE ALARM" red stamp overlay

Card fades out after 2 seconds

Notification badge decrements


Reviewed incidents section below:

Same layout but buttons replaced with decision badge

Accepted = green DISPATCHED badge

Ignored = red FALSE ALARM badge

Shows time of incident + time of review + response time


PAGE 4 — DISPATCH (dispatch.html?id=INC-XXXX)

Opens after accepting an incident.
Pulsing red border around entire page (fades after 5 seconds).

Header:

EMERGENCY RESPONSE INITIATED (large, Orbitron, red, pulsing)

Incident ID + type + camera + timestamp


Four steps animate in sequentially (600ms apart each):

STEP 1 — INCIDENT LOCATION (icon: 📍, color: cyan)

Camera ID and location name

GPS coordinates from camera record

Incident type and confidence

Time of detection


STEP 2 — AMBULANCE DISPATCHED (icon: 🚑, color: green)

Animated after 600ms

Unit: AMB-07 — City Emergency Services

Nearest hospital with available beds

Hospital GPS coordinates

ETA calculated from distance

Route: Camera location → Hospital


STEP 3 — TRAFFIC POLICE NOTIFIED (icon: 🚔, color: amber)

Animated after 1200ms

Nearest police station name

Contact number

Route clearance message

Backup unit alert


STEP 4 — GOLDEN HOUR WINDOW (icon: ⏱, color: red)

Animated after 1800ms

Large countdown timer: 60:00 counting down in real time

MM:SS format in Orbitron font

Progress bar depleting

"CRITICAL TRAUMA RESPONSE WINDOW" label


SVG Route Map (below the steps):

Simple SVG fake map with grid background

Red blinking dot = incident location with GPS label

Green dot = nearest hospital with GPS label

Amber moving dot = ambulance unit moving between them

Dashed line connecting incident to hospital

No external map API — pure SVG


Bottom buttons:

RETURN TO DASHBOARD → index.html

VIEW FULL INCIDENT LOG → shows incident table overlay


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 8 — DETECTION PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Two separate MJPEG streams per camera:

1. Clean stream → used on dashboard (no boxes)


2. Detection stream → used on camera detail page (with boxes)



Both streams run from same detection thread.
Detection thread processes frames in background.
Dashboard just receives raw frames.
Camera detail page receives annotated frames.

Frame processing (per camera thread):

1. OpenCV reads frame from video file or webcam


2. Loop video when it ends (cap.set(CAP_PROP_POS_FRAMES, 0))


3. Every 2nd frame: run YOLOv8n with ByteTrack


4. Every frame: run MediaPipe Pose on detected person crops


5. Every frame: draw annotations on copy of frame


6. Push raw frame to clean buffer


7. Push annotated frame to detection buffer


8. Push raw frame to circular clip buffer (deque)


9. Run accident detection logic every 5 frames


10. Encode both frames as JPEG for streaming



YOLOv8n settings for CPU optimization:

model = YOLO('yolov8n.pt')

model.track(frame, persist=True, tracker='bytetrack.yaml',
classes=[0,1,2,3,7], conf=0.45, iou=0.5,
imgsz=416, verbose=False)

classes: 0=person, 1=bicycle, 2=car, 3=motorcycle, 7=truck

imgsz=416 instead of 640 for speed

Process every 2nd frame, reuse last result on skipped frames


MediaPipe Pose:

mp.solutions.pose.Pose(
static_image_mode=False,
model_complexity=0,
min_detection_confidence=0.5,
min_tracking_confidence=0.5)

model_complexity=0 for fastest CPU performance

Run on each detected person's cropped bbox region

Extract landmarks: LEFT_SHOULDER, RIGHT_SHOULDER,
LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE,
LEFT_ANKLE, RIGHT_ANKLE

Draw skeleton lines on person in detection stream


Tracking ID format:

Person IDs displayed as X1, X2, X3, X4...

Vehicle IDs displayed as V1, V2, V3...

IDs are assigned sequentially as objects enter frame

If person leaves and re-enters: gets new incremented ID

This is handled by ByteTrack internally, we just format
the display label


Speed calculation:

Track bbox center (cx, cy) per object ID per frame

speed_px = distance between current and previous center

speed_kmh = speed_px * 0.05 (calibration constant)

Display on vehicle boxes only

Smooth with rolling average of last 5 frames


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 9 — ACCIDENT DETECTION LOGIC (HEURISTICS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

All detection is heuristic-based. We do NOT use any
pre-trained accident classification model.
Judges are told: "heuristic behavioral analysis —
AI flags, humans verify."

DETECTION 1 — FALL DETECTION (PRIMARY via MediaPipe)
Method A (MediaPipe — preferred):

Get shoulder midpoint Y and hip midpoint Y

Get ankle midpoint Y

If shoulders Y > hips Y (shoulders below hips in frame)
this means person is horizontal → fall

Confirm if this persists for 45+ consecutive frames

Confidence: 88%


Method B (YOLO bbox fallback):

If bbox width > bbox height * 1.3 (wider than tall)

Persists for 60+ frames

Confidence: 75%


Use Method A if MediaPipe landmarks available,
fall back to Method B if not.

DETECTION 2 — COLLISION

For each pair of vehicle bboxes:
Calculate IoU (Intersection over Union)
IoU = intersection_area / union_area

If IoU > 0.12 AND was 0 in previous 15 frames
AND at least one vehicle speed > 8 km/h

Confidence: 82%


DETECTION 3 — PERSON UNCONSCIOUS

Person bbox center moves less than 15px over 300 frames

AND MediaPipe confirms horizontal pose (or bbox fallback)

Confidence: 90%


DETECTION 4 — CROWD SCATTER

Person count jumps from <3 to >6 within 20 frames

Confidence: 72%


DETECTION 5 — MANUAL FLAG

Operator clicks "FLAG SUSPICIOUS ACTIVITY" button

Creates incident of type "Manual Flag"

Confidence: 100% (human triggered)

Immediately cuts 30-second clip and sends to review


When ANY detection fires:

1. Check cooldown: same camera cannot fire for 30 seconds


2. Generate incident_id: INC-XXXX (auto-increment from DB)


3. Save thumbnail: current annotated frame →
/static/thumbnails/INC-XXXX.jpg


4. Call buffer.save_clip(incident_id, camera_id)


5. Insert incident row in DB with decision=Pending


6. Emit SocketIO event 'new_alert' to all clients


7. Start 30-second cooldown for this camera



━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 10 — BUFFER SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Per camera: collections.deque(maxlen=fps*30)
Stores raw numpy frames (not annotated)
FPS auto-detected from video or defaulted to 20

save_clip(incident_id, camera_id):

Takes all frames currently in deque

Writes to /static/clips/INC-XXXX.mp4

Uses cv2.VideoWriter with mp4v codec

Returns file path, stores in DB


delete_clip(incident_id):

Called automatically after operator decision

Deletes /static/clips/INC-XXXX.mp4

Updates DB: clip_path = NULL


IMPORTANT: Clips are ALWAYS deleted after decision.
Only thumbnail (single frame JPG) and DB log entry survive.
This is by design — privacy + storage efficiency.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 11 — FLASK ROUTES AND SOCKETIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GET  /                          → index.html
GET  /camera/<camera_id>        → camera.html
GET  /alerts                    → alerts.html
GET  /dispatch/<incident_id>    → dispatch.html

GET  /video_feed/<camera_id>         → clean MJPEG stream
GET  /video_feed_detection/<cam_id>  → annotated MJPEG stream

POST /api/start_feed    → {camera_id, source, file_path}
POST /api/stop_feed     → {camera_id}
GET  /api/incidents     → all incidents JSON
GET  /api/incident/<id> → single incident JSON
GET  /api/stats         → {total, accepted, ignored,
pending, avg_response_time}
GET  /api/hospitals     → all hospitals JSON
GET  /api/police        → all police stations JSON
GET  /api/cameras       → all cameras JSON

POST /api/review/<incident_id>
→ records time_of_review, marks reviewed=True

POST /api/decision/<incident_id>
→ {decision: "accept" or "ignore"}
→ records time of decision
→ calculates response_time_seconds
→ calls delete_clip()
→ if accept: finds nearest hospital, stores in DB
→ returns full incident data for dispatch page

POST /api/manual_flag/<camera_id>
→ immediately triggers incident creation + alert

SocketIO events emitted by server:

'new_alert': {incident_id, type, camera_id, location,
confidence, time, thumbnail_path}

'detection_update': {camera_id, persons, vehicles,
fps, active_alerts}


SocketIO events listened from client:

'connect': client joins monitoring room

'request_stats': server emits current stats back


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 12 — DESIGN SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Colors:
--bg:      #04080F  (near black, main background)
--panel:   #080E1A  (dark blue-black, card backgrounds)
--border:  #0D2137  (dark border color)
--accent:  #00D4FF  (cyan, primary highlight)
--danger:  #FF3C5A  (red, alerts and danger)
--safe:    #39FF6E  (green, confirmed/safe/dispatched)
--warn:    #FFB800  (amber, police/warnings)
--text:    #C8DFF0  (light blue-white, body text)
--muted:   #3A5570  (muted blue-gray, secondary text)

Fonts (Google Fonts):

'Orbitron' 400/700/900: headings, IDs, system names

'Rajdhani' 400/500/600/700: UI text, labels, buttons

'Share Tech Mono': coordinates, data values, timestamps


Key animations:

pulse: opacity 1→0.3→1 for active/alert states

blink: box-shadow glow pulse for alert cards

scanline: top-to-bottom line sweep on camera feeds

fadeUp: entrance animation for dispatch steps

borderPulse: red border animation on dispatch page


Design aesthetic:

Dark military/surveillance control room

Cyan glow accents

Monospaced data everywhere

No rounded corners larger than 4px

Thin 1px borders with glow on hover - Semi-transparent panel backgrounds


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 13 — IMPORTANT DECISIONS ALREADY MADE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NO DeepSORT — use ByteTrack (built into Ultralytics)


2. NO corner-bracket ESP style on camera detail page —
use solid rectangle bounding boxes


3. Dashboard shows CLEAN video (no boxes)
Camera detail page shows ANNOTATED video (with boxes)


4. NO real ambulance API — fully simulated


5. NO cloud — localhost only


6. Clips are ALWAYS deleted after operator decision


7. Only thumbnail + DB log entry persists per incident


8. MediaPipe Pose is PRIMARY fall detection method
YOLO bbox ratio is FALLBACK method


9. Public safety detection is NOT automated —
only manual flag button triggers it
Reason: false positive rate too high for automated crime


10. Person tracking IDs: X1, X2, X3 (X prefix for persons)
Vehicle tracking IDs: V1, V2, V3 (V prefix for vehicles)


11. Video loops when it ends (for demo purposes)


12. Webcam is CAM-05, has its own tile with on/off button


13. Simulate Alert button on dashboard for demo purposes
(fires a fake incident so judges can see the full flow)


14. YOLOv8n processes every 2nd frame for CPU optimization
imgsz=416 for speed, conf threshold 0.45


15. Golden hour timer starts from 60:00 on dispatch page



━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 14 — WHAT TO SAY TO JUDGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Detection is heuristic-based, not a black box AI

False positives exist — that is WHY human review exists

We deliberately did NOT automate public safety decisions

Speed detection is approximate pixel-based estimation

GPS coordinates are static per camera (prototype)

No real emergency APIs — prototype demonstrates the flow

MediaPipe Pose gives us 33 skeletal landmarks for
accurate human pose analysis

ByteTrack maintains object identity across frames

The 30-second clip is deleted after review — privacy by design

System is designed to scale: replace static GPS with real
GPS modules, replace simulated dispatch with real APIs

few more things I wanna add on like In backend during detection it should work like 
yolo then pose estimation get skeleton then HAR rules detects fall / motion then decision engine then alert system that architecture is what we are using 


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END OF BRIEFING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are now fully briefed. Acknowledge that you understand
the complete project and wait for my next instruction. Don't make just understand whole thing of program for now