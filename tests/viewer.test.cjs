const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "docs", "arkdb", "viewer", "init.js"), "utf8");
const runtime = fs.readFileSync(path.join(__dirname, "..", "docs", "arkdb", "viewer", "viewer.js"), "utf8");
const key = "orcasql-workbench.theme";

function element(attributes = {}) {
  const values = new Map(Object.entries(attributes));
  const events = new Map();
  return {
    values, events, textContent: "", hidden: true, children: [],
    setAttribute: (name, value) => values.set(name, value),
    getAttribute: name => values.get(name) ?? null,
    hasAttribute: name => values.has(name),
    removeAttribute: name => values.delete(name),
    addEventListener: (name, callback) => events.set(name, callback),
    appendChild(child) { this.children.push(child); },
    querySelectorAll() { return this.children; },
  };
}

function boot(options = {}) {
  const values = options.values ?? new Map();
  const writes = [];
  const warnings = [];
  const errors = [];
  const root = element();
  const status = element();
  const button = element();
  const label = element();
  const node = element({ "data-node-id": "host", "data-node-label": "宿主应用" });
  const svg = element({ role: "img", focusable: "false" });
  svg.children.push(node);
  const surfaces = [element({ inert: "" }), element({ inert: "" }), element({ inert: "" })];
  const events = new Map();
  const documentEvents = new Map();
  const media = {
    matches: options.dark ?? true,
    addEventListener(name, callback) { this.change = callback; },
  };
  const storage = {
    getItem(name) {
      if (options.readError) throw options.readError;
      return values.get(name) ?? null;
    },
    setItem(name, value) {
      if (options.writeError) throw options.writeError;
      writes.push(["set", name, value]);
      values.set(name, value);
    },
    removeItem(name) {
      if (options.writeError) throw options.writeError;
      writes.push(["remove", name]);
      values.delete(name);
    },
  };
  const document = {
    documentElement: root,
    getElementById: () => status,
    addEventListener: (name, callback) => documentEvents.set(name, callback),
    querySelectorAll: () => surfaces,
    querySelector: selector => selector === ".diagram-container svg" ? svg : null,
    createElementNS: () => element(),
  };
  const window = {
    location: { search: options.search ?? "", hash: "" },
    localStorage: storage,
    matchMedia: () => media,
    addEventListener: (name, callback) => events.set(name, callback),
    dispatchEvent() {},
  };
  vm.runInNewContext(source, {
    window, document, DOMException, URLSearchParams, Event,
    console: { warn: (...args) => warnings.push(args), error: (...args) => errors.push(args) },
  }, { filename: "viewer/init.js", timeout: 1000 });
  window.ArkDBViewer.bindTheme(button, label);
  return { viewer: window.ArkDBViewer, values, writes, warnings, errors, root, status,
    button, label, node, svg, surfaces, events, documentEvents, media, storage };
}

test("viewer shares the site preference and cycles system/light/dark without touching other keys", () => {
  const state = boot({ values: new Map([["other", "keep"]]) });
  assert.equal(state.root.getAttribute("data-theme-mode"), "system");
  assert.equal(state.root.getAttribute("data-theme"), "dark");
  assert.deepEqual(state.writes, []);
  state.viewer.theme.toggle();
  assert.equal(state.values.get(key), "light");
  state.viewer.theme.toggle();
  assert.equal(state.values.get(key), "dark");
  state.viewer.theme.toggle();
  assert.equal(state.values.has(key), false);
  assert.equal(state.values.get("other"), "keep");
  assert.equal(state.button.getAttribute("aria-pressed"), null);
  assert.match(state.button.getAttribute("aria-label"), /跟随系统/);
});

test("viewer follows parent-page storage changes and OS changes only in system mode", () => {
  const state = boot();
  state.values.set(key, "light");
  state.events.get("storage")({ key, storageArea: state.storage });
  assert.equal(state.root.getAttribute("data-theme"), "light");
  state.media.matches = true;
  state.media.change();
  assert.equal(state.root.getAttribute("data-theme"), "light");
  state.values.delete(key);
  state.events.get("storage")({ key, storageArea: state.storage });
  assert.equal(state.root.getAttribute("data-theme-mode"), "system");
  state.media.matches = false;
  state.media.change();
  assert.equal(state.root.getAttribute("data-theme"), "light");
});

test("explicit preview theme does not overwrite the saved site preference", () => {
  const state = boot({ search: "?theme=light", values: new Map([[key, "dark"]]) });
  assert.equal(state.root.getAttribute("data-theme"), "light");
  assert.equal(state.values.get(key), "dark");
  assert.deepEqual(state.writes, []);
});

test("expected storage failures are visible while unexpected errors are not swallowed", () => {
  const state = boot({ writeError: new DOMException("blocked", "SecurityError") });
  state.viewer.theme.toggle();
  assert.equal(state.root.getAttribute("data-theme"), "light");
  assert.equal(state.status.hidden, false);
  assert.match(state.status.textContent, /未能保存/);
  assert.equal(state.warnings.length, 1);
  assert.throws(() => boot({ readError: new Error("unexpected") }), /unexpected/);
});

test("controls are activated only after initialization and become inert on failure", () => {
  const state = boot();
  assert.ok(state.surfaces.every(surface => surface.hasAttribute("inert")));
  state.viewer.prepare();
  assert.equal(state.svg.getAttribute("role"), "group");
  assert.equal(state.node.getAttribute("role"), "button");
  state.viewer.ready();
  assert.equal(state.root.getAttribute("data-viewer-ready"), "true");
  assert.ok(state.surfaces.every(surface => !surface.hasAttribute("inert")));
  state.events.get("error")({ error: new Error("runtime failed") });
  assert.equal(state.root.getAttribute("data-viewer-failed"), "true");
  assert.ok(state.surfaces.every(surface => surface.hasAttribute("inert")));
  assert.match(state.status.textContent, /静态架构图/);
  assert.equal(state.errors.length, 1);
});

test("downloaded SVG retains image semantics without live keyboard controls", () => {
  const state = boot();
  state.viewer.prepare();
  state.viewer.cleanExport(state.svg);
  assert.equal(state.svg.getAttribute("role"), "img");
  assert.equal(state.svg.getAttribute("focusable"), "false");
  for (const name of ["role", "tabindex", "aria-pressed", "aria-label"]) {
    assert.equal(state.node.getAttribute(name), null);
  }
  assert.match(state.svg.children.at(-1).textContent, /cursor:default/);
});

for (const canonicalStateClean of [true, false]) {
  test(`export cleanup bridge preserves the ${canonicalStateClean} canonical-state result`, () => {
    const bridge = runtime.match(/function cleanExportClone\(clone\) \{[\s\S]*?\n\s*\}/);
    assert.ok(bridge, "The live export cleanup bridge must be exercised.");
    const clone = {};
    const calls = [];
    const context = {
      clone,
      cleanViewerClone(value) {
        assert.equal(value, clone);
        calls.push("viewer");
        return canonicalStateClean;
      },
      window: {
        ArkDBViewer: {
          cleanExport(value) {
            assert.equal(value, clone);
            calls.push("accessibility");
          },
        },
      },
    };
    const result = vm.runInNewContext(bridge[0] + "\ncleanExportClone(clone);", context,
      { filename: "viewer/export-cleanup", timeout: 1000 });
    assert.deepEqual(calls, ["viewer", "accessibility"]);
    assert.equal(result, canonicalStateClean);
  });
}
