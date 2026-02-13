/**
 * VENDOR CALL COCKPIT - PORTRAIT MODE CONTROLLER
 * Handles all interactions for the portrait cockpit interface
 */

// ===== STATE MANAGEMENT =====
const state = {
  currentGate: 1,
  currentState: "Screening",
  vendor: "",
  source: "",
  client: "",
  structure: "",
  rate: "",
  visa: "",
  askedQuestions: new Set(),
  callStartTime: null,
};

// ===== QUESTION LIBRARY =====
// Group 1: Opening (7 questions)
const GROUP_1 = [
  "May I know where you got my profile from?",
  "Can you confirm this is not a duplicate submission?",
  "Have you already sent my profile for this role?",
  "Who is the end client for this opportunity?",
  "Can you share the detailed job description?",
  "Is this position still actively open?",
  "What is the interview timeline for this role?",
];

// Group 2: Screening (8 questions)
const GROUP_2 = [
  "Was my profile shared by anyone else for this role?",
  "How many candidates have you submitted so far?",
  "Is the client actively interviewing candidates?",
  "When was this position opened?",
  "What is the reason for this opening?",
  "Is this a new role or a backfill?",
  "Who will I be reporting to?",
  "What is the team size and structure?",
];

// Group 3: JD Clarity (6 questions)
const GROUP_3 = [
  "Can you share the complete job description document?",
  "What are the must-have technical skills?",
  "What are the nice-to-have skills?",
  "Is this role more focused on platform or analytics?",
  "Will this be hands-on or more architectural?",
  "What percentage of time is coding vs meetings?",
];

// Group 4: Requirement (9 questions)
const GROUP_4 = [
  "Is this a client requirement or vendor requirement?",
  "If it's W2, is it client-mandated or vendor-mandated?",
  "Who determines the requirements—client or your company?",
  "Do you work with multiple partners on this client?",
  "Can you share the list of other vendors?",
  "What is your relationship with the client?",
  "Are you the prime vendor or tier-2/tier-3?",
  "How long have you been working with this client?",
  "What is the typical submission-to-interview ratio?",
];

// Group 5: Structure (7 questions)
const GROUP_5 = [
  "Is this W2 or C2C or Corp-to-Corp?",
  "If W2, what benefits are included?",
  "If C2C, what is the payment cycle?",
  "Do you offer health insurance for W2?",
  "Is this a 1099 or W2 structure?",
  "Can I choose between W2 and C2C?",
  "What are the differences in rate between W2 and C2C?",
];

// Group 6: Rate (10 questions)
const GROUP_6 = [
  "What is the approved rate range for this role?",
  "Is the rate flexible or fixed?",
  "What rate are you offering me?",
  "Is this rate on W2 or C2C?",
  "Does the rate include benefits?",
  "Is the rate negotiable?",
  "What is the payment cycle?",
  "Are expenses covered separately?",
  "Is overtime paid if required?",
  "What is the typical rate band for this client?",
];

// Group 7: Docs (8 questions)
const GROUP_7 = [
  "What documents are needed for submission?",
  "At what stage is the passport required?",
  "Is DL sufficient for submission?",
  "Do I need to share my I-94 now?",
  "Can documents be shared via secure link?",
  "What is the document submission deadline?",
  "Can we finalize rate before sharing documents?",
  "Will my documents be shared with other clients?",
];

// Group 8: Visa (6 questions)
const GROUP_8 = [
  "Is there any specific visa requirement from the client side?",
  "Does the client accept H1B transfer candidates?",
  "Does the client sponsor visas?",
  "Are there any visa restrictions for this role?",
  "Is EAD acceptable for this client?",
  "Does the client prefer US Citizens or Green Card holders?",
];

// Group 9: Timeline (7 questions)
const GROUP_9 = [
  "When is the submission deadline?",
  "When can I expect to hear back?",
  "What is the interview process?",
  "How many rounds of interviews?",
  "When are interviews expected to start?",
  "What is the expected start date?",
  "How long is the decision-making process?",
];

// Group 10: Close (6 questions)
const GROUP_10 = [
  "What are the next steps from your side?",
  "When should I expect an update?",
  "Can I follow up if I don't hear back?",
  "What is the typical response time?",
  "Will you confirm the submission via email?",
  "Can I get your direct contact for follow-up?",
];

