import React, { useState, useEffect } from "react";
import MetricBar from "../components/MetricBar";

export default function Popup() {
  const [rates, setRates] = useState({
    FILES_MODIFIED_THRESHOLD: 20,
    TIME_WINDOW_SECONDS: 30,
    BYTES_WRITTEN_THRESHOLD: 100000000,
    RENAMES_THRESHOLD: 10,
    ENTROPY_THRESHOLD: 7.5,
  });

  const [metrics, setMetrics] = useState({
    cpu_usage: 0,
    disk_io_mb: 0,
    confidence: 0,
    alert: { active: false, message: "" },
  });

  const [status, setStatus] = useState("");

  const handleChange = (e) =>
    setRates((prev) => ({
      ...prev,
      [e.target.id]: parseFloat(e.target.value),
    }));

  const fetchStatus = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/status");
      const data = await res.json();
      setMetrics(data);
    } catch (e) {
      console.error(e);
    }
  };

  const sendRates = async (e) => {
    e.preventDefault();
    try {
      await fetch("http://127.0.0.1:8000/set_rates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rates),
      });
      setStatus("✅ Rates updated successfully!");
    } catch {
      setStatus("❌ Failed to update rates.");
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex bg-gray-50 text-sm w-[600px]">
      {/* Left */}
      <div className="flex-1 p-4">
        <h2 className="text-xl font-semibold text-blue-700">CrisisGuard</h2>
        <p className="text-gray-600 mb-3">
          Set local detection thresholds (connected to 127.0.0.1:8000)
        </p>

        <form onSubmit={sendRates} className="space-y-3">
          {Object.entries(rates).map(([key, val]) => (
            <label key={key} className="block">
              <span className="text-xs font-medium">
                {key.replace(/_/g, " ")}:
              </span>
              <input
                id={key}
                type="number"
                value={val}
                onChange={handleChange}
                className="mt-1 w-full border border-gray-300 rounded-md px-2 py-1"
              />
            </label>
          ))}
          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
          >
            Send Rates
          </button>
        </form>

        {status && <p className="text-xs text-green-600 mt-2">{status}</p>}
      </div>

      {/* Right */}
      <div className="w-[220px] bg-white border-l border-gray-200 p-4">
        <h3 className="text-base font-semibold text-blue-600 mb-3">
          Live Metrics
        </h3>

        <MetricBar label="CPU Usage" value={metrics.cpu_usage} suffix="%" />
        <MetricBar label="Disk I/O" value={metrics.disk_io_mb} suffix=" MB/s" />
        <MetricBar
          label="Confidence"
          value={metrics.confidence * 100}
          suffix="%"
          color="bg-orange-500"
        />

        {metrics.alert?.active && (
          <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 rounded-md p-2 mt-3 text-xs">
            ⚠️ {metrics.alert.message}
          </div>
        )}
      </div>
    </div>
  );
}
