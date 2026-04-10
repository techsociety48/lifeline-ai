const state = { incidents: [], reviewedEnabled: new Set() };

function $id(id) { return document.getElementById(id); }
async function api(url, opts = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
function fmtTime(iso) {
  if (!iso) return "--";
  return new Date(iso).toLocaleString();
}
function setClock() {
  const el = $id("liveClock");
  if (!el) return;
  const tick = () => { el.textContent = new Date().toLocaleString(); };
  tick();
  setInterval(tick, 1000);
}
async function setNotifCount() {
  const badge = $id("notifCount");
  if (!badge) return;
  const stats = await api("/api/stats").catch(() => ({ pending: 0 }));
  badge.textContent = String(stats.pending || 0);
}
function mmss(seconds) {
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

async function renderDashboard() {
  const [cameras, hospitals, police, incidents, stats] = await Promise.all([
    api("/api/cameras"), api("/api/hospitals"), api("/api/police"), api("/api/incidents"), api("/api/stats")
  ]);
  state.incidents = incidents;
  const grid = $id("cameraGrid");
  grid.innerHTML = "";

  cameras.forEach((cam) => {
    const tile = document.createElement("article");
    tile.className = "card camera-tile";
    const statusClass = cam.status === "active" || cam.status === "webcam" ? "safe" : "warn";
    tile.innerHTML = `
      <div class="tile-head"><strong>${cam.id}</strong><span>${cam.location}</span><span class="${statusClass}">${cam.status}</span><span>Severity: ${cam.severity}</span></div>
      <img class="tile-stream" src="/video_feed/${cam.id}" alt="${cam.id}">
      <div class="tile-foot">
        <span class="mono">GPS: ${cam.lat}, ${cam.lng}</span>
        <span class="mono">Last event: live monitoring</span>
        <a class="btn" href="/camera?id=${cam.id}">CAMERA DETAIL</a>
      </div>`;
    grid.appendChild(tile);
  });
  const manualTile = document.createElement("article");
  manualTile.className = "card camera-tile";
  manualTile.innerHTML = `
    <h3>Manual Flag</h3>
    <select id="manualCamSelect">${cameras.map((c) => `<option value="${c.id}">${c.id}</option>`).join("")}</select>
    <button id="manualFlagBtn" class="btn danger">FLAG SUSPICIOUS ACTIVITY</button>`;
  grid.appendChild(manualTile);

  $id("manualFlagBtn").addEventListener("click", async () => {
    const cameraId = $id("manualCamSelect").value;
    await api(`/api/manual_flag/${cameraId}`, { method: "POST" });
    await renderDashboard();
    await setNotifCount();
    alert(`Manual incident created for ${cameraId}.`);
  });

  $id("statCameras").textContent = String(cameras.filter((c) => c.status !== "idle").length);
  $id("statIncidents").textContent = String(stats.total || 0);
  $id("statResponse").textContent = mmss(stats.avg_response_time || 0);

  const hBody = document.querySelector("#hospitalTable tbody");
  const pBody = document.querySelector("#policeTable tbody");
  hBody.innerHTML = hospitals.map((h) => {
    const status = h.empty_beds > 5 ? "AVAILABLE" : h.empty_beds > 0 ? "LIMITED" : "FULL";
    const cls = h.empty_beds > 5 ? "safe" : h.empty_beds > 0 ? "warn" : "danger";
    return `<tr><td>${h.name}</td><td>--</td><td>${h.empty_beds}</td><td class="mono">${h.lat},${h.lng}</td><td class="${cls}">${status}</td></tr>`;
  }).join("");
  pBody.innerHTML = police.map((p) => `<tr><td>${p.name}</td><td>--</td><td>${p.contact}</td><td class="mono">${p.lat},${p.lng}</td><td class="safe">READY</td></tr>`).join("");

  const strip = $id("incidentStrip");
  strip.innerHTML = incidents.slice(0, 5).map((i) => `
    <article class="incident-card">
      <strong>${i.incident_type}</strong>
      <p class="mono">${i.incident_id}</p>
      <p>${fmtTime(i.time_of_incident)}</p>
      <p class="${i.decision === "accept" ? "safe" : i.decision === "ignore" ? "danger" : "warn"}">${i.decision}</p>
    </article>`).join("");
}

async function renderCameraPage() {
  const camId = document.body.dataset.cameraId;
  const list = $id("detectionLog");
  const socket = window.io ? window.io() : null;
  if (socket) {
    socket.on("detection_update", (d) => {
      if (d.camera_id !== camId) return;
      $id("hudModel").textContent = `MODEL: YOLOv8n | TRACKER: ByteTrack | FPS: ${d.fps}`;
      const conf = d.yolo_conf != null ? d.yolo_conf : 0.32;
      const sz = d.yolo_imgsz != null ? d.yolo_imgsz : 640;
      $id("hudCounts").textContent = `PERSONS: ${d.persons} | VEHICLES: ${d.vehicles} | CONF: ${conf} | SZ: ${sz}`;
      const row = document.createElement("li");
      row.className = "mono";
      row.textContent = `${new Date().toLocaleTimeString()} | persons=${d.persons} vehicles=${d.vehicles}`;
      list.prepend(row);
      while (list.children.length > 10) list.removeChild(list.lastChild);
    });
  }
}

async function renderAlertsPage() {
  const pending = $id("pendingList");
  const reviewed = $id("reviewedList");
  const modal = $id("reviewModal");
  const markBtn = $id("markReviewedBtn");
  const reviewVideo = $id("reviewVideo");
  let activeIncident = null;

  async function paint() {
    const incidents = await api("/api/incidents");
    state.incidents = incidents;
    const p = incidents.filter((i) => i.decision === "Pending");
    const r = incidents.filter((i) => i.decision !== "Pending");
    pending.innerHTML = p.map((i) => `
      <article class="alert-card">
        <div>
          <strong>${i.incident_id} | ${i.incident_type}</strong>
          <p class="mono">${i.camera_id} | ${i.camera_location}</p>
          <p class="mono">${fmtTime(i.time_of_incident)} | CONF ${Number(i.confidence).toFixed(0)}%</p>
        </div>
        <div class="button-row">
          <button class="btn review" data-id="${i.incident_id}">REVIEW FOOTAGE</button>
          <button class="btn accept" data-id="${i.incident_id}" ${state.reviewedEnabled.has(i.incident_id) ? "" : "disabled"}>ACCEPT</button>
          <button class="btn danger ignore" data-id="${i.incident_id}" ${state.reviewedEnabled.has(i.incident_id) ? "" : "disabled"}>IGNORE</button>
        </div>
      </article>`).join("");
    reviewed.innerHTML = r.map((i) => `
      <article class="alert-card">
        <strong>${i.incident_id}</strong>
        <span class="${i.decision === "accept" ? "safe" : "danger"}">${i.decision === "accept" ? "DISPATCHED" : "FALSE ALARM"}</span>
        <span class="mono">${fmtTime(i.time_of_review)}</span>
      </article>`).join("");
    await setNotifCount();
  }

  pending.addEventListener("click", async (e) => {
    const target = e.target;
    const id = target.dataset.id;
    if (!id) return;
    if (target.classList.contains("review")) {
      const incident = state.incidents.find((x) => x.incident_id === id);
      activeIncident = id;
      reviewVideo.src = incident?.clip_path || "";
      modal.classList.remove("hidden");
      return;
    }
    if (target.classList.contains("accept")) {
      if (!state.reviewedEnabled.has(id)) {
        alert("Please review the footage first before accepting this incident.");
        return;
      }
      await api(`/api/decision/${id}`, { method: "POST", body: JSON.stringify({ decision: "accept" }) });
      window.location.href = `/dispatch?id=${id}`;
      return;
    }
    if (target.classList.contains("ignore")) {
      if (!state.reviewedEnabled.has(id)) {
        alert("Please review the footage first before ignoring this incident.");
        return;
      }
      if (!confirm("Confirm: Mark as False Alarm?")) return;
      await api(`/api/decision/${id}`, { method: "POST", body: JSON.stringify({ decision: "ignore" }) });
      await paint();
    }
  });

  markBtn.addEventListener("click", async () => {
    modal.classList.add("hidden");
    if (!activeIncident) return;
    await api(`/api/review/${activeIncident}`, { method: "POST" });
    state.reviewedEnabled.add(activeIncident);
    await paint();
  });

  await paint();
}

async function runDispatch() {
  const steps = document.querySelectorAll(".step");
  steps.forEach((step, i) => setTimeout(() => step.classList.remove("hidden"), 600 * (i + 1)));
  const incidentId = document.body.dataset.incidentId;
  const meta = $id("dispatchMeta");
  if (incidentId) {
    const incident = await api(`/api/incident/${incidentId}`).catch(() => null);
    if (incident) {
      meta.textContent = `Incident: ${incident.incident_id} | Type: ${incident.incident_type} | Camera: ${incident.camera_id} | Time: ${fmtTime(incident.time_of_incident)}`;
    }
  }
  const el = $id("countdown");
  let seconds = 600;
  setInterval(() => {
    seconds = Math.max(0, seconds - 1);
    el.textContent = mmss(seconds);
  }, 1000);
}

async function main() {
  setClock();
  await setNotifCount();
  const page = document.body.dataset.page;
  if (page === "dashboard") await renderDashboard();
  if (page === "camera") await renderCameraPage();
  if (page === "alerts") await renderAlertsPage();
  if (page === "dispatch") await runDispatch();
}

document.addEventListener("DOMContentLoaded", () => {
  main().catch((e) => console.error(e));
});