// Group 11: Red Flags (8 questions)
const GROUP_11 = [
  "Why are you looking for candidates immediately?",
  "Has anyone else been submitted from your company?",
  "Do you have an exclusive agreement with the client?",
  "Why is the rate lower than market standards?",
  "Why are documents needed before rate confirmation?",
  "Why can't you share the client name now?",
  "Have previous candidates from you been selected?",
  "What is your placement ratio for this client?",
];

const QUESTION_GROUPS = {
  1: { title: "G1: Opening", questions: GROUP_1 },
  2: { title: "G2: Screening", questions: GROUP_2 },
  3: { title: "G3: JD Clarity", questions: GROUP_3 },
  4: { title: "G4: Requirement", questions: GROUP_4 },
  5: { title: "G5: Structure", questions: GROUP_5 },
  6: { title: "G6: Rate", questions: GROUP_6 },
  7: { title: "G7: Docs", questions: GROUP_7 },
  8: { title: "G8: Visa", questions: GROUP_8 },
  9: { title: "G9: Timeline", questions: GROUP_9 },
  10: { title: "G10: Close", questions: GROUP_10 },
  11: { title: "G11: Red Flags", questions: GROUP_11 },
};

// HOT 10 Questions (highest priority)
const HOT_10 = [
  "May I know where you got my profile from?",
  "Who is the end client for this opportunity?",
  "Can you share the detailed job description?",
  "Is this a client requirement or vendor requirement?",
  "Is this W2 or C2C or Corp-to-Corp?",
  "What is the approved rate range for this role?",
  "Is there any specific visa requirement from the client side?",
  "At what stage is the passport required—submission or client interview?",
  "Has the client already started interviewing, and is this role actively moving forward?",
  "What are the next steps from your side, and when should I expect an update?",
];

// ===== NEXT 5 QUESTIONS MAPPING =====
const NEXT_5_MAP = {
  Screening: [
    "May I know where you got my profile from?",
    "Was my profile shared by anyone else for this role?",
    "Can you share the detailed job description?",
    "Who is the end client for this opportunity?",
    "Is this W2 or C2C or Corp-to-Corp?",
  ],
  Requirement: [
    "Is this a client requirement or vendor requirement?",
    "Who is the end client for this opportunity?",
    "Do you work with multiple partners on this client?",
    "What is your relationship with the client?",
    "What are the must-have technical skills?",
  ],
  Rate: [
    "What is the approved rate range for this role?",
    "Is the rate flexible or fixed?",
    "What rate are you offering me?",
    "What is the payment cycle?",
    "Are expenses covered separately?",
  ],
  Docs: [
    "What documents are needed for submission?",
    "At what stage is the passport required?",
    "Is there any specific visa requirement from the client side?",
    "Can we finalize rate before sharing documents?",
    "Can documents be shared via secure link?",
  ],
  Close: [
    "What are the next steps from your side?",
    "When should I expect an update?",
    "When is the submission deadline?",
    "Will you confirm the submission via email?",
    "What is the interview process?",
  ],
};

// ===== NEXT ACTION MAPPING =====
const NEXT_ACTION_MAP = {
  Screening: "Ask: Where did you get my profile from?",
  Requirement: "Ask: Is this a client requirement or vendor requirement?",
  Rate: "Ask: What is the approved rate range for this role?",
  Docs: "Ask: What documents are needed and at what stage?",
  Close: "Ask: What are the next steps and when should I expect an update?",
};

// ===== INITIALIZATION =====
document.addEventListener("DOMContentLoaded", () => {
  initializeControls();
  initializeFlowGraph();
  initializeNext5();
  initializeGroupPills();
  initializeDrawer();
  initializeFullscreen();
  initializeTimer();
});

