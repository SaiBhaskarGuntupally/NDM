(function (global) {
  "use strict";

  function normalizePhone(value) {
    var digits = String(value || "").replace(/\D/g, "");
    if (!digits) {
      return { digits: "", last10: "", last4: "", e164: "" };
    }
    var last10 = digits;
    if (digits.length === 11 && digits.indexOf("1") === 0) {
      last10 = digits.slice(1);
    } else if (digits.length > 10) {
      last10 = digits.slice(-10);
    }
    var last4 = last10.length >= 4 ? last10.slice(-4) : "";
    var e164 =
      last10.length === 10
        ? "+1-" +
          last10.slice(0, 3) +
          "-" +
          last10.slice(3, 6) +
          "-" +
          last10.slice(6)
        : digits;
    return { digits: digits, last10: last10, last4: last4, e164: e164 };
  }

  function deriveJdTitle(jdText) {
    if (!jdText) return "";
    var lines = String(jdText)
      .split(/\r?\n/)
      .map(function (line) {
        return line.trim();
      })
      .filter(function (line) {
        return line.length > 0;
      });
    if (!lines.length) return "";
    var title = lines[0];
    if (title.length > 60) {
      title = title.slice(0, 57) + "...";
    }
    return title;
  }

  function getBaseUrl(opts) {
    var base = (opts && opts.baseUrl) || global.__PROFILE_API_BASE__ || "";
    if (base.endsWith("/")) {
      return base.slice(0, -1);
    }
    return base;
  }

  async function loadProfile(phoneDigits, opts) {
    var norm = normalizePhone(phoneDigits);
    if (!norm.last10) return null;
    var base = getBaseUrl(opts);
    var res = await fetch(
      base + "/profile-data/" + encodeURIComponent(norm.last10),
    );
    if (!res.ok) return null;
    var data = await res.json();
    return data.profile || null;
  }

  async function saveProfile(profile, opts) {
    var norm = normalizePhone(
      profile &&
        (profile.phone_digits || profile.phoneE164 || profile.phone || ""),
    );
    if (!norm.last10) return null;
    var payload = Object.assign({}, profile, { phone_digits: norm.last10 });
    var base = getBaseUrl(opts);
    var res = await fetch(
      base + "/profile-data/" + encodeURIComponent(norm.last10),
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    if (!res.ok) return null;
    var data = await res.json();
    return data.profile || null;
  }

  async function saveNote(phoneDigits, noteText, opts) {
    var norm = normalizePhone(phoneDigits);
    if (!norm.last10) return null;
    var base = getBaseUrl(opts);
    var res = await fetch(
      base + "/profile-data/" + encodeURIComponent(norm.last10) + "/notes",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note_text: noteText || "" }),
      },
    );
    if (!res.ok) return null;
    var data = await res.json();
    return data.notes || [];
  }

  function renderResearch(profile) {
    if (!profile) return;
    var vendorNameInput = document.getElementById("vendorNameInput");
    var vendorCompanyInput = document.getElementById("vendorCompanyInput");
    var vendorTitleInput = document.getElementById("vendorTitleInput");
    var jdTitleEl = document.getElementById("jdTitle");
    var jdTextEl = document.getElementById("jdText");
    var resumeTextEl = document.getElementById("resumeText");

    if (vendorNameInput) vendorNameInput.value = profile.name || "";
    if (vendorCompanyInput) vendorCompanyInput.value = profile.company || "";
    if (vendorTitleInput) vendorTitleInput.value = profile.title || "";

    if (jdTitleEl) {
      var title = profile.jd_title || deriveJdTitle(profile.jd_text || "");
      jdTitleEl.textContent = title || "—";
    }
    if (jdTextEl) {
      jdTextEl.textContent = profile.jd_text || "No JD pinned.";
    }
    if (resumeTextEl) {
      if (resumeTextEl.tagName === "TEXTAREA") {
        resumeTextEl.value = profile.resume_text || "";
      } else {
        resumeTextEl.textContent = profile.resume_text || "";
      }
    }
  }

  function renderOnCall(profile) {
    var jdTitleEl = document.getElementById("jdTitle");
    var jdTextEl = document.getElementById("jdText");
    var resumeMatchEl = document.getElementById("resumeMatch");
    var notesEl = document.getElementById("notes");
    var callerMetaEl = document.getElementById("callerMeta");

    if (!profile) {
      if (jdTitleEl) jdTitleEl.textContent = "—";
      if (jdTextEl) jdTextEl.textContent = "No JD pinned.";
      if (resumeMatchEl) resumeMatchEl.textContent = "No resume match yet.";
      if (notesEl) notesEl.textContent = "";
      if (callerMetaEl) callerMetaEl.textContent = "—";
      return;
    }

    var title = profile.jd_title || deriveJdTitle(profile.jd_text || "");
    if (jdTitleEl) jdTitleEl.textContent = title || "—";
    if (jdTextEl) jdTextEl.textContent = profile.jd_text || "No JD pinned.";
    if (resumeMatchEl) {
      resumeMatchEl.textContent = profile.resume_text || "No resume match yet.";
    }

    if (notesEl) {
      notesEl.innerHTML = "";
      if (profile.notes && profile.notes.length) {
        profile.notes.forEach(function (note) {
          var item = document.createElement("div");
          item.className = "note-item";
          var ts = document.createElement("div");
          ts.textContent = note.ts || "";
          var text = document.createElement("div");
          text.textContent = note.note_text || "";
          item.appendChild(ts);
          item.appendChild(text);
          notesEl.appendChild(item);
        });
      } else {
        var empty = document.createElement("div");
        empty.className = "empty-text";
        empty.textContent = "No notes yet.";
        notesEl.appendChild(empty);
      }
    }

    if (callerMetaEl) {
      var parts = [];
      if (profile.name) parts.push(profile.name);
      if (profile.company) parts.push(profile.company);
      if (profile.vendor && profile.vendor !== profile.name) {
        parts.push("Vendor: " + profile.vendor);
      }
      if (profile.title) parts.push(profile.title);
      callerMetaEl.textContent = parts.length ? parts.join(" · ") : "—";
    }
  }

  global.ProfileStore = {
    normalizePhone: normalizePhone,
    loadProfile: loadProfile,
    saveProfile: saveProfile,
    saveNote: saveNote,
    renderResearch: renderResearch,
    renderOnCall: renderOnCall,
  };
})(window);
