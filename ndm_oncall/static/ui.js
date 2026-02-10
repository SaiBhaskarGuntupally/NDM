let currentPhoneDigits = null;
let currentCallId = null;
let toastTimer = null;
let emailRefreshTimer = null;
// Preserve Gmail results to avoid race-condition clears after refreshes.
let currentGmailResults = null;
let currentGmailPhone = null;

const statusEl = document.getElementById("status");
const callerInfoEl = document.getElementById("callerInfo");
const recentCallsEl = document.getElementById("recentCalls");
const notesEl = document.getElementById("notes");
const noteInput = document.getElementById("noteInput");
const saveNoteBtn = document.getElementById("saveNote");
const jdTitleEl = document.getElementById("jdTitle");
const jdTextEl = document.getElementById("jdText");
const resumeMatchEl = document.getElementById("resumeMatch");
const talkTrackEl = document.getElementById("talkTrack");
const recentCallsListEl = document.getElementById("recentCallsList");
const emailsRecentListEl = document.getElementById("emailsRecentList");
const emailsRelatedListEl = document.getElementById("emailsRelatedList");
const emailsRecentEl = document.getElementById("emailsRecent");
const emailsRelatedEl = document.getElementById("emailsRelated");
const stopRecordingBtn = document.getElementById("stopRecording");
const toastEl = document.getElementById("toast");
const toastCloseBtn = document.getElementById("toastClose");

// KIOSK MODE
let isKioskMode = false;

function getTauriInvoke() {
  return window.__TAURI__?.invoke || null;
}

async function enterKioskMode() {
  const invoke = getTauriInvoke();
  if (!invoke) return;
  await invoke("enter_kiosk");
  isKioskMode = true;
}

async function exitKioskMode() {
  const invoke = getTauriInvoke();
  if (!invoke) return;
  await invoke("exit_kiosk");
  isKioskMode = false;
}

stopRecordingBtn.disabled = true;
stopRecordingBtn.style.display = "none";

function setActiveTab(tab) {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".tab-content").forEach((el) => {
    el.classList.toggle("active", el.id === `tab-${tab}`);
  });
}

function formatPhoneDigits(digits) {
  if (!digits) return "—";
  const cleaned = String(digits).replace(/\D/g, "");
  if (cleaned.length === 10) {
    return `+1-${cleaned.slice(0, 3)}-${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  }
  if (cleaned.length === 11 && cleaned.startsWith("1")) {
    return `+1-${cleaned.slice(1, 4)}-${cleaned.slice(4, 7)}-${cleaned.slice(7)}`;
  }
  return digits;
}

function formatTimestamp(isoString) {
  if (!isoString) return "";
  const dt = new Date(isoString);
  if (Number.isNaN(dt.getTime())) return isoString;
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(dt);
}

function envelopeIcon(color) {
  return `
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="4" width="20" height="16" rx="3" stroke="${color}" stroke-width="1.6" />
      <path d="M4 7.5L12 13.5L20 7.5" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `;
}

function buildGmailOpenUrl({
  gmailMessageId,
  rfcMessageId,
  mailboxEmail,
  accountIndex,
}) {
  const base = "https://mail.google.com/mail";
  const authUser = mailboxEmail
    ? `?authuser=${encodeURIComponent(mailboxEmail)}`
    : "";
  const accountPath =
    !authUser && accountIndex !== "" && accountIndex != null
      ? `/u/${encodeURIComponent(accountIndex)}`
      : "";

  if (gmailMessageId) {
    const query = `#all/${encodeURIComponent(gmailMessageId)}`;
    return `${base}${accountPath}${authUser}${query}`;
  }

  if (rfcMessageId) {
    const normalized = String(rfcMessageId).trim().replace(/^<|>$/g, "");
    const query = `#search/rfc822msgid:${encodeURIComponent(normalized)}`;
    return `${base}${accountPath}${authUser}${query}`;
  }

  return "";
}