// ===== CONTROL BAR HANDLERS =====
function initializeControls() {
  // Source selector
  document.querySelectorAll("#sourceSelector .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document
        .querySelectorAll("#sourceSelector .chip")
        .forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.source = chip.dataset.value;
    });
  });

  // Structure control
  document.querySelectorAll("#structureControl .segment").forEach((segment) => {
    segment.addEventListener("click", () => {
      document
        .querySelectorAll("#structureControl .segment")
        .forEach((s) => s.classList.remove("active"));
      segment.classList.add("active");
      state.structure = segment.dataset.value;
    });
  });

  // Visa selector
  document.querySelectorAll("#visaSelector .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document
        .querySelectorAll("#visaSelector .chip")
        .forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.visa = chip.dataset.value;
    });
  });

  // Call state control
  document.querySelectorAll("#callStateControl .segment").forEach((segment) => {
    segment.addEventListener("click", () => {
      document
        .querySelectorAll("#callStateControl .segment")
        .forEach((s) => s.classList.remove("active"));
      segment.classList.add("active");
      state.currentState = segment.dataset.state;
      updateNextAction();
      updateNext5();
    });
  });

  // Input fields
  document.getElementById("vendorName").addEventListener("input", (e) => {
    state.vendor = e.target.value;
  });

  document.getElementById("clientName").addEventListener("input", (e) => {
    state.client = e.target.value;
  });

  document.getElementById("rateInput").addEventListener("input", (e) => {
    state.rate = e.target.value;
  });
}

function updateNextAction() {
  const nextActionText = document.getElementById("nextAction");
  nextActionText.textContent =
    NEXT_ACTION_MAP[state.currentState] || "Continue conversation";
}

// ===== FLOW GRAPH HANDLERS =====
function initializeFlowGraph() {
  document.querySelectorAll(".gate-node").forEach((node) => {
    node.addEventListener("click", () => {
      const gateNumber = parseInt(node.dataset.gate);
      setActiveGate(gateNumber);
    });
  });

  // Set initial gate
  setActiveGate(1);
}

function setActiveGate(gateNumber) {
  state.currentGate = gateNumber;

  // Map gate to call state
  const gateToStateMap = {
    1: "Screening", // JD Gate
    2: "Screening", // Role Alignment
    3: "Requirement", // Structure Gate
    4: "Rate", // Rate Gate
    5: "Docs", // Docs Gate
    6: "Docs", // RTR Gate
    7: "Close", // Close
  };

  const newState = gateToStateMap[gateNumber];
  if (newState && newState !== state.currentState) {
    state.currentState = newState;

    // Update call state segmented control
    document
      .querySelectorAll("#callStateControl .segment")
      .forEach((s) => s.classList.remove("active"));
    const activeSegment = document.querySelector(
      `#callStateControl .segment[data-state="${newState}"]`,
    );
    if (activeSegment) {
      activeSegment.classList.add("active");
    }

    // Update next action and next 5 questions
    updateNextAction();
    updateNext5();
  }

  // Reset all gates
  document.querySelectorAll(".gate-circle").forEach((circle) => {
    circle.classList.remove("blue", "green", "red");
    circle.classList.add("gray");
    circle.nextElementSibling.classList.remove("active");
  });

  // Mark gates as passed (green) up to current gate
  for (let i = 1; i < gateNumber; i++) {
    const node = document.querySelector(`.gate-node[data-gate="${i}"]`);
    if (node) {
      const circle = node.querySelector(".gate-circle");
      circle.classList.remove("gray");
      circle.classList.add("green");
    }
  }

  // Mark current gate as active (blue)
  const currentNode = document.querySelector(
    `.gate-node[data-gate="${gateNumber}"]`,
  );
  if (currentNode) {
    const circle = currentNode.querySelector(".gate-circle");
    const text = currentNode.querySelector(".gate-text");
    circle.classList.remove("gray");
    circle.classList.add("blue");
    text.classList.add("active");
  }
}

// ===== NEXT 5 QUESTIONS HANDLERS =====
function initializeNext5() {
  updateNext5();
}

function updateNext5() {
  const next5List = document.getElementById("next5List");
  const questions = NEXT_5_MAP[state.currentState] || HOT_10.slice(0, 5);

  next5List.innerHTML = "";

  questions.forEach((question, index) => {
    const item = document.createElement("div");
    item.className = "next5-item";

    const text = document.createElement("div");
    text.className = "next5-text";
    text.textContent = question;

    const actions = document.createElement("div");
    actions.className = "next5-actions";

    const copyBtn = document.createElement("button");
    copyBtn.className = "action-btn";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", () => {
      copyToClipboard(question);
    });

    const askedBtn = document.createElement("button");
    askedBtn.className = "action-btn";
    askedBtn.textContent = state.askedQuestions.has(question)
      ? "✓ Asked"
      : "Asked";
    if (state.askedQuestions.has(question)) {
      askedBtn.classList.add("asked");
    }
    askedBtn.addEventListener("click", () => {
      toggleAsked(question, askedBtn);
    });

    actions.appendChild(copyBtn);
    actions.appendChild(askedBtn);

    item.appendChild(text);
    item.appendChild(actions);

    next5List.appendChild(item);
  });
}

