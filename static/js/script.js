/**
 * Voice-Driven eCommerce Analytics Dashboard
 * Frontend JavaScript — Voice, Charts, API calls
 */

/* ── Live clock ─────────────────────────────────────────────────────────── */
(function startClock() {
  const el = document.getElementById("clock");
  if (!el) return;
  function tick() {
    el.textContent = new Date().toLocaleString("en-IN", {
      weekday: "long", year: "numeric", month: "long",
      day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }
  tick();
  setInterval(tick, 1000);
})();

/* ── Status helper ───────────────────────────────────────────────────────── */
function setStatus(msg, type = "idle") {
  const el = document.getElementById("statusMsg");
  if (!el) return;
  el.textContent = msg;
  el.className   = `status-${type}`;
}

/* ── Web Speech API (Voice Input) ─────────────────────────────────────────── */
let recognition = null;
let isListening = false;

function initSpeechRecognition() {
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("Web Speech API not supported in this browser.");
    return null;
  }
  const r        = new SpeechRecognition();
  r.lang         = "en-US";
  r.interimResults = true;
  r.maxAlternatives = 1;

  r.onstart = () => {
    isListening = true;
    updateMicBtn(true);
    setStatus("🎙 Listening…", "loading");
  };

  r.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map((r) => r[0].transcript)
      .join("");
    document.getElementById("queryInput").value = transcript;
    const txEl = document.getElementById("transcript");
    if (txEl) txEl.textContent = `"${transcript}"`;

    if (event.results[event.results.length - 1].isFinal) {
      submitQuery(true);
    }
  };

  r.onerror = (event) => {
    console.error("Speech error:", event.error);
    setStatus(`Speech error: ${event.error}`, "error");
    stopListening();
  };

  r.onend = () => {
    isListening = false;
    updateMicBtn(false);
    setStatus("Ready", "idle");
  };

  return r;
}

function toggleVoice() {
  if (!recognition) recognition = initSpeechRecognition();
  if (!recognition) {
    alert("Voice recognition is not supported in your browser. Please use Chrome.");
    return;
  }
  if (isListening) {
    stopListening();
  } else {
    recognition.start();
  }
}

function stopListening() {
  if (recognition && isListening) {
    recognition.stop();
  }
}

function updateMicBtn(active) {
  const btn = document.getElementById("micBtn");
  if (!btn) return;
  if (active) {
    btn.classList.add("active");
    btn.querySelector(".mic-label").textContent = "Stop";
    btn.querySelector(".mic-icon").textContent  = "⏹";
  } else {
    btn.classList.remove("active");
    btn.querySelector(".mic-label").textContent = "Start Voice";
    btn.querySelector(".mic-icon").textContent  = "🎤";
  }
}

/* ── Query submission ────────────────────────────────────────────────────── */
async function submitQuery(withVoice = false) {
  const input = document.getElementById("queryInput");
  const query = (input?.value || "").trim();
  if (!query) {
    setStatus("Please enter a query", "error");
    return;
  }

  setStatus("Analysing…", "loading");
  hideResult();

  try {
    const res  = await fetch("/analyze", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ query, voice: withVoice }),
    });
    const data = await res.json();

    if (data.error) {
      setStatus(`Error: ${data.error}`, "error");
      return;
    }

    displayResult(data);
    setStatus("Done ✓", "success");
  } catch (err) {
    console.error(err);
    setStatus("Network error", "error");
  }
}

function displayResult(data) {
  const area  = document.getElementById("resultArea");
  const text  = document.getElementById("resultText");
  const audio = document.getElementById("audioPlayer");
  const dDiv  = document.getElementById("resultData");

  area.classList.remove("hidden");

  text.textContent = data.text || JSON.stringify(data, null, 2);

  // Audio
  if (data.audio_url) {
    audio.src = data.audio_url;
    audio.classList.remove("hidden");
    audio.play().catch(() => {});
  } else {
    audio.classList.add("hidden");
  }

  // Extra data
  const extra = { ...data };
  delete extra.text;
  delete extra.audio_url;
  dDiv.textContent = JSON.stringify(extra, null, 2);
}

function hideResult() {
  const area = document.getElementById("resultArea");
  if (area) area.classList.add("hidden");
}

function quickQuery(q) {
  const inp = document.getElementById("queryInput");
  if (inp) inp.value = q;
  submitQuery(false);
}

/* ── Enter key on query input ────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  const inp = document.getElementById("queryInput");
  if (inp) {
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitQuery(false);
    });
  }
});

/* ── Chart.js helpers ────────────────────────────────────────────────────── */
const CHART_DEFAULTS = {
  color: "#d1fae5",
  borderColor: "#1e3329",
  plugins: {
    legend: { labels: { color: "#6b7280", font: { family: "'DM Sans'" } } },
  },
  scales: {
    x: {
      ticks: { color: "#6b7280" },
      grid:  { color: "#1e3329" },
    },
    y: {
      ticks: { color: "#6b7280" },
      grid:  { color: "#1e3329" },
    },
  },
};

