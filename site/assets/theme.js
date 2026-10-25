(function () {
  "use strict";

  const key = "orcasql-workbench.theme";
  const modes = new Set(["system", "light", "dark"]);
  const labels = { system: "跟随系统", light: "浅色", dark: "深色" };
  const nextModes = { system: "light", light: "dark", dark: "system" };
  let storage;
  let currentMode;

  function storageError(error) {
    return error instanceof DOMException &&
      (error.name === "SecurityError" || error.name === "QuotaExceededError");
  }

  function readMode() {
    try {
      storage = window.localStorage;
      const saved = storage.getItem(key);
      if (saved === null) return "system";
      if (modes.has(saved)) return saved;
      console.warn("Ignoring an unsupported site theme preference.");
      return "system";
    } catch (error) {
      if (!storageError(error)) throw error;
      console.warn("The site theme preference could not be read.", error);
      return "system";
    }
  }

  function applyMode(mode) {
    currentMode = mode;
    if (mode === "system") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", mode);
    }
    for (const control of document.querySelectorAll("[data-theme-control]")) {
      control.value = mode;
      const label = `主题：${labels[mode]}；切换为${labels[nextModes[mode]]}`;
      control.setAttribute("aria-label", label);
      control.setAttribute("title", label);
    }
  }

  function showStorageWarning(visible) {
    for (const status of document.querySelectorAll("[data-theme-status]")) {
      status.hidden = !visible;
    }
  }

  function initialize() {
    applyMode(currentMode);
    for (const control of document.querySelectorAll("[data-theme-control]")) {
      control.addEventListener("click", function () {
        const mode = nextModes[currentMode];
        applyMode(mode);
        try {
          storage = window.localStorage;
          if (mode === "system") {
            storage.removeItem(key);
          } else {
            storage.setItem(key, mode);
          }
          showStorageWarning(false);
        } catch (error) {
          if (!storageError(error)) throw error;
          console.warn("The site theme preference could not be saved.", error);
          showStorageWarning(true);
        }
      });
    }
    for (const settings of document.querySelectorAll("[data-theme-settings]")) {
      settings.hidden = false;
    }
  }

  applyMode(readMode());
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }

  window.addEventListener("storage", function (event) {
    if (event.storageArea !== storage || (event.key !== key && event.key !== null)) return;
    applyMode(readMode());
    showStorageWarning(false);
  });
}());