function toggleAsked(question, button) {
  if (state.askedQuestions.has(question)) {
    state.askedQuestions.delete(question);
    button.classList.remove("asked");
    button.textContent = "Asked";
  } else {
    state.askedQuestions.add(question);
    button.classList.add("asked");
    button.textContent = "✓ Asked";
  }
}

// ===== GROUP PILLS & DRAWER =====
function initializeGroupPills() {
  document.querySelectorAll(".group-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const groupNum = parseInt(pill.dataset.group);
      openGroupDrawer(groupNum);
    });
  });
}

function initializeDrawer() {
  // Close button
  document.getElementById("drawerClose").addEventListener("click", closeDrawer);

  // ESC key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDrawer();
    }
  });

  // Click outside
  document.getElementById("drawerOverlay").addEventListener("click", (e) => {
    if (e.target.id === "drawerOverlay") {
      closeDrawer();
    }
  });

  // Search
  document.getElementById("drawerSearch").addEventListener("input", (e) => {
    filterDrawerQuestions(e.target.value);
  });
}

function openGroupDrawer(groupNum) {
  const group = QUESTION_GROUPS[groupNum];
  if (!group) return;

  const drawerTitle = document.getElementById("drawerTitle");
  const drawerBody = document.getElementById("drawerBody");
  const drawerSearch = document.getElementById("drawerSearch");

  drawerTitle.textContent = group.title;
  drawerSearch.value = "";

  drawerBody.innerHTML = "";

  group.questions.forEach((question) => {
    const item = document.createElement("div");
    item.className = "drawer-question";
    item.dataset.question = question.toLowerCase();

    const text = document.createElement("div");
    text.className = "drawer-question-text";
    text.textContent = question;

    const copyBtn = document.createElement("button");
    copyBtn.className = "drawer-copy-btn";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", () => {
      copyToClipboard(question);
    });

    item.appendChild(text);
    item.appendChild(copyBtn);

    drawerBody.appendChild(item);
  });

  document.getElementById("drawerOverlay").classList.remove("hidden");
}

function closeDrawer() {
  document.getElementById("drawerOverlay").classList.add("hidden");
}

function filterDrawerQuestions(searchTerm) {
  const term = searchTerm.toLowerCase();
  document.querySelectorAll(".drawer-question").forEach((item) => {
    const question = item.dataset.question;
    if (question.includes(term)) {
      item.style.display = "flex";
    } else {
      item.style.display = "none";
    }
  });
}

// ===== FULLSCREEN HANDLER =====
function initializeFullscreen() {
  document.addEventListener("keydown", (e) => {
    // Ctrl+Space (ignore if typing in input/textarea)
    if (e.ctrlKey && e.code === "Space") {
      const activeElement = document.activeElement;
      if (
        activeElement.tagName === "INPUT" ||
        activeElement.tagName === "TEXTAREA"
      ) {
        return;
      }

      e.preventDefault();
      toggleFullscreen();
    }
  });
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch((err) => {
      console.error("Fullscreen error:", err);
    });
  } else {
    document.exitFullscreen();
  }
}

// ===== TIMER =====
function initializeTimer() {
  state.callStartTime = Date.now();
  setInterval(updateTimer, 1000);
}

function updateTimer() {
  if (!state.callStartTime) return;

  const elapsed = Math.floor((Date.now() - state.callStartTime) / 1000);
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;

  document.getElementById("callTimer").textContent =
    `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

// ===== COPY TO CLIPBOARD =====
function copyToClipboard(text) {
  navigator.clipboard
    .writeText(text)
    .then(() => {
      showToast("Copied");
    })
    .catch((err) => {
      console.error("Copy failed:", err);
    });
}

// ===== TOAST NOTIFICATION =====
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");

  setTimeout(() => {
    toast.classList.add("hidden");
  }, 2000);
}
