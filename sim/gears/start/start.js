// Start page of the simulator origin (ADR 0019, section 5).
// Sets GearsBot's defaults only if the browser has none yet, then opens the
// pinned GearsBot version with the same query string. Part of Checkermint's
// GearsBot packaging, GNU GPL v3 (see sim/gears/LICENSE).
(function () {
  try {
    if (!localStorage.getItem("LANG")) {
      localStorage.setItem("LANG", "de");
    }
    if (!localStorage.getItem("whatsNew")) {
      // GearsBot shows its English "What's New" dialog until this is set.
      localStorage.setItem("whatsNew", "99999999");
    }
  } catch (e) {
    // localStorage blocked: GearsBot starts in English, nothing else breaks.
  }
  location.replace("/v/__GEARS_VERSION__/index.html" + location.search);
})();
