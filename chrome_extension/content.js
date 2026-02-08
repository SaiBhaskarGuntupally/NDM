(() => {
  const CALL_POST_URL = "http://127.0.0.1:8787/incoming_call";
  const LOG_PREFIX = "[VoiceLookup]";
  const MIN_RESEND_MS = 15000;
  const PAUSE_AFTER_SEND_MS = 3000;
  const BURST_INTERVAL_MS = 50;
  const BURST_DURATION_MS = 2000;
  const FALLBACK_SCAN_MS = 2500;
  const TITLE_EMPTY_RESET_MS = 2000;

  const spacedDigitsRegex = /(\d\s){9,}\d/;

  console.log(LOG_PREFIX, "content script boot", location.href);
  window.addEventListener("error", (event) => {
    console.error(
      LOG_PREFIX,
      "content script error",
      event.error || event.message,
    );
  });

  let lastDigitsSent = "";
  let lastSentAt = 0;
  let scanPausedUntil = 0;
  let burstTimer = null;
  let burstStopTimer = null;
  let burstActive = false;
  let titleObserver = null;
  let subtitleObserver = null;
  let observedTitleEl = null;
  let observedSubtitleEl = null;
  let headerEmptySince = null;
  let lastTitleText = "";

  function digitsOnly(text) {
    return (text || "").replace(/\D/g, "");
  }

  function last10(digits) {
    if (!digits) return "";
    return digits.length >= 10 ? digits.slice(-10) : digits;
  }

  function isValidPhoneDigits(digits) {
    return /^\d{10}$/.test(digits) || /^1\d{10}$/.test(digits);
  }

  function buildVariants(raw) {
    const digits = digitsOnly(raw);
    if (!digits || !isValidPhoneDigits(digits)) {
      return { digits: "", last10: "", variants: [] };
    }

    const l10 = last10(digits);
    const base = new Set();

    if (digits) base.add(digits);
    if (l10) base.add(l10);

    if (l10.length === 10) {
      const area = l10.slice(0, 3);
      const mid = l10.slice(3, 6);
      const last = l10.slice(6);
      base.add(`${area}${mid}${last}`);
      base.add(`${area}-${mid}-${last}`);
      base.add(`(${area}) ${mid}-${last}`);
      base.add(`+1 ${area}-${mid}-${last}`);
      base.add(`+1 (${area}) ${mid}-${last}`);
    }

    return { digits, last10: l10, variants: Array.from(base) };
  }

  function cleanRaw(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function getTitleElement() {
    return document.querySelector(".remote-display-title");
  }

  function getSubtitleElement() {
    return document.querySelector(".remote-display-subtitle");
  }

  function getTitleText() {
    const titleEl = getTitleElement();
    return titleEl ? cleanRaw(titleEl.textContent) : "";
  }

  function getSubtitleText() {
    const subtitleEl = getSubtitleElement();
    return subtitleEl ? cleanRaw(subtitleEl.textContent) : "";
  }

  function tryGrabTitleNumber() {
    const raw = getTitleText();
    const digits = digitsOnly(raw);
    if (!digits || !isValidPhoneDigits(digits)) return "";
    return raw;
  }

  function tryGrabSubtitleNumber() {
    const raw = getSubtitleText();
    const digits = digitsOnly(raw);
    if (!digits || !isValidPhoneDigits(digits)) return "";
    return raw;
  }

  function tryGrabHiddenSpacedDigits() {
    const hiddenEl = document.querySelector(".cdk-visually-hidden");
    if (!hiddenEl) return "";
    const text = hiddenEl.textContent || "";
    const match = text.match(spacedDigitsRegex);
    if (!match) return "";
    return match[0];
  }

  async function postIncomingCall(raw) {
    const { digits, last10: l10, variants } = buildVariants(raw);

    if (!digits) return;

    const now = Date.now();
    if (digits === lastDigitsSent && now - lastSentAt < MIN_RESEND_MS) return;

    lastDigitsSent = digits;
    lastSentAt = now;
    scanPausedUntil = now + PAUSE_AFTER_SEND_MS;

    console.log(LOG_PREFIX, "CALL_FOUND", raw);

    const payload = {
      raw,
      digits,
      last10: l10,
      variants,
    };

    try {
      chrome.runtime.sendMessage(
        { type: "incoming_call", payload },
        (response) => {
          if (chrome.runtime.lastError) {
            console.warn(
              LOG_PREFIX,
              "POST_FAIL",
              chrome.runtime.lastError.message,
            );
            return;
          }

          if (!response?.ok) {
            console.warn(
              LOG_PREFIX,
              "POST_FAIL",
              response?.status || response?.error,
            );
          } else {
            console.log(LOG_PREFIX, "POST_OK");
          }
        },
      );
    } catch (err) {
      console.warn(LOG_PREFIX, "POST_FAIL", err?.message || err);
    }
  }

  function scanAndSend() {
    let raw = tryGrabTitleNumber();
    if (raw) {
      lastTitleText = raw;
    } else {
      raw = tryGrabSubtitleNumber();
    }

    if (!raw) {
      raw = tryGrabHiddenSpacedDigits();
    }

    if (!raw) return;

    postIncomingCall(raw);
    stopBurst();
  }

  function startBurst() {
    if (burstActive) return;
    if (Date.now() < scanPausedUntil) {
      const currentTitle = getTitleText();
      if (currentTitle && currentTitle === lastTitleText) return;
    }
    burstActive = true;
    console.log(LOG_PREFIX, "BURST_START");
    burstTimer = setInterval(scanAndSend, BURST_INTERVAL_MS);
    burstStopTimer = setTimeout(stopBurst, BURST_DURATION_MS);
  }

  function stopBurst() {
    if (!burstActive) return;
    burstActive = false;
    if (burstTimer) clearInterval(burstTimer);
    if (burstStopTimer) clearTimeout(burstStopTimer);
    burstTimer = null;
    burstStopTimer = null;
  }

  function observeTitleElement(el) {
    if (!el || el === observedTitleEl) return;
    if (titleObserver) titleObserver.disconnect();
    observedTitleEl = el;
    titleObserver = new MutationObserver(() => {
      const text = getTitleText();
      if (text) {
        headerEmptySince = null;
        startBurst();
      } else {
        handleEmptyHeader();
      }
    });
    titleObserver.observe(el, {
      characterData: true,
      subtree: true,
      childList: true,
    });
  }

  function observeSubtitleElement(el) {
    if (!el || el === observedSubtitleEl) return;
    if (subtitleObserver) subtitleObserver.disconnect();
    observedSubtitleEl = el;
    subtitleObserver = new MutationObserver(() => {
      const text = getSubtitleText();
      if (text) {
        headerEmptySince = null;
        startBurst();
      } else {
        handleEmptyHeader();
      }
    });
    subtitleObserver.observe(el, {
      characterData: true,
      subtree: true,
      childList: true,
    });
  }

  function handleEmptyHeader() {
    const titleText = getTitleText();
    const subtitleText = getSubtitleText();
    if (titleText || subtitleText) {
      headerEmptySince = null;
      return;
    }
    if (!headerEmptySince) headerEmptySince = Date.now();
    if (Date.now() - headerEmptySince < TITLE_EMPTY_RESET_MS) return;

    stopBurst();
    if (titleObserver) {
      titleObserver.disconnect();
      titleObserver = null;
    }
    if (subtitleObserver) {
      subtitleObserver.disconnect();
      subtitleObserver = null;
    }
    observedTitleEl = null;
    observedSubtitleEl = null;
    headerEmptySince = null;
  }

  function isRelevantNode(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return false;
    if (node.matches?.(".remote-display-title")) return true;
    if (node.matches?.(".remote-display-subtitle")) return true;
    if (node.matches?.(".cdk-visually-hidden")) return true;
    return !!node.querySelector?.(
      ".remote-display-title, .remote-display-subtitle, .cdk-visually-hidden",
    );
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (!mutation.addedNodes || mutation.addedNodes.length === 0) continue;
      for (const node of mutation.addedNodes) {
        if (!isRelevantNode(node)) continue;
        if (node.matches?.(".remote-display-title")) {
          observeTitleElement(node);
        }
        if (node.matches?.(".remote-display-subtitle")) {
          observeSubtitleElement(node);
        }
        const titleEl = node.querySelector?.(".remote-display-title");
        if (titleEl) observeTitleElement(titleEl);
        const subtitleEl = node.querySelector?.(".remote-display-subtitle");
        if (subtitleEl) observeSubtitleElement(subtitleEl);
        startBurst();
        return;
      }
    }
  });

  function start() {
    if (!document.body) {
      setTimeout(start, 500);
      return;
    }

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    setInterval(() => {
      const titleEl = getTitleElement();
      if (titleEl) observeTitleElement(titleEl);
      const subtitleEl = getSubtitleElement();
      if (subtitleEl) observeSubtitleElement(subtitleEl);
      handleEmptyHeader();
      scanAndSend();
    }, FALLBACK_SCAN_MS);

    console.log(LOG_PREFIX, "observer started");
  }

  start();
})();
