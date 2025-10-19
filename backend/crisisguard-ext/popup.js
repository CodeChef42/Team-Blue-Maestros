document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("ratesForm");
  const statusJson = document.getElementById("statusJson");
  const refreshBtn = document.getElementById("refreshStatus");

  // Right panel base elements
  const rightPanel = document.querySelector(".right-panel");
  const cpuBar = document.getElementById("cpuBar");
  const diskBar = document.getElementById("diskBar");
  const confBar = document.getElementById("confBar");
  const cpuValue = document.getElementById("cpuValue");
  const diskValue = document.getElementById("diskValue");
  const confValue = document.getElementById("confValue");
  const alertArea = document.getElementById("alertArea");

  // Create a section for detector metrics dynamically
  const detectorsSection = document.createElement("div");
  detectorsSection.innerHTML = `
    <hr/>
    <h4 style="margin-top:10px; font-size:14px; color:#0078d4;">Detector Scores</h4>
    <div id="detectorsArea"></div>
  `;
  rightPanel.appendChild(detectorsSection);
  const detectorsArea = document.getElementById("detectorsArea");

  // Keep references to created bars for reuse
  const detectorBars = {};

  async function fetchStatus() {
    try {
      const resp = await fetch("http://127.0.0.1:8000/status");
      const data = await resp.json();
      updateUI(data);
    } catch (err) {
      console.error("Error fetching status", err);
    }
  }

  function createDetectorBar(name, value) {
    const safeName = name.replace(/_/g, " ");
    const container = document.createElement("div");
    container.classList.add("metric");
    container.innerHTML = `
      <span class="metric-label">${safeName}</span>
      <div class="bar"><div class="bar-fill" id="${name}Bar"></div></div>
      <span class="metric-value" id="${name}Value">${(value * 100).toFixed(
      1
    )}%</span>
    `;
    detectorsArea.appendChild(container);
    detectorBars[name] = {
      bar: container.querySelector(`#${name}Bar`),
      value: container.querySelector(`#${name}Value`),
    };
  }

  function updateUI(data) {
    statusJson.textContent = JSON.stringify(data, null, 2);

    const detectors = data.detectors || {};
    const conf = (data.confidence || 0) * 100;
    const cpu = data.cpu_usage || 0;
    const io = data.disk_io_mb || 0;

    // Confidence
    confBar.style.width = Math.min(conf, 100) + "%";
    confValue.textContent = conf.toFixed(1) + "%";

    // CPU + Disk
    cpuBar.style.width = Math.min(cpu, 100) + "%";
    cpuValue.textContent = cpu.toFixed(1) + "%";
    diskBar.style.width = Math.min(io * 10, 100) + "%";
    diskValue.textContent = io.toFixed(2) + " MB/s";

    // Color intensity
    cpuBar.style.backgroundColor =
      cpu < 40 ? "#4caf50" : cpu < 70 ? "#ffb300" : "#e53935";
    diskBar.style.backgroundColor =
      io < 1 ? "#4caf50" : io < 5 ? "#ffb300" : "#e53935";
    confBar.style.backgroundColor =
      conf < 30 ? "#4caf50" : conf < 60 ? "#ffb300" : "#e53935";

    // Update detectors
    for (const [key, val] of Object.entries(detectors)) {
      if (!detectorBars[key]) {
        createDetectorBar(key, val);
      }
      const v = Math.min(val * 100, 100);
      detectorBars[key].bar.style.width = v + "%";
      detectorBars[key].value.textContent = v.toFixed(1) + "%";
      detectorBars[key].bar.style.backgroundColor =
        v < 30 ? "#4caf50" : v < 60 ? "#ffb300" : "#e53935";
    }

    // Alert area
    if (data.alert && data.alert.active) {
      alertArea.style.display = "block";
      alertArea.textContent = "⚠️ ALERT: " + data.alert.message;
    } else if (conf > 5) {
      alertArea.style.display = "block";
      alertArea.textContent =
        "⚠️ Suspicious Activity Detected (" + conf.toFixed(1) + "%)";
    } else {
      alertArea.style.display = "none";
    }
  }

  // manual refresh
  refreshBtn.addEventListener("click", fetchStatus);

  // periodic refresh
  setInterval(fetchStatus, 3000);

  // existing form submit logic (unchanged)
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      FILES_MODIFIED_THRESHOLD: parseInt(
        document.getElementById("FILES_MODIFIED_THRESHOLD").value,
        10
      ),
      TIME_WINDOW_SECONDS: parseInt(
        document.getElementById("TIME_WINDOW_SECONDS").value,
        10
      ),
      BYTES_WRITTEN_THRESHOLD: parseInt(
        document.getElementById("BYTES_WRITTEN_THRESHOLD").value,
        10
      ),
      RENAMES_THRESHOLD: parseInt(
        document.getElementById("RENAMES_THRESHOLD").value,
        10
      ),
      ENTROPY_THRESHOLD: parseFloat(
        document.getElementById("ENTROPY_THRESHOLD").value
      ),
    };

    try {
      const res = await fetch("http://127.0.0.1:8000/set_rates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      statusJson.textContent = "Rates updated: " + JSON.stringify(json);
    } catch (err) {
      statusJson.textContent = "Error updating rates: " + err;
    }
  });

  fetchStatus();
});