function renderCaller(info) {
  const number = formatPhoneDigits(info.phone_digits || "");
  // Name will be set dynamically later
  callerInfoEl.innerHTML = `
    <div class="caller-dash">—</div>
    <div class="caller-number">${number}</div>
    <div class="caller-subtitle">—</div>
    <div class="caller-details">
      <div class="caller-detail-line" id="callerName">—</div>
      <div class="caller-detail-line" id="callerCompany">—</div>
      <div class="caller-detail-line" id="callerTitle">—</div>
    </div>
    <div class="caller-meta" id="callerMeta"></div>
  `;
  updateCallerSubtitle(false);
}

function updateCallerSubtitle(hasEmails) {
  const subtitle = callerInfoEl.querySelector(".caller-subtitle");
  if (!subtitle) return;
  if (hasEmails) {
    subtitle.textContent = "Machaa, number dorikindi.";
    subtitle.style.color = "#00FF00";
    subtitle.style.textShadow = "0 0 8px #00FF00, 0 0 16px #00FF00";
  } else {
    subtitle.textContent = "Machaa, em dorakala";
    subtitle.style.color = "#FF3333";
    subtitle.style.textShadow = "0 0 8px #FF3333, 0 0 16px #FF3333";
  }
}

function setSeenBadge(isSeen) {
  // Removed: badge logic, no longer needed
}

function renderRecentCalls(items) {
  recentCallsEl.innerHTML = "";
  if (!items || items.length === 0) {
    recentCallsEl.innerHTML = "Evaru call cheyyaledu<br />machaa...";
    return;
  }
  recentCallsListEl.innerHTML = "";
  items.slice(0, 3).forEach((call) => {
    const div = document.createElement("div");
    div.className = "email-row";
    const tsLabel = formatTimestamp(call.ts_start);
    div.innerHTML = `
      <div class="email-icon">${envelopeIcon("#FFC83D")}</div>
      <div>
        <div class="email-title">${formatPhoneDigits(call.phone_digits)}</div>
        <div class="email-sub">recording coming soon...</div>
      </div>
      <div class="email-time">${tsLabel}</div>
    `;
    div.addEventListener("click", () => loadWorkspace(call.phone_digits));
    recentCallsListEl.appendChild(div);
  });
}

function renderNotes(items) {
  notesEl.innerHTML = "";
  if (!items || items.length === 0) return;
  items.forEach((note) => {
    const div = document.createElement("div");
    div.className = "note-item";
    div.innerHTML = `<div>${note.ts}</div><div>${note.note_preview || ""}</div>`;
    notesEl.appendChild(div);
  });
}

function renderOpportunity(op) {
  if (!talkTrackEl) return;
  if (!op) {
    talkTrackEl.textContent = "No talk track yet.";
    return;
  }
  talkTrackEl.textContent = op.talk_track_text || "No talk track yet.";
}

async function applyProfile(phoneDigits) {
  if (!window.ProfileStore?.loadProfile) {
    console.warn("[NDM] ProfileStore.loadProfile not available");
    return;
  }
  try {
    const profile = await window.ProfileStore.loadProfile(phoneDigits, {
      baseUrl: window.__PROFILE_API_BASE__ || "",
    });
    console.log("[NDM] Loaded profile for", phoneDigits, profile);
    if (window.ProfileStore?.renderOnCall) {
      window.ProfileStore.renderOnCall(profile);
    }
  } catch (err) {
    console.error("[NDM] Failed to load profile:", err);
  }
}

