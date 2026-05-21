const video = document.querySelector("#camera");
const overlay = document.querySelector("#overlay");
const statusLine = document.querySelector("#statusLine");
const studentForm = document.querySelector("#studentForm");
const studentSelect = document.querySelector("#studentSelect");
const studentList = document.querySelector("#studentList");
const attendanceList = document.querySelector("#attendanceList");
const reportDate = document.querySelector("#reportDate");
const excelExport = document.querySelector("#excelExport");
const pdfExport = document.querySelector("#pdfExport");

let stream = null;
let recognitionTimer = null;

const today = new Date().toISOString().slice(0, 10);
reportDate.value = today;

function setStatus(message) {
  statusLine.textContent = message;
}

function selectedDate() {
  return reportDate.value || today;
}

function frameData() {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.82);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

async function startCamera() {
  stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
  video.srcObject = stream;
  setStatus("Camera is ready.");
}

function stopRecognition() {
  clearInterval(recognitionTimer);
  recognitionTimer = null;
  drawDetections([]);
  setStatus("Recognition stopped.");
}

function drawDetections(detections) {
  const ctx = overlay.getContext("2d");
  overlay.width = video.videoWidth || overlay.clientWidth;
  overlay.height = video.videoHeight || overlay.clientHeight;
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  ctx.lineWidth = 3;
  ctx.font = "18px system-ui";

  detections.forEach((item) => {
    const { x, y, w, h } = item.box;
    const known = item.status === "Present";
    ctx.strokeStyle = known ? "#2dd17d" : "#ffb15c";
    ctx.fillStyle = known ? "#14543d" : "#8a441f";
    ctx.strokeRect(x, y, w, h);
    const label = known ? `${item.name} ${Math.round(item.confidence * 100)}%` : "Unknown";
    const labelWidth = ctx.measureText(label).width + 16;
    ctx.fillRect(x, Math.max(0, y - 30), labelWidth, 28);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, x + 8, Math.max(20, y - 10));
  });
}

async function recognizeOnce() {
  if (!video.videoWidth) return;
  try {
    const result = await api("/api/recognize", {
      method: "POST",
      body: JSON.stringify({ image: frameData() }),
    });
    drawDetections(result.detections);
    const names = result.detections.map((d) => d.name).join(", ") || "No faces";
    document.querySelector("#lastScan").textContent = new Date().toLocaleTimeString();
    setStatus(`Scan: ${names}`);
    await refreshDashboard();
    await refreshAttendance();
  } catch (error) {
    setStatus(error.message);
  }
}

async function startRecognition() {
  if (!stream) await startCamera();
  if (recognitionTimer) return;
  await recognizeOnce();
  recognitionTimer = setInterval(recognizeOnce, 2500);
}

async function captureSample() {
  if (!stream) await startCamera();
  const studentId = studentSelect.value;
  if (!studentId) {
    setStatus("Add and select a student first.");
    return;
  }
  try {
    const result = await api("/api/enroll-frame", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId, image: frameData() }),
    });
    setStatus(`${result.message} Total samples: ${result.sample_count}`);
    await refreshStudents();
  } catch (error) {
    setStatus(error.message);
  }
}

async function refreshStudents() {
  const students = await api("/api/students");
  studentSelect.innerHTML = students
    .map((s) => `<option value="${s.id}">${s.roll_no} - ${s.name}</option>`)
    .join("");
  studentList.innerHTML = students
    .map(
      (s) => `
      <div class="list-item">
        <strong>${s.name}</strong>
        <span>${s.roll_no} · ${s.class_name}</span>
        <span>${s.email || "No email"} · ${s.phone || "No phone"}</span>
        <span class="badge">${s.sample_count} face samples</span>
      </div>`
    )
    .join("");
}

async function refreshDashboard() {
  const data = await api(`/api/dashboard?date=${encodeURIComponent(selectedDate())}`);
  document.querySelector("#totalStudents").textContent = data.students;
  document.querySelector("#presentCount").textContent = data.present;
  document.querySelector("#absentCount").textContent = data.absent;
}

async function refreshAttendance() {
  const rows = await api(`/api/attendance?date=${encodeURIComponent(selectedDate())}`);
  attendanceList.innerHTML = rows
    .map(
      (row) => `
      <div class="list-item">
        <strong>${row.name}</strong>
        <span>${row.roll_no} · ${row.class_name}</span>
        <span>${row.first_seen || "-"} to ${row.last_seen || "-"}</span>
        <span class="badge ${row.status === "Absent" ? "absent" : ""}">${row.status}</span>
      </div>`
    )
    .join("");
  excelExport.href = `/export/excel?date=${encodeURIComponent(selectedDate())}`;
  pdfExport.href = `/export/pdf?date=${encodeURIComponent(selectedDate())}`;
}

studentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(studentForm).entries());
  try {
    await api("/api/students", { method: "POST", body: JSON.stringify(payload) });
    studentForm.reset();
    setStatus("Student added. Capture face samples next.");
    await refreshStudents();
    await refreshDashboard();
    await refreshAttendance();
  } catch (error) {
    setStatus(error.message);
  }
});

document.querySelector("#startCamera").addEventListener("click", startCamera);
document.querySelector("#startRecognition").addEventListener("click", startRecognition);
document.querySelector("#stopRecognition").addEventListener("click", stopRecognition);
document.querySelector("#captureSample").addEventListener("click", captureSample);

document.querySelector("#sendAlerts").addEventListener("click", async () => {
  try {
    const result = await api("/api/alerts/absent", {
      method: "POST",
      body: JSON.stringify({ date: selectedDate() }),
    });
    setStatus(`Alerts sent: ${result.sent.length}. Skipped: ${result.skipped.length}.`);
  } catch (error) {
    setStatus(error.message);
  }
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-body").forEach((body) => body.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector(`#${tab.dataset.tab}Tab`).classList.add("active");
  });
});

reportDate.addEventListener("change", async () => {
  await refreshDashboard();
  await refreshAttendance();
});

window.addEventListener("load", async () => {
  if (window.lucide) window.lucide.createIcons();
  await refreshStudents();
  await refreshDashboard();
  await refreshAttendance();
});
