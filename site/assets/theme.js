(function () {
  "use strict";

  const key = "orcasql-workbench.theme";
  const modes = new Set(["system", "light", "dark"]);
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
    }
  }

  function showStorageWarning(visible) {
    for (const status of document.querySelectorAll("[data-theme-status]")) {
      status.hidden = !visible;
    }
  }

  function initialize() {
    for (const control of document.querySelectorAll("[data-theme-control]")) {
      control.value = currentMode;
      control.addEventListener("change", function () {
        const mode = control.value;
        if (!modes.has(mode)) {
          console.warn("Ignoring an unsupported site theme selection.");
          control.value = currentMode;
          return;
        }
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