function renderEmails(items) {
  emailsRecentEl.innerHTML = "";
  emailsRelatedEl.innerHTML = "";
  updateCallerSubtitle(!!(items && items.length));

  if (!items || items.length === 0) {
    emailsRecentEl.innerHTML =
      '<div class="empty-text">No related emails.</div>';
    emailsRelatedEl.innerHTML =
      '<div class="empty-text">No related emails.</div>';
    return;
  }

  const recent = items.slice(0, 3);
  const related = items.slice(3, 6);

  recent.forEach((email) => {
    const sender = email.from || email.from_addr || "Unknown";
    const subject = email.subject || "(no subject)";
    const date = email.date || "";
    const link =
      buildGmailOpenUrl({
        gmailMessageId: email.gmail_message_id || email.gmailMessageId,
        rfcMessageId: email.rfc_message_id || email.rfcMessageId,
        mailboxEmail: email.mailbox_email || email.mailboxEmail,
        accountIndex: email.account_index || email.accountIndex,
      }) ||
      email.link ||
      email.gmail_link ||
      "";
    const div = document.createElement("div");
    div.className = "email-row";
    div.innerHTML = `
      <div class="email-icon">${envelopeIcon("#FFC83D")}</div>
      <div>
        <div class="email-title">${sender}</div>
        <div class="email-sub">${subject}</div>
      </div>
      <div class="email-time">${date}</div>
    `;
    if (link) {
      div.addEventListener("click", () =>
        window.open(link, "_blank", "noopener,noreferrer"),
      );
    }
    emailsRecentEl.appendChild(div);
  });

  if (related.length === 0) {
    emailsRelatedEl.innerHTML =
      '<div class="empty-text">No related emails.</div>';
    return;
  }

  related.forEach((email) => {
    const sender = email.from || email.from_addr || "Unknown";
    const subject = email.subject || "(no subject)";
    const date = email.date || "";
    const link =
      buildGmailOpenUrl({
        gmailMessageId: email.gmail_message_id || email.gmailMessageId,
        rfcMessageId: email.rfc_message_id || email.rfcMessageId,
        mailboxEmail: email.mailbox_email || email.mailboxEmail,
        accountIndex: email.account_index || email.accountIndex,
      }) ||
      email.link ||
      email.gmail_link ||
      "";
    const div = document.createElement("div");
    div.className = "email-row";
    div.innerHTML = `
      <div class="email-icon">${envelopeIcon("#3AFFC3")}</div>
      <div>
        <div class="email-title">${sender}</div>
        <div class="email-sub">${subject}</div>
      </div>
      <div class="email-time">${date}</div>
    `;
    if (link) {
      div.addEventListener("click", () =>
        window.open(link, "_blank", "noopener,noreferrer"),
      );
    }
    emailsRelatedEl.appendChild(div);
  });
}

function renderGmailFromState() {
  if (currentGmailResults && currentGmailResults.length > 0) {
    renderEmails(currentGmailResults);
    return true;
  }
  return false;
}

async function refreshEmailsFromWorkspace() {
  if (!currentPhoneDigits) return;
  if (currentGmailPhone === currentPhoneDigits && renderGmailFromState()) {
    return;
  }
  const res = await fetch(`/workspace/${currentPhoneDigits}`);
  const data = await res.json();
  if (!currentGmailResults || currentGmailPhone !== currentPhoneDigits) {
    renderEmails(data.emails || []);
  }
  setSeenBadge((data.emails || []).length > 0);
}

function showToast(phoneDigits) {
  if (!toastEl) return;
  const formatted = formatPhoneDigits(phoneDigits || "+1-205-240-3989");
  const textEls = toastEl.querySelectorAll(".toast-text div");
  if (textEls.length >= 2) {
    textEls[1].textContent = `${formatted}. Gmail lo dorikindi ✉️`;
  }
  toastEl.classList.remove("hidden");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.add("hidden"), 4000);
}

function hideToast() {
  if (!toastEl) return;
  toastEl.classList.add("hidden");
}

