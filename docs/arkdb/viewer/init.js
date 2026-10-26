(function () {
  "use strict";

  const root = document.documentElement;
  const key = "orcasql-workbench.theme";
  const modes = new Set(["system", "light", "dark"]);
  const labels = { system: "跟随系统", light: "浅色", dark: "深色" };
  const nextModes = { system: "light", light: "dark", dark: "system" };
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const parameters = new URLSearchParams(window.location.search);
  let storage;
  let button;
  let label;
  let statusMessage = "";
  let override = parameters.get("theme");
  if (override !== null && override !== "light" && override !== "dark") {
    console.warn("Ignoring an unsupported architecture viewer theme parameter.");
    override = null;
  }

  function status(message) {
    statusMessage = message;
    const node = document.getElementById("viewer-status");
    if (node) {
      node.textContent = message;
      node.hidden = !message;
    }
  }

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
      console.warn("The architecture viewer theme preference could not be read.", error);
      status("无法读取主题偏好，当前视图仍可使用。");
      return "system";
    }
  }

  let mode;

  function apply() {
    const resolved = mode === "system" ? (media.matches ? "dark" : "light") : mode;
    root.setAttribute("data-theme", resolved);
    root.setAttribute("data-theme-mode", mode);
    if (button && label) {
      label.textContent = labels[mode];
      const description = `主题：${labels[mode]}；切换为${labels[nextModes[mode]]}`;
      button.setAttribute("aria-label", description);
      button.setAttribute("title", description + "（T）");
      button.removeAttribute("aria-pressed");
    }
  }

  function toggle() {
    if (root.hasAttribute("data-viewer-failed")) return;
    override = null;
    mode = nextModes[mode];
    apply();
    try {
      storage = window.localStorage;
      if (mode === "system") storage.removeItem(key);
      else storage.setItem(key, mode);
      status("");
    } catch (error) {
      if (!storageError(error)) throw error;
      console.warn("The architecture viewer theme preference could not be saved.", error);
      status("主题已切换，但浏览器未能保存此偏好。");
    }
  }

  function fail(error) {
    console.error("The architecture viewer failed; the static diagram remains available.", error);
    root.removeAttribute("data-present");
    root.setAttribute("data-viewer-failed", "true");
    for (const surface of document.querySelectorAll(".toolbar, .diagram-container, .reader-rail")) {
      surface.setAttribute("inert", "");
    }
    status("交互视图未能加载，已显示静态架构图。");
  }

  window.addEventListener("error", function (event) {
    if (event.error || (event.target && event.target.tagName === "SCRIPT")) {
      fail(event.error || new Error("A viewer script could not be loaded."));
    }
  }, true);
  window.addEventListener("unhandledrejection", function (event) {
    fail(event.reason);
  });
  window.addEventListener("storage", function (event) {
    if (override || (event.key !== key && event.key !== null)) return;
    if (event.storageArea && storage && event.storageArea !== storage) return;
    mode = readMode();
    apply();
  });
  media.addEventListener("change", function () {
    if (mode === "system") apply();
  });
  document.addEventListener("DOMContentLoaded", function () {
    status(statusMessage);
  }, { once: true });

  window.ArkDBViewer = {
    theme: { toggle },
    bindTheme(control, text) {
      if (!control || !text) throw new Error("Architecture viewer theme controls are missing.");
      button = control;
      label = text;
      button.addEventListener("click", toggle);
      apply();
    },
    prepare() {
      const svg = document.querySelector(".diagram-container svg");
      if (!svg) throw new Error("The architecture diagram is missing.");
      svg.setAttribute("role", "group");
      for (const node of svg.querySelectorAll("[data-node-id]")) {
        node.setAttribute("tabindex", "0");
        node.setAttribute("role", "button");
        node.setAttribute("aria-pressed", "false");
        node.setAttribute("aria-label", "聚焦 " + node.getAttribute("data-node-label"));
      }
    },
    ready() {
      if (root.hasAttribute("data-viewer-failed")) return;
      root.setAttribute("data-viewer-ready", "true");
      for (const surface of document.querySelectorAll(".toolbar, .diagram-container, .reader-rail")) {
        surface.removeAttribute("inert");
      }
      window.dispatchEvent(new Event("resize"));
      const selected = document.querySelector(".diagram-container [data-focus-selected]");
      if (selected && window.location.hash) selected.focus({ preventScroll: true });
    },
    cleanExport(svg) {
      svg.setAttribute("role", "img");
      svg.setAttribute("focusable", "false");
      const attributes = ["tabindex", "accesskey", "aria-pressed", "aria-expanded",
        "aria-controls", "aria-haspopup", "aria-keyshortcuts"];
      for (const node of svg.querySelectorAll("*")) {
        const interactive = node.getAttribute("role") === "button";
        if (interactive) node.removeAttribute("role");
        if (interactive || node.hasAttribute("data-node-id")) node.removeAttribute("aria-label");
        for (const attribute of attributes) node.removeAttribute(attribute);
      }
      const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
      style.textContent = "svg [data-node-id],svg [data-node-id]:hover," +
        "svg [data-node-id]:focus-visible{cursor:default!important;filter:none!important}";
      svg.appendChild(style);
    },
  };

  if (parameters.get("present") === "1") root.setAttribute("data-present", "true");
  mode = override || readMode();
  apply();
  root.setAttribute("data-viewer-started", "true");
}());
