const WS_URL = "ws://127.0.0.1:8000/ws";

let ws;

function connect() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => console.log("[CrisisGuard] Connected to agent WS");
  ws.onmessage = (msg) => handleMessage(msg);
  ws.onclose = () => setTimeout(connect, 2000);
}

function handleMessage(msg) {
  try {
    const data = JSON.parse(msg.data);
    if (data.type === "alert") {
      chrome.notifications.create({
        type: "basic",
        title: "🚨 CrisisGuard Alert",
        message:
          data.payload?.message || "Possible ransomware activity detected!",
        iconUrl: "../public/icons/icon-128.png",
      });
    }
  } catch (err) {
    console.error("WS error", err);
  }
}

chrome.runtime.onInstalled.addListener(() => connect());
connect();