async function loadCharts() {
  await Promise.all([
    loadLineChart(),
    loadDoughnutChart(),
    loadBarChart(),
  ]);
}

async function loadLineChart() {
  const canvas = document.getElementById("chartRevenue");
  if (!canvas) return;
  try {
    const res  = await fetch("/api/chart-data/revenue_7days");
    const data = await res.json();
    new Chart(canvas, {
      type: "line",
      data,
      options: {
        ...CHART_DEFAULTS,
        plugins: {
          ...CHART_DEFAULTS.plugins,
          title: { display: false },
        },
        elements: { point: { radius: 5, hoverRadius: 7, backgroundColor: "#10b981" } },
      },
    });
  } catch (e) {
    console.error("Line chart error:", e);
  }
}

async function loadDoughnutChart() {
  const canvas = document.getElementById("chartCategory");
  if (!canvas) return;
  try {
    const res  = await fetch("/api/chart-data/category");
    const data = await res.json();
    new Chart(canvas, {
      type: "doughnut",
      data,
      options: {
        plugins: {
          legend: {
            position: "right",
            labels: { color: "#6b7280", font: { family: "'DM Sans'" }, boxWidth: 12 },
          },
        },
        cutout: "62%",
      },
    });
  } catch (e) {
    console.error("Doughnut chart error:", e);
  }
}

async function loadBarChart() {
  const canvas = document.getElementById("chartProducts");
  if (!canvas) return;
  try {
    const res  = await fetch("/api/chart-data/top_products");
    const data = await res.json();
    new Chart(canvas, {
      type: "bar",
      data,
      options: {
        ...CHART_DEFAULTS,
        indexAxis: "y",
        plugins: {
          ...CHART_DEFAULTS.plugins,
          title: { display: false },
        },
      },
    });
  } catch (e) {
    console.error("Bar chart error:", e);
  }
}

/* ── Report modal ─────────────────────────────────────────────────────────── */
function openReportModal()  { document.getElementById("reportModal").classList.remove("hidden"); }
function closeReportModal() { document.getElementById("reportModal").classList.add("hidden"); }

async function generateReport() {
  const type  = document.getElementById("reportType")?.value  || "daily";
  const email = document.getElementById("reportEmail")?.value || "";
  const res   = document.getElementById("reportResult");

  res.className = "report-result";
  res.classList.remove("hidden");
  res.textContent = "Generating report…";

  try {
    const resp = await fetch("/api/generate-report", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ type, email }),
    });
    const data = await resp.json();

    if (data.success) {
      res.classList.add("success");
      res.innerHTML = `✓ Report generated! <a href="${data.url}" target="_blank" style="color:inherit;text-decoration:underline">Download</a>`;
    } else {
      res.classList.add("error");
      res.textContent = `Error: ${data.error || "Unknown error"}`;
    }
  } catch (e) {
    res.classList.add("error");
    res.textContent = "Network error";
  }
}

/* ── Load sample data ────────────────────────────────────────────────────── */
async function loadSampleData() {
  if (!confirm("This will load 50 sample orders into DynamoDB. Continue?")) return;
  setStatus("Loading sample data…", "loading");
  try {
    const res  = await fetch("/api/load-sample-data", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      setStatus(`✓ Loaded ${data.loaded} orders`, "success");
    } else {
      setStatus(`Error: ${data.error}`, "error");
    }
  } catch (e) {
    setStatus("Network error", "error");
  }
}

/* ── Image analysis ───────────────────────────────────────────────────────── */
async function analyzeImage() {
  const fileInput = document.getElementById("imageInput");
  const labelsDiv = document.getElementById("imageLabels");
  if (!fileInput?.files[0]) return;

  labelsDiv.innerHTML = "<span style='color:#6b7280;font-size:.82rem'>Analysing with Rekognition…</span>";
  labelsDiv.classList.remove("hidden");

  const formData = new FormData();
  formData.append("image", fileInput.files[0]);

  try {
    const res  = await fetch("/api/analyze-image", { method: "POST", body: formData });
    const data = await res.json();

    if (data.labels?.length) {
      labelsDiv.innerHTML = data.labels
        .map((l) => `<span class="label-tag">${l.name} (${l.confidence}%)</span>`)
        .join("");
    } else {
      labelsDiv.innerHTML = "<span style='color:#6b7280;font-size:.82rem'>No labels detected</span>";
    }
  } catch (e) {
    labelsDiv.innerHTML = "<span style='color:#ef4444;font-size:.82rem'>Analysis failed</span>";
  }
}

/* ── Drag-and-drop on image zone ─────────────────────────────────────────── */
(function setupDrop() {
  const zone = document.getElementById("dropZone");
  if (!zone) return;
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.style.borderColor = "#10b981"; });
  zone.addEventListener("dragleave", ()  => { zone.style.borderColor = ""; });
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.style.borderColor = "";
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      document.getElementById("imageInput").files = e.dataTransfer.files;
      analyzeImage();
    }
  });
})();

/* ── Bootstrap on DOMContentLoaded ─────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("chartRevenue")) {
    loadCharts();
  }
});