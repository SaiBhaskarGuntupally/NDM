(() => {
  const DEBUG_WAR_ROOM = window.DEBUG_WAR_ROOM === true;

  const DEFAULT_PRIMARY_LEFT = 0;
  const DEFAULT_TOP = 0;
  const DEFAULT_MONITOR_WIDTH = 1920;
  const DEFAULT_PRIMARY_WIDTH = 1200;
  const DEFAULT_PRIMARY_HEIGHT = 1040;
  const DEFAULT_PORTRAIT_WIDTH = 900;
  const DEFAULT_PORTRAIT_HEIGHT = 1100;
  const DEFAULT_RIGHT_LEFT = DEFAULT_MONITOR_WIDTH;

  const RESUME_WINDOW_NAME = "NDM_WAR_ROOM_LEFT";
  const CHEATS_WINDOW_NAME = "NDM_WAR_ROOM_RIGHT";
  const RESUME_ROUTE = "/war-room/resume";
  const CHEATS_ROUTE = "/war-room/cheats";

  let resumeRef = null;
  let cheatsRef = null;

  function log(...args) {
    if (!DEBUG_WAR_ROOM) return;
    console.log("[WarRoom]", ...args);
  }

  function buildFeatures({ left, top, width, height }) {
    return [
      "popup=yes",
      "toolbar=no",
      "location=no",
      "menubar=no",
      "scrollbars=yes",
      "resizable=yes",
      `left=${left}`,
      `top=${top}`,
      `width=${width}`,
      `height=${height}`,
    ].join(",");
  }

  function isWindowMissing(ref) {
    return !ref || ref.closed;
  }

  function openWindow(url, name, features) {
    const ref = window.open(url, name, features);
    if (ref) {
      try {
        ref.focus();
      } catch (err) {
        log("Focus failed", err);
      }
    }
    return ref;
  }

  function openResumeWindow() {
    const features = buildFeatures({
      left: DEFAULT_PRIMARY_LEFT,
      top: DEFAULT_TOP,
      width: DEFAULT_PRIMARY_WIDTH,
      height: DEFAULT_PRIMARY_HEIGHT,
    });
    const ref = openWindow(RESUME_ROUTE, RESUME_WINDOW_NAME, features);
    if (ref) {
      resumeRef = ref;
      try {
        ref.location.href = RESUME_ROUTE;
      } catch (err) {
        log("Resume navigation failed", err);
      }
    }
    log(ref ? "Resume window opened/reused" : "Resume popup blocked");
    return ref;
  }

  function openCheatWindow() {
    const features = buildFeatures({
      left: DEFAULT_RIGHT_LEFT,
      top: DEFAULT_TOP,
      width: DEFAULT_PORTRAIT_WIDTH,
      height: DEFAULT_PORTRAIT_HEIGHT,
    });
    const ref = openWindow(CHEATS_ROUTE, CHEATS_WINDOW_NAME, features);
    if (ref) {
      cheatsRef = ref;
      try {
        ref.location.href = CHEATS_ROUTE;
      } catch (err) {
        log("Cheats navigation failed", err);
      }
    }
    log(ref ? "Cheats window opened/reused" : "Cheats popup blocked");
    return ref;
  }

  function openWarRoom() {
    const resume = openResumeWindow();
    const cheats = openCheatWindow();
    const popupBlocked = !resume || !cheats;
    log("War Room open", { resume: !!resume, cheats: !!cheats, popupBlocked });
    return {
      resumeOpened: !!resume,
      cheatsOpened: !!cheats,
      popupBlocked,
    };
  }

  function focusExistingWindows() {
    if (!isWindowMissing(resumeRef)) {
      try {
        resumeRef.focus();
      } catch (err) {
        log("Resume focus failed", err);
      }
    }
    if (!isWindowMissing(cheatsRef)) {
      try {
        cheatsRef.focus();
      } catch (err) {
        log("Cheats focus failed", err);
      }
    }
  }

  function getWindowStatus() {
    if (resumeRef && resumeRef.closed) resumeRef = null;
    if (cheatsRef && cheatsRef.closed) cheatsRef = null;
    return {
      resumeOpen: !!resumeRef,
      cheatsOpen: !!cheatsRef,
    };
  }

  function isPopupBlocked(ref) {
    return !ref;
  }

  // QA checklist:
  // - Popups blocked scenario -> error panel + manual open buttons
  // - Reuse behavior -> repeated click does not spawn duplicates
  // - Close one window -> reopen only missing window
  // - Role locking validation -> wrong route redirects
  // - Drag to monitors once -> Chrome remembers positions
  window.WarRoomManager = {
    openWarRoom,
    openResumeWindow,
    openCheatWindow,
    focusExistingWindows,
    getWindowStatus,
    isPopupBlocked,
    constants: {
      DEFAULT_PRIMARY_LEFT,
      DEFAULT_TOP,
      DEFAULT_MONITOR_WIDTH,
      DEFAULT_PRIMARY_WIDTH,
      DEFAULT_PRIMARY_HEIGHT,
      DEFAULT_PORTRAIT_WIDTH,
      DEFAULT_PORTRAIT_HEIGHT,
      DEFAULT_RIGHT_LEFT,
    },
  };
})();
