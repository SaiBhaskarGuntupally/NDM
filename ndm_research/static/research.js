const input = document.getElementById("searchInput");
const btn = document.getElementById("searchBtn");
const list = document.getElementById("resultsList");
const backBtn = document.getElementById("backToSearch");
const stateIdle = document.getElementById("stateIdle");
const stateResults = document.getElementById("stateResults");
const stateEmpty = document.getElementById("stateEmpty");
const stateAllNumbers = document.getElementById("stateAllNumbers");
const createDigits = document.getElementById("createProfileDigits");
const createBtn = document.getElementById("createProfileBtn");
const allNumbersBtn = document.getElementById("allNumbersBtn");
const allNumbersList = document.getElementById("allNumbersList");
const emptyCard = document.getElementById("emptyStateCard");
const emptyDigits = document.getElementById("emptyDigits");
const emptyCreateBtn = document.getElementById("emptyCreateBtn");
const vendorName = document.getElementById("vendorName");
const vendorPhone = document.getElementById("vendorPhone");
const vendorNameInput = document.getElementById("vendorNameInput");
const vendorCompanyInput = document.getElementById("vendorCompanyInput");
const vendorTitleInput = document.getElementById("vendorTitleInput");
const saveProfileBtn = document.getElementById("saveProfile");
const jdText = document.getElementById("jdText");
const saveJd = document.getElementById("saveJd");
const resumeText = document.getElementById("resumeText");
const saveResume = document.getElementById("saveResume");
const newNoteText = document.getElementById("newNoteText");
const addNoteBtn = document.getElementById("addNoteBtn");
const notesList = document.getElementById("notesList");
const summaryLastCall = document.getElementById("summaryLastCall");
const summaryCount = document.getElementById("summaryCount");
const emailsList = document.getElementById("emailsList");
const recordingsList = document.getElementById("recordingsList");

const workspacePayload = window.__WORKSPACE__ || null;
let activeDigits = workspacePayload?.phone_digits || "";
let latestCallId = workspacePayload?.latest_call_id || null;
let allNumbersLoaded = false;

function formatPhone(digits) {
  if (!digits) return "--";
  const cleaned = String(digits).replace(/\D/g, "");
  if (cleaned.length === 10) {
    return `+1-${cleaned.slice(0, 3)}-${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  }
  return cleaned;
}

function formatTimestamp(iso) {
  if (!iso) return "--";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(dt);
}

function normalizeQuery(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (!digits) return null;
  if (digits.length === 11 && digits.startsWith("1")) {
    const last10 = digits.slice(1);
    return { mode: "last10", last10, last4: last10.slice(-4) };
  }
  if (digits.length >= 10) {
    const last10 = digits.slice(-10);
    return { mode: "last10", last10, last4: last10.slice(-4) };
  }
  if (digits.length === 4) {
    return { mode: "last4", last4: digits };
  }
  return { mode: "partial", partial: digits };
}

function setEmpty(el, message) {
  if (!el) return;
  el.innerHTML = "";
  const div = document.createElement("div");
  div.className = "empty-state";
  div.textContent = message;
  el.appendChild(div);
}

async function fetchJson(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

function setState(state, payload) {
  if (!stateIdle || !stateResults || !stateEmpty) return;
  stateIdle.classList.add("hidden");
  stateResults.classList.add("hidden");
  stateEmpty.classList.add("hidden");
  stateAllNumbers?.classList.add("hidden");
  stateEmpty.dataset.phoneDigits = "";

  if (state === "idle") {
    stateIdle.classList.remove("hidden");
    return;
  }

  if (state === "results") {
    stateResults.classList.remove("hidden");
    return;
  }

  if (state === "all") {
    stateAllNumbers?.classList.remove("hidden");
    return;
  }

  if (state === "empty") {
    stateEmpty.classList.remove("hidden");
    if (payload?.digits && createDigits) {
      createDigits.textContent = formatPhone(payload.digits);
      stateEmpty.dataset.phoneDigits = payload.digits;
    }
  }
}

async function loadAllNumbers() {
  if (!allNumbersList) return;
  setState("all");
  if (!allNumbersLoaded) {
    setEmpty(allNumbersList, "Loading numbers...");
    try {
      const data = await fetchJson("/research/numbers");
      const results = data.results || [];
      allNumbersList.innerHTML = "";
      if (results.length === 0) {
        setEmpty(allNumbersList, "No numbers found.");
      } else {
        results.forEach((item) => renderResultRow(item, allNumbersList));
      }
      allNumbersLoaded = true;
    } catch (err) {
      setEmpty(allNumbersList, "Failed to load numbers.");
    }
  }
}

function renderResultRow(item, container) {
  const row = document.createElement("div");
  row.className = "result-row";
  const info = document.createElement("div");
  info.className = "result-info";
  const number = document.createElement("div");
  number.className = "result-number";
  number.textContent = item.formatted || formatPhone(item.phone_digits);
  const meta = document.createElement("div");
  meta.className = "result-meta";
  const vendor = item.vendor_name ? ` · ${item.vendor_name}` : "";
  meta.textContent = `Last call: ${formatTimestamp(item.last_call_ts)} · Calls: ${item.call_count || 0}${vendor}`;
  info.appendChild(number);
  info.appendChild(meta);

  const openBtn = document.createElement("button");
  openBtn.className = "action-btn";
  openBtn.textContent = "Open";
  openBtn.addEventListener("click", () => {
    window.location.href = `/research/workspace/${encodeURIComponent(item.phone_digits)}`;
  });

  row.appendChild(info);
  row.appendChild(openBtn);
  container.appendChild(row);
}

function renderNotes(items) {
  if (!notesList) return;
  notesList.innerHTML = "";
  if (!items || items.length === 0) {
    setEmpty(notesList, "No notes yet.");
    return;
  }
  items.forEach((note) => {
    const item = document.createElement("div");
    item.className = "note-item";

    const meta = document.createElement("div");
    meta.className = "result-meta";
    meta.textContent = `${formatTimestamp(note.ts)}${note.source === "call" ? " · call" : ""}`;

    const textarea = document.createElement("textarea");
    textarea.value = note.note_text || "";

    const actions = document.createElement("div");
    actions.className = "note-row-actions";

    const editBtn = document.createElement("button");
    editBtn.className = "note-btn";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", async () => {
      await fetchJson(`/research/note/${note.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note_text: textarea.value.trim() }),
      });
      await refreshWorkspace();
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "note-btn delete";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm("Delete this note?")) return;
      await fetchJson(`/research/note/${note.id}`, { method: "DELETE" });
      await refreshWorkspace();
    });

    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);

    item.appendChild(meta);
    item.appendChild(textarea);
    item.appendChild(actions);
    notesList.appendChild(item);
  });
}

