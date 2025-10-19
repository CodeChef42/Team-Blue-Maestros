document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("ratesForm");
  const statusJson = document.getElementById("statusJson");
  const refreshBtn = document.getElementById("refreshStatus");

  // Right panel elements
  const cpuBar = document.getElementById("cpuBar");
  const diskBar = document.getElementById("diskBar");
  const confBar = document.getElementById("confBar");
  const cpuValue = document.getElementById("cpuValue");
  const diskValue = document.getElementById("diskValue");
  const confValue = document.getElementById("confValue");
  const alertArea = document.getElementById("alertArea");

  async function fetchStatus() {
    try {
      const resp = await fetch("http://127.0.0.1:8000/status");
      const data = await resp.json();
      updateUI(data);
    } catch (err) {
      console.error("Error fetching status", err);
    }
  }

  function updateUI(data) {
    statusJson.textContent = JSON.stringify(data, null, 2);

    const cpu = data.cpu_usage || 0;
    const io = data.disk_io_mb || 0;
    const conf = (data.confidence || 0) * 100;

    cpuBar.style.width = Math.min(cpu, 100) + "%";
    cpuValue.textContent = cpu.toFixed(1) + "%";

    diskBar.style.width = Math.min(io * 2, 100) + "%";
    diskValue.textContent = io.toFixed(1) + " MB/s";

    confBar.style.width = Math.min(conf, 100) + "%";
    confValue.textContent = conf.toFixed(1) + "%";

    if (data.alert && data.alert.active) {
      alertArea.style.display = "block";
      alertArea.textContent = "⚠️ ALERT: " + data.alert.message;
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
