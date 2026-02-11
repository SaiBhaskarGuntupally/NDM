const CALL_POST_URL = "http://127.0.0.1:8787/incoming_call";
const LOG_PREFIX = "[VoiceLookup]";

console.log(LOG_PREFIX, "service worker loaded");

// Load keep-alive module (additive, feature-flagged)
try {
  importScripts("keep_voice_alive.js");
} catch (e) {
  console.warn(
    LOG_PREFIX,
    "failed to import keep_voice_alive module",
    e?.message || e,
  );
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "incoming_call") return;

  console.log(LOG_PREFIX, "incoming_call message", sender?.url || "");

  const payload = message.payload;

  fetch(CALL_POST_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
    .then(async (res) => {
      if (!res.ok) {
        console.warn(LOG_PREFIX, "POST failed", res.status);
        sendResponse({ ok: false, status: res.status });
        return;
      }
      const data = await res.json().catch(() => ({}));
      sendResponse({ ok: true, status: res.status, data });
    })
    .catch((err) => {
      console.warn(LOG_PREFIX, "POST error", err?.message || err);
      sendResponse({ ok: false, error: err?.message || String(err) });
    });

  return true;
});