async function loadWorkspace(phoneDigits) {
  const res = await fetch(`/workspace/${phoneDigits}`);
  const data = await res.json();
  currentPhoneDigits = phoneDigits;
  currentCallId = data.current_call_id || null;
  stopRecordingBtn.disabled = !data.recording_active;
  renderCaller({ phone_digits: phoneDigits, display_name: data.display_name });
  setSeenBadge(false);
  await fetchCallHistory(phoneDigits);
  await applyProfile(phoneDigits);
  renderOpportunity(data.opportunity || null);
  if (!renderGmailFromState()) {
    renderEmails(data.emails || []);
  }
  statusEl.textContent = `Workspace ready: ${phoneDigits}`;
}

async function fetchCallHistory(phoneDigits) {
  if (!phoneDigits) {
    renderRecentCalls([]);
    return;
  }
  const res = await fetch(
    `/call_history?digits=${encodeURIComponent(phoneDigits)}`,
  );
  const data = await res.json();
  renderRecentCalls(data.calls || []);
}

async function saveNote() {
  const text = noteInput.value.trim();
  if (!text || !currentPhoneDigits) return;
  if (window.ProfileStore?.saveNote) {
    await window.ProfileStore.saveNote(currentPhoneDigits, text, {
      baseUrl: window.__PROFILE_API_BASE__ || "",
    });
    await applyProfile(currentPhoneDigits);
  }
  noteInput.value = "";
}

saveNoteBtn.addEventListener("click", saveNote);

noteInput.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "Enter") saveNote();
});

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
});

toastCloseBtn?.addEventListener("click", hideToast);

// KIOSK MODE
document.addEventListener("keydown", (event) => {
  if (event.key === "F11") {
    event.preventDefault();
    if (isKioskMode) {
      exitKioskMode();
    } else {
      enterKioskMode();
    }
  }
});

const evtSource = new EventSource("/events");

evtSource.addEventListener("incoming_call_workspace", (event) => {
  const data = JSON.parse(event.data);
  const isNewCall = data.phone_digits !== currentPhoneDigits;
  currentPhoneDigits = data.phone_digits;
  currentCallId = data.call_id;
  if (isNewCall) {
    currentGmailResults = null;
    currentGmailPhone = null;
  }
  renderCaller(data);
  setSeenBadge(false);
  fetchCallHistory(data.phone_digits);
  applyProfile(data.phone_digits);
  renderOpportunity(data.opportunity || null);
  if (!renderGmailFromState()) {
    renderEmails(data.emails || []);
  }
  stopRecordingBtn.disabled = !data.recording_active;
  statusEl.textContent = `Incoming call: ${data.phone_digits}`;
  showToast(data.phone_digits);

  if (emailRefreshTimer) clearTimeout(emailRefreshTimer);
  emailRefreshTimer = setTimeout(refreshEmailsFromWorkspace, 1200);
});

evtSource.addEventListener("gmail_results_ready", (event) => {
  const data = JSON.parse(event.data);
  if (data.phone_digits !== currentPhoneDigits) return;
  if (data.emails && data.emails.length > 0) {
    currentGmailResults = data.emails || [];
    currentGmailPhone = data.phone_digits;
    renderEmails(currentGmailResults);
    setSeenBadge(true);
  } else {
    refreshEmailsFromWorkspace();
  }
  statusEl.textContent = `Gmail results ready: ${data.phone_digits}`;
});

