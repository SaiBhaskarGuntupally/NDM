(() => {
  const ROUTES = {
    resume: "/war-room/resume",
    cheats: "/war-room/cheats",
  };

  function init({ role, windowSide }) {
    const storedRole = localStorage.getItem("ndm_war_room_role");
    if (storedRole && storedRole !== role && ROUTES[storedRole]) {
      window.location.replace(ROUTES[storedRole]);
      return;
    }

    localStorage.setItem("ndm_war_room_role", role);
    localStorage.setItem("ndm_war_room_window", windowSide);
  }

  window.WarRoomPages = { init };
})();
