(function () {
  const toast = document.getElementById("machaaToast");
  const timerEl = document.getElementById("machaaTimer");
  const branchCard = document.getElementById("machaaBranchCard");
  const branchButtons = document.querySelectorAll(".machaa-branch-btn");
  const hotButtons = document.querySelectorAll(".machaa-hot-btn");
  let openHotId = null;
  let openBranchKey = null;

  const branchContent = {
    intro: {
      rule: "Rule: Keep it 10-15 seconds, then take control.",
      response: [
        "Response: Quick intro with current role and focus area.",
        "Response: Express interest in learning about the role.",
      ],
      reverse: [
        "Ask back: Is this a new requirement or duplicate?",
        "Ask back: Did you send the JD to my email?",
      ],
    },
    visa: {
      rule: "Rule: Do not answer directly; ask client requirement first.",
      response: [
        "Response: I can align to the client policy.",
        "Response: Please share the client's visa requirement.",
      ],
      reverse: [
        "Ask back: Is there a specific visa requirement?",
        "Ask back: When is passport required?",
      ],
    },
    jd: {
      rule: "Rule: Pause and confirm structure before details.",
      response: [
        "Response: Happy to review once we confirm client and terms.",
        "Response: Please share rate range and engagement type.",
      ],
      reverse: [
        "Ask back: Is this client or vendor requirement?",
        "Ask back: Is it W2, C2C, or contract-to-hire?",
      ],
    },
  };

  function showToast() {
    if (!toast) return;
    toast.classList.add("show");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toast.classList.remove("show"), 1200);
  }

  function copyText(text) {
    if (!text) return;
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(showToast).catch(() => {});
      return;
    }
    const temp = document.createElement("textarea");
    temp.value = text;
    temp.style.position = "fixed";
    temp.style.opacity = "0";
    document.body.appendChild(temp);
    temp.select();
    try {
      document.execCommand("copy");
      showToast();
    } catch (e) {}
    document.body.removeChild(temp);
  }

  function toggleBranch(key) {
    const content = branchContent[key];
    if (!content || !branchCard) return;
    if (openBranchKey === key) {
      openBranchKey = null;
      branchButtons.forEach((btn) => btn.classList.remove("is-open"));
      branchCard.classList.remove("is-open");
      return;
    }
    openBranchKey = key;
    branchButtons.forEach((btn) => {
      btn.classList.toggle("is-open", btn.dataset.branch === key);
    });
    branchCard.innerHTML = `
      <h4>${content.rule}</h4>
      <div>${content.response[0]}</div>
      <div>${content.response[1]}</div>
      <div style="margin-top:8px; color:#3affc3; font-weight:600;">Reverse questions:</div>
      <div>${content.reverse[0]}</div>
      <div>${content.reverse[1]}</div>
    `;
    branchCard.classList.add("is-open");
  }

  function toggleHot(targetId) {
    if (openHotId === targetId) {
      openHotId = null;
      hotButtons.forEach((btn) => {
        btn.classList.remove("is-open");
        const panel = document.getElementById(btn.dataset.toggle);
        if (panel) panel.classList.remove("is-open");
      });
      return;
    }
    openHotId = targetId;
    hotButtons.forEach((btn) => {
      const panel = document.getElementById(btn.dataset.toggle);
      const isActive = btn.dataset.toggle === targetId;
      btn.classList.toggle("is-open", isActive);
      if (panel) panel.classList.toggle("is-open", isActive);
    });
  }

    function isTypingTarget(target) {
      if (!target) return false;
      const tag = target.tagName ? target.tagName.toLowerCase() : "";
      return (
        tag === "input" ||
        tag === "textarea" ||
        tag === "select" ||
        target.isContentEditable
      );
    }

    document.addEventListener("keydown", (event) => {
      if (!event.ctrlKey || event.code !== "Space") return;
      if (isTypingTarget(document.activeElement)) return;
      event.preventDefault();
      if (document.fullscreenElement) {
        document.exitFullscreen().catch((err) => {
          console.warn("[Machaa Portrait] exit fullscreen failed:", err);
        });
      } else {
        document.documentElement
          .requestFullscreen()
          .catch((err) => {
            console.warn("[Machaa Portrait] enter fullscreen failed:", err);
          });
      }
    });
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const copyBtn = target.closest("[data-copy]");
    if (copyBtn) {
      copyText(copyBtn.dataset.copy);
      return;
    }
    const hotBtn = target.closest(".machaa-hot-btn");
    if (hotBtn) {
      toggleHot(hotBtn.dataset.toggle);
      return;
    }
    const branchBtn = target.closest(".machaa-branch-btn");
    if (branchBtn) {
      toggleBranch(branchBtn.dataset.branch);
    }
  });

  if (timerEl) {
    const start = Date.now();
    setInterval(() => {
      const elapsed = Math.floor((Date.now() - start) / 1000);
      const minutes = String(Math.floor(elapsed / 60)).padStart(2, "0");
      const seconds = String(elapsed % 60).padStart(2, "0");
      timerEl.textContent = `${minutes}:${seconds}`;
    }, 1000);
  }
})();