function initWarRoomUI() {
  if (!warRoomButton || !window.WarRoomManager) return;

  const helperKey = "ndm_hide_war_room_helper";
  let popupBlocked = false;
  let helperShown = false;

  function setHelperVisibility(visible) {
    if (!warRoomHelperEl) return;
    warRoomHelperEl.classList.toggle("hidden", !visible);
  }

  function showHelperIfNeeded() {
    if (!warRoomHelperEl || helperShown) return;
    const isHidden = localStorage.getItem(helperKey) === "true";
    if (isHidden) return;
    helperShown = true;
    setHelperVisibility(true);
  }

  function updateHelperToggle() {
    if (!warRoomHelperToggle) return;
    const isHidden = localStorage.getItem(helperKey) === "true";
    warRoomHelperToggle.checked = isHidden;
  }

  function setPopupBlockedState(blocked) {
    popupBlocked = blocked;
    if (!warRoomPopupBlockedEl) return;
    warRoomPopupBlockedEl.classList.toggle("hidden", !blocked);
  }

  function setStatusState(state, missing) {
    if (!warRoomStatusEl || !warRoomButton) return;
    warRoomStatusEl.classList.remove(
      "status-active",
      "status-inactive",
      "status-incomplete",
    );
    if (state === "active") {
      warRoomStatusEl.textContent = "WAR ROOM ACTIVE";
      warRoomStatusEl.classList.add("status-active");
      warRoomButton.classList.remove("is-flashing");
    } else if (state === "incomplete") {
      warRoomStatusEl.textContent = "WAR ROOM INCOMPLETE";
      warRoomStatusEl.classList.add("status-incomplete");
      warRoomButton.classList.add("is-flashing");
    } else {
      warRoomStatusEl.textContent = "WAR ROOM INACTIVE";
      warRoomStatusEl.classList.add("status-inactive");
      warRoomButton.classList.add("is-flashing");
    }

    if (!warRoomIncompleteEl) return;
    const showIncomplete = state === "incomplete";
    warRoomIncompleteEl.classList.toggle("hidden", !showIncomplete);
    if (!showIncomplete || !warRoomMissingTextEl) return;
    warRoomMissingTextEl.textContent = missing || "";
  }

  function updateMissingButtons(status) {
    if (reopenResumeBtn) {
      reopenResumeBtn.style.display = status.resumeOpen
        ? "none"
        : "inline-flex";
    }
    if (reopenCheatsBtn) {
      reopenCheatsBtn.style.display = status.cheatsOpen
        ? "none"
        : "inline-flex";
    }
  }

  function buildMissingText(status) {
    if (!status.resumeOpen && !status.cheatsOpen) {
      return "Resume and Cheats windows are missing.";
    }
    if (!status.resumeOpen) return "Resume window is missing.";
    if (!status.cheatsOpen) return "Cheats window is missing.";
    return "";
  }

  function refreshStatus() {
    const status = window.WarRoomManager.getWindowStatus();
    const bothOpen = status.resumeOpen && status.cheatsOpen;
    const anyOpen = status.resumeOpen || status.cheatsOpen;
    if (bothOpen) {
      setStatusState("active");
      setPopupBlockedState(false);
      showHelperIfNeeded();
    } else if (anyOpen) {
      setStatusState("incomplete", buildMissingText(status));
    } else {
      setStatusState("inactive");
    }
    updateMissingButtons(status);
    return status;
  }

  warRoomButton.addEventListener("click", () => {
    const result = window.WarRoomManager.openWarRoom();
    if (result.popupBlocked) {
      setPopupBlockedState(true);
    }
    refreshStatus();
  });

  reopenResumeBtn?.addEventListener("click", () => {
    window.WarRoomManager.openResumeWindow();
    refreshStatus();
  });

  reopenCheatsBtn?.addEventListener("click", () => {
    window.WarRoomManager.openCheatWindow();
    refreshStatus();
  });

  manualResumeBtn?.addEventListener("click", () => {
    const ref = window.WarRoomManager.openResumeWindow();
    if (ref) setPopupBlockedState(false);
    refreshStatus();
  });

  manualCheatsBtn?.addEventListener("click", () => {
    const ref = window.WarRoomManager.openCheatWindow();
    if (ref) setPopupBlockedState(false);
    refreshStatus();
  });

  warRoomHelperToggle?.addEventListener("change", (event) => {
    const isHidden = event.target.checked;
    localStorage.setItem(helperKey, isHidden ? "true" : "false");
    if (isHidden) setHelperVisibility(false);
  });

  updateHelperToggle();
  refreshStatus();
  setInterval(refreshStatus, 1500);
}
