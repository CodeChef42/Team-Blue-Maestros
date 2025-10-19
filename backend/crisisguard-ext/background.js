// background.js
// Service worker for CrisisGuard extension
// Handles WebSocket to agent and shows notifications

const AGENT_WS = "ws://127.0.0.1:8000/ws";
const AGENT_STATUS_URL = "http://127.0.0.1:8000/status";

let ws = null;
let reconnectTimer = null;
const RECONNECT_DELAY_MS = 2000;
const KEEPALIVE_PING_MS = 15000;

// Simple exponential backoff with cap
let backoff = 1;

async function createNotification(title, message, id = null) {
  const notifId = id || "cg-notif-" + Date.now();
  try {
    if (typeof chrome !== "undefined" && chrome.notifications) {
      chrome.notifications.create(notifId, {
        type: "basic",
        title,
        message,
        iconUrl: "icons/icon-48.png",
      });
    } else if (typeof browser !== "undefined" && browser.notifications) {
      browser.notifications.create({
        type: "basic",
        title,
        message,
        iconUrl: browser.runtime.getURL("icons/icon-48.png"),
      });
    } else {
      console.log("[CrisisGuard] Notification:", title, message);
    }
  } catch (e) {
    console.error("Notification error", e);
  }
}

function log(...args) {
  console.log("[CrisisGuard ext]", ...args);
}

// parse possible JSON message and return object or null
function tryParseJson(s) {
  try {
    return JSON.parse(s);
  } catch (e) {
    return null;
  }
}

function handleWsMessage(evt) {
  // Server may send JSON or text. We expect an object {type:"alert", payload: {...}}
  let data = evt.data;
  const parsed = tryParseJson(data);
  if (parsed && parsed.type === "alert") {
    const payload = parsed.payload || parsed;
    // Build a friendly message
    const conf = payload.confidence
      ? parseFloat(payload.confidence).toFixed(2)
      : "unknown";
    const message = `Possible ransomware detected (confidence ${conf}). Open CrisisGuard to inspect.`;
    log("Received alert", payload);
    createNotification("CrisisGuard Alert", message);
    // Optionally store last alert for popup UI
    if (typeof chrome !== "undefined" && chrome.storage) {
      chrome.storage.local.set({ last_alert: payload });
    } else if (typeof browser !== "undefined") {
      browser.storage.local.set({ last_alert: payload });
    }
  } else {
    // handle ping/pong or other messages — log for debugging
    log("WS msg (raw):", data);
  }
}

function openWebSocket() {
  try {
    log("Opening WebSocket ->", AGENT_WS);
    ws = new WebSocket(AGENT_WS);

    ws.onopen = () => {
      log("WebSocket connected");
      backoff = 1;
      // send periodic ping to keep service worker active (best-effort)
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send("extension:hello");
      }
      schedulePing();
    };

    ws.onmessage = (evt) => {
      handleWsMessage(evt);
    };

    ws.onclose = (evt) => {
      log("WebSocket closed", evt.reason || evt.code);
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.error("WebSocket error", err);
      try {
        ws.close();
      } catch (e) {}
      scheduleReconnect();
    };
  } catch (e) {
    console.error("Failed to open WebSocket", e);
    scheduleReconnect();
  }
}

function schedulePing() {
  // Keepalive: send periodic small message if connection open
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  try {
    ws.send(JSON.stringify({ type: "ping", t: Date.now() }));
  } catch (e) {
    console.warn("ping failed", e);
  }
  setTimeout(schedulePing, KEEPALIVE_PING_MS);
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  const delay = Math.min(30000, RECONNECT_DELAY_MS * backoff);
  log(`Scheduling reconnect in ${delay} ms`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    backoff = Math.min(backoff * 2, 16);
    openWebSocket();
  }, delay);
}

// exposed: send rates to agent
async function setRatesToAgent(ratesObj) {
  try {
    const res = await fetch("http://127.0.0.1:8000/set_rates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ratesObj),
    });
    if (!res.ok) {
      const text = await res.text();
      log("Set rates failed:", res.status, text);
      createNotification(
        "CrisisGuard",
        "Failed to update rates: " + res.status
      );
      return { ok: false, status: res.status, body: text };
    }
    const json = await res.json();
    log("Rates updated:", json);
    createNotification("CrisisGuard", "Rates updated successfully.");
    return { ok: true, body: json };
  } catch (e) {
    console.error("Error sending rates", e);
    createNotification(
      "CrisisGuard",
      "Failed to reach local agent. Is it running?"
    );
    return { ok: false, error: String(e) };
  }
}

// message passing from popup
// For MV3 service worker we use chrome.runtime.onMessage
if (
  typeof chrome !== "undefined" &&
  chrome.runtime &&
  chrome.runtime.onMessage
) {
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === "set_rates") {
      setRatesToAgent(msg.payload)
        .then((resp) => sendResponse(resp))
        .catch((e) => sendResponse({ ok: false, error: String(e) }));
      // indicate we will respond async
      return true;
    } else if (msg && msg.type === "fetch_status") {
      fetch("http://127.0.0.1:8000/status")
        .then((r) => r.json())
        .then((j) => sendResponse({ ok: true, body: j }))
        .catch((e) => sendResponse({ ok: false, error: String(e) }));
      return true;
    }
    // otherwise ignore
  });
} else if (
  typeof browser !== "undefined" &&
  browser.runtime &&
  browser.runtime.onMessage
) {
  browser.runtime.onMessage.addListener((msg) => {
    if (msg && msg.type === "set_rates") {
      return setRatesToAgent(msg.payload);
    } else if (msg && msg.type === "fetch_status") {
      return fetch("http://127.0.0.1:8000/status").then((r) => r.json());
    }
  });
}

// Start WebSocket when service worker loads
openWebSocket();

// Service worker lifecycle note: it may be suspended by browser. WebSocket will reconnect when worker restarts.
// Keep logs visible in chrome://extensions -> Service worker background page (Inspect views).