function renderEmails(items) {
  if (!emailsList) return;
  emailsList.innerHTML = "";
  if (!items || items.length === 0) {
    setEmpty(emailsList, "No emails linked yet.");
    return;
  }
  items.slice(0, 4).forEach((email) => {
    const row = document.createElement("div");
    row.className = "email-row";
    const info = document.createElement("div");
    info.className = "result-info";
    const subject = document.createElement("div");
    subject.className = "result-number";
    subject.textContent = email.subject || "(no subject)";
    const meta = document.createElement("div");
    meta.className = "result-meta";
    meta.textContent = `${email.from_addr || "Unknown"} · ${email.date || ""}`;
    info.appendChild(subject);
    info.appendChild(meta);

    const link = document.createElement("a");
    link.href = email.gmail_link || "#";
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Open";

    row.appendChild(info);
    row.appendChild(link);
    emailsList.appendChild(row);
  });
}

function renderRecordings(recordings, calls) {
  if (!recordingsList) return;
  recordingsList.innerHTML = "";
  const items = recordings && recordings.length ? recordings : calls || [];
  if (!items || items.length === 0) {
    setEmpty(recordingsList, "No recordings yet.");
    return;
  }
  items.slice(0, 4).forEach((item) => {
    const row = document.createElement("div");
    row.className = "recording-row";

    const play = document.createElement("div");
    play.className = "play-btn";
    play.innerHTML = `
      <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
        <path d="M8 6l10 6-10 6z" fill="currentColor" />
      </svg>
    `;

    const name = document.createElement("div");
    name.className = "recording-name";
    name.textContent = item.file_path
      ? item.file_path.split("/").pop()
      : item.audio_path
        ? item.audio_path.split("/").pop()
        : `Call_${item.id}`;

    const time = document.createElement("div");
    time.className = "recording-time";
    time.textContent = formatTimestamp(item.created_at || item.ts_start);

    const trash = document.createElement("button");
    trash.className = "trash-btn";
    trash.innerHTML = `
      <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
        <path d="M4 7h16M9 7V5h6v2M10 11v6M14 11v6M6 7l1 12h10l1-12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    `;
    trash.addEventListener("click", async () => {
      if (!item.id) return;
      if (!confirm("Delete this call?")) return;
      await fetchJson(`/research/call/${item.id}`, { method: "DELETE" });
      await refreshWorkspace();
    });

    row.appendChild(play);
    row.appendChild(name);
    row.appendChild(time);
    row.appendChild(trash);
    recordingsList.appendChild(row);
  });
}

function updateEmptyState(payload) {
  if (!emptyCard) return;
  if (!payload) {
    emptyCard.classList.remove("hidden");
    return;
  }
  emptyCard.classList.add("hidden");
  if (emptyDigits) {
    emptyDigits.textContent =
      payload.formatted || formatPhone(payload.phone_digits);
  }
}

