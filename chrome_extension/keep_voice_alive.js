/* keep_voice_alive.js
   Minimal MV3 keep-alive for voice.google.com
   Feature-flagged (default OFF)
   Uses chrome.alarms + chrome.scripting to run a HEAD/GET same-origin request in voice tab
*/

const KVA_LOG = "[KeepVoiceAlive]";
const KVA_ALARM = "VOICE_KEEPALIVE";
const KVA_STORAGE_KEY = "voice_keepalive_enabled";
const KVA_PERIOD_MINUTES = 1; // aligns with requirement >=45s (1 minute)

console.log(KVA_LOG, "module loaded");

async function isFeatureEnabled() {
  return new Promise((res) => {
    chrome.storage.local.get([KVA_STORAGE_KEY], (items) => {
      res(Boolean(items[KVA_STORAGE_KEY]));
    });
  });
}

function enableFeature() {
  console.log(KVA_LOG, "enableFeature");
  // request keep-awake (best-effort)
  try {
    if (chrome.power && chrome.power.requestKeepAwake) {
      chrome.power.requestKeepAwake("system");
      console.log(KVA_LOG, "requested keepAwake(system)");
    }
  } catch (e) {
    console.warn(KVA_LOG, "power.requestKeepAwake failed", e?.message || e);
  }

  chrome.alarms.create(KVA_ALARM, { periodInMinutes: KVA_PERIOD_MINUTES });
}

function disableFeature() {
  console.log(KVA_LOG, "disableFeature");
  try {
    if (chrome.power && chrome.power.releaseKeepAwake) {
      chrome.power.releaseKeepAwake();
      console.log(KVA_LOG, "released keepAwake");
    }
  } catch (e) {
    console.warn(KVA_LOG, "power.releaseKeepAwake failed", e?.message || e);
  }
  chrome.alarms.clear(KVA_ALARM);
}

async function heartbeatForTab(tabId) {
  try {
    // Execute a small script in page context that issues a HEAD GET to same origin
    const result = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        try {
          // Skip if document is not fully loaded
          if (
            document.readyState !== "complete" &&
            document.readyState !== "interactive"
          )
            return { ok: false, reason: "not-ready" };

          // Lightweight detection for active call UI - conservative selectors, no UI changes
          const callSelector =
            'button[aria-label*="Hang up"], button[aria-label*="End call"], .call-active';
          if (document.querySelector(callSelector))
            return { ok: false, reason: "call-in-progress" };

          // perform a HEAD request to same origin. Use keepalive and credentials included.
          const url = location.origin;
          fetch(url, {
            method: "HEAD",
            cache: "no-store",
            credentials: "include",
            keepalive: true,
          }).catch(() => {});
          return { ok: true };
        } catch (e) {
          return { ok: false, error: String(e) };
        }
      },
    });

    // result is an array of InjectionResult
    if (Array.isArray(result) && result.length > 0) {
      const res = result[0]?.result;
      console.log(KVA_LOG, "tab", tabId, "heartbeat result", res);
      return res;
    }
  } catch (err) {
    console.warn(KVA_LOG, "heartbeatForTab failed", err?.message || err);
  }
  return null;
}

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm?.name !== KVA_ALARM) return;
  console.log(KVA_LOG, "alarm fired");
  try {
    const tabs = await new Promise((res) =>
      chrome.tabs.query({ url: "*://voice.google.com/*" }, res),
    );
    if (!tabs || tabs.length === 0) return;
    for (const tab of tabs) {
      if (tab.discarded) {
        console.log(KVA_LOG, "tab discarded, skipping", tab.id);
        continue;
      }
      if (!tab.id) continue;
      // skip tabs that are not complete (loading) to avoid interfering
      if (tab.status && tab.status !== "complete") {
        console.log(KVA_LOG, "tab not complete, skipping", tab.id, tab.status);
        continue;
      }
      heartbeatForTab(tab.id);
    }
  } catch (e) {
    console.warn(KVA_LOG, "alarms handler error", e?.message || e);
  }
});

// Listen for storage changes to toggle feature dynamically
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (KVA_STORAGE_KEY in changes) {
    const nv = changes[KVA_STORAGE_KEY].newValue;
    if (nv) enableFeature();
    else disableFeature();
  }
});

// Expose a helper on runtime for tests / quick toggle
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || !msg.type) return;
  if (msg.type === "kva_toggle") {
    const enable = Boolean(msg.enable);
    chrome.storage.local.set({ [KVA_STORAGE_KEY]: enable }, () => {
      sendResponse({ ok: true, enabled: enable });
    });
    return true; // async
  }
});

// Initialize from storage
(async () => {
  const enabled = await isFeatureEnabled();
  console.log(KVA_LOG, "initial enabled?", enabled);
  if (enabled) enableFeature();
})();
