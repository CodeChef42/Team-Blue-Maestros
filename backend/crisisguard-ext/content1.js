(() => {
  console.log("[CrisisGuard] Scanning page links...");

  const API_URL = "http://localhost:8080/scan";
  const links = Array.from(document.querySelectorAll("a[href]"));

  if (links.length === 0) {
    console.log("[CrisisGuard] No links found on this page.");
    return;
  }

  console.log(`[CrisisGuard] Found ${links.length} links.`);

  // Tooltip shared by all disabled links
  const tooltip = document.createElement("div");
  tooltip.textContent = "⚠️ Dangerous link — access blocked by CrisisGuard.";
  Object.assign(tooltip.style, {
    position: "fixed",
    background: "#e53935",
    color: "#fff",
    padding: "6px 10px",
    borderRadius: "6px",
    fontSize: "13px",
    whiteSpace: "nowrap",
    display: "none",
    zIndex: "999999",
    boxShadow: "0 2px 6px rgba(0,0,0,0.25)",
    pointerEvents: "none",
    transition: "opacity 0.2s ease",
    opacity: "0",
  });
  document.body.appendChild(tooltip);

  // Function to disable a malicious link
  const disableLink = (link) => {
    link.style.pointerEvents = "auto"; // needed for hover
    link.style.color = "#b0b0b0";
    link.style.textDecoration = "line-through";
    link.style.cursor = "not-allowed";

    const blockEvent = (e) => {
      e.preventDefault();
      e.stopPropagation();
      return false;
    };
    ["click", "mousedown", "mouseup", "contextmenu"].forEach((evt) =>
      link.addEventListener(evt, blockEvent, true)
    );

    link.addEventListener("mouseenter", (e) => {
      tooltip.style.display = "block";
      tooltip.style.opacity = "1";
      tooltip.style.left = e.pageX + 10 + "px";
      tooltip.style.top = e.pageY + 10 + "px";
    });
    link.addEventListener("mousemove", (e) => {
      tooltip.style.left = e.pageX + 10 + "px";
      tooltip.style.top = e.pageY + 10 + "px";
    });
    link.addEventListener("mouseleave", () => {
      tooltip.style.opacity = "0";
      setTimeout(() => (tooltip.style.display = "none"), 200);
    });
  };

  // Asynchronous scanning
  const scanLink = async (link) => {
    const url = link.href;
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });

      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();

      console.log(`[CrisisGuard] Scan result for ${url}: ${data.verdict}`);

      if (data.verdict === "MALICIOUS") {
        disableLink(link);
      }
    } catch (err) {
      console.error(`[CrisisGuard] Error scanning ${url}:`, err);
    }
  };

  // Run scans concurrently but not all at once
  (async () => {
    for (const link of links) {
      await scanLink(link);
    }
  })();
})();