function renderWorkspace(payload) {
  if (!payload) return;
  activeDigits = payload.phone_digits;
  latestCallId = payload.latest_call_id || null;
  if (input) input.value = payload.formatted || formatPhone(activeDigits);
  if (vendorPhone)
    vendorPhone.textContent = payload.formatted || formatPhone(activeDigits);
  if (vendorName) {
    vendorName.textContent =
      payload.profile?.vendor_name ||
      payload.display_name ||
      "Research Profile";
  }
  if (vendorNameInput)
    vendorNameInput.value = payload.profile?.vendor_name || "";
  if (vendorCompanyInput)
    vendorCompanyInput.value = payload.profile?.vendor_company || "";
  if (vendorTitleInput)
    vendorTitleInput.value = payload.profile?.vendor_title || "";
  if (jdText) jdText.value = payload.jd_text || "";
  if (resumeText) resumeText.value = payload.resume_text || "";
  if (summaryLastCall)
    summaryLastCall.textContent = formatTimestamp(payload.last_call_ts);
  if (summaryCount) summaryCount.textContent = payload.call_count || 0;
  renderNotes(payload.notes || []);
  renderEmails(payload.emails || []);
  renderRecordings(payload.recordings || [], payload.calls || []);
  updateEmptyState(payload);
}

async function refreshWorkspace() {
  if (!activeDigits) return;
  const data = await fetchJson(
    `/research/workspace/${encodeURIComponent(activeDigits)}/data`,
  );
  renderWorkspace(data.workspace);
}

async function runSearch() {
  if (!list || !input) return;
  const q = input.value.trim();
  const normalized = normalizeQuery(q);
  if (!normalized) {
    setState("idle");
    return;
  }
  setState("results");
  setEmpty(list, "Searching...");
  try {
    const data = await fetchJson(`/research/search?q=${encodeURIComponent(q)}`);
    const results = data.results || [];
    list.innerHTML = "";
    if (results.length === 0) {
      if (normalized.mode === "last10" && normalized.last10) {
        setState("empty", { digits: normalized.last10 });
      } else {
        setState("empty", { digits: normalized.partial || normalized.last4 });
      }
      return;
    }
    setState("results");
    results.forEach((item) => renderResultRow(item, list));
    if (results.length === 1 && results[0].phone_digits) {
      window.location.href = `/research/workspace/${encodeURIComponent(results[0].phone_digits)}`;
    }
  } catch (err) {
    setState("results");
    setEmpty(list, "Search failed.");
  }
}

async function createProfileFlow(last10) {
  await fetchJson("/research/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_digits: last10 }),
  });
  window.location.href = `/research/workspace/${encodeURIComponent(last10)}`;
}

btn?.addEventListener("click", runSearch);
input?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") runSearch();
});

allNumbersBtn?.addEventListener("click", loadAllNumbers);

createBtn?.addEventListener("click", () => {
  const last10 = stateEmpty?.dataset.phoneDigits;
  if (!last10) return;
  if (String(last10).length !== 10) {
    alert("Enter a full 10-digit phone number to create a profile.");
    input?.focus();
    input?.select();
    return;
  }
  createProfileFlow(last10);
});

emptyCreateBtn?.addEventListener("click", () => {
  if (activeDigits) createProfileFlow(activeDigits);
});

backBtn?.addEventListener("click", () => {
  window.location.href = "/research";
});

saveProfileBtn?.addEventListener("click", async () => {
  if (!activeDigits) return;
  await fetchJson(`/research/profile/${encodeURIComponent(activeDigits)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vendor_name: vendorNameInput?.value || "",
      vendor_company: vendorCompanyInput?.value || "",
      vendor_title: vendorTitleInput?.value || "",
    }),
  });
  await refreshWorkspace();
});

saveJd?.addEventListener("click", async () => {
  if (!activeDigits) return;
  await fetchJson(`/research/jd/${encodeURIComponent(activeDigits)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jd_text: jdText?.value || "" }),
  });
  await refreshWorkspace();
});

saveResume?.addEventListener("click", async () => {
  if (!activeDigits) return;
  await fetchJson(`/research/resume/${encodeURIComponent(activeDigits)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume_text: resumeText?.value || "" }),
  });
  await refreshWorkspace();
});

addNoteBtn?.addEventListener("click", async () => {
  const text = newNoteText?.value.trim();
  if (!text || !activeDigits) return;
  await fetchJson("/research/note", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_digits: activeDigits, note_text: text }),
  });
  newNoteText.value = "";
  await refreshWorkspace();
});

if (workspacePayload) {
  renderWorkspace(workspacePayload);
} else if (stateIdle) {
  setState("idle");
}
