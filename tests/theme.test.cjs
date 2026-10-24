const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "site", "assets", "theme.js"), "utf8");
const key = "orcasql-workbench.theme";

function boot(options = {}) {
  const values = options.values ?? new Map();
  const warnings = [];
  const writes = [];
  const root = new Map();
  const documentEvents = new Map();
  const windowEvents = new Map();
  const controlEvents = new Map();
  const control = {
    value: "system",
    addEventListener: (name, callback) => controlEvents.set(name, callback),
  };
  const settings = { hidden: true };
  const status = { hidden: true };
  let ready = !options.loading;
  const storage = {
    getItem(name) {
      if (options.readError) throw options.readError;
      return values.get(name) ?? null;
    },
    setItem(name, value) {
      if (options.writeError) throw options.writeError;
      values.set(name, value);
      writes.push(["set", name, value]);
    },
    removeItem(name) {
      if (options.removeError) throw options.removeError;
      values.delete(name);
      writes.push(["remove", name]);
    },
  };
  const document = {
    readyState: ready ? "complete" : "loading",
    documentElement: {
      setAttribute: (name, value) => root.set(name, value),
      removeAttribute: name => root.delete(name),
    },
    querySelectorAll(selector) {
      if (!ready) return [];
      return {
        "[data-theme-control]": [control],
        "[data-theme-settings]": [settings],
        "[data-theme-status]": [status],
      }[selector];
    },
    addEventListener: (name, callback) => documentEvents.set(name, callback),
  };
  const window = {
    get localStorage() {
      if (options.accessError) throw options.accessError;
      return storage;
    },
    addEventListener: (name, callback) => windowEvents.set(name, callback),
  };
  vm.runInNewContext(source, {
    document, window, DOMException,
    console: { warn: (...arguments) => warnings.push(arguments) },
  }, { filename: "theme.js", timeout: 1000 });
  return {
    values, root, warnings, writes, control, settings, status, storage,
    ready() {
      ready = true;
      documentEvents.get("DOMContentLoaded")();
    },
    choose(mode) {
      control.value = mode;
      controlEvents.get("change")();
    },
    storageEvent(event) {
      windowEvents.get("storage")(event);
    },
  };
}

test("defaults to CSS system mode without writing storage", () => {
  const state = boot();
  assert.equal(state.root.has("data-theme"), false);
  assert.equal(state.control.value, "system");
  assert.equal(state.settings.hidden, false);
  assert.deepEqual(state.writes, []);
  assert.deepEqual(state.warnings, []);
});

test("restores a saved theme before the body is parsed", () => {
  for (const mode of ["light", "dark"]) {
    const state = boot({ loading: true, values: new Map([[key, mode]]) });
    assert.equal(state.root.get("data-theme"), mode);
    assert.equal(state.settings.hidden, true);
    state.ready();
    assert.equal(state.control.value, mode);
    assert.equal(state.settings.hidden, false);
  }
});

test("manual choices persist across page loads without touching unrelated keys", () => {
  const values = new Map([["unrelated", "keep"]]);
  const first = boot({ values });
  first.choose("dark");
  assert.equal(first.root.get("data-theme"), "dark");
  assert.equal(values.get(key), "dark");
  assert.equal(boot({ values }).root.get("data-theme"), "dark");
  first.choose("light");
  assert.equal(boot({ values }).root.get("data-theme"), "light");
  assert.equal(values.get("unrelated"), "keep");
  assert.equal(first.status.hidden, true);
});

test("system mode removes only the theme key and returns control to CSS", () => {
  const state = boot({ values: new Map([[key, "dark"], ["unrelated", "keep"]]) });
  state.choose("system");
  assert.equal(state.root.has("data-theme"), false);
  assert.equal(state.values.has(key), false);
  assert.equal(state.values.get("unrelated"), "keep");
  assert.equal(boot({ values: state.values }).control.value, "system");
  assert.deepEqual(state.writes, [["remove", key]]);
});

test("a stored system preference is supported without fixing an effective color", () => {
  const state = boot({ values: new Map([[key, "system"]]) });
  assert.equal(state.root.has("data-theme"), false);
  assert.equal(state.control.value, "system");
  assert.equal(state.warnings.length, 0);
});

test("invalid stored values fall back to system with a warning", () => {
  for (const value of ["", "unknown", "__proto__", "constructor", "<script>"]) {
    const state = boot({ values: new Map([[key, value]]) });
    assert.equal(state.root.has("data-theme"), false);
    assert.equal(state.control.value, "system");
    assert.equal(state.warnings.length, 1);
    assert.deepEqual(state.writes, []);
  }
});

test("blocked storage access keeps controls usable and reports an unsaved choice", () => {
  const state = boot({ accessError: new DOMException("Blocked", "SecurityError") });
  assert.equal(state.root.has("data-theme"), false);
  assert.equal(state.settings.hidden, false);
  state.choose("dark");
  assert.equal(state.root.get("data-theme"), "dark");
  assert.equal(state.status.hidden, false);
  assert.equal(state.warnings.length, 2);
});

test("a failed read falls back to system and a later choice can still be saved", () => {
  const state = boot({ readError: new DOMException("Blocked", "SecurityError") });
  assert.equal(state.control.value, "system");
  state.choose("light");
  assert.equal(state.root.get("data-theme"), "light");
  assert.equal(state.values.get(key), "light");
  assert.equal(state.status.hidden, true);
});

test("quota failure applies the current-page theme and successful retry clears the warning", () => {
  const options = { writeError: new DOMException("Full", "QuotaExceededError") };
  const state = boot(options);
  state.choose("dark");
  assert.equal(state.root.get("data-theme"), "dark");
  assert.equal(state.values.has(key), false);
  assert.equal(state.status.hidden, false);
  options.writeError = null;
  state.choose("light");
  assert.equal(state.values.get(key), "light");
  assert.equal(state.status.hidden, true);
});

test("failed removal does not pretend the saved preference was cleared", () => {
  const state = boot({
    values: new Map([[key, "dark"]]),
    removeError: new DOMException("Blocked", "SecurityError"),
  });
  state.choose("system");
  assert.equal(state.root.has("data-theme"), false);
  assert.equal(state.values.get(key), "dark");
  assert.equal(state.status.hidden, false);
});

test("storage changes and clearing synchronize other tabs without writing back", () => {
  const state = boot({ values: new Map([[key, "light"]]) });
  state.values.set(key, "dark");
  state.storageEvent({ storageArea: state.storage, key });
  assert.equal(state.root.get("data-theme"), "dark");
  assert.equal(state.control.value, "dark");
  state.values.delete(key);
  state.storageEvent({ storageArea: state.storage, key: null });
  assert.equal(state.root.has("data-theme"), false);
  assert.equal(state.control.value, "system");
  assert.deepEqual(state.writes, []);
});

test("unrelated keys and sessionStorage events do not change the theme", () => {
  const state = boot({ values: new Map([[key, "dark"]]) });
  state.values.set(key, "light");
  state.storageEvent({ storageArea: state.storage, key: "unrelated" });
  state.storageEvent({ storageArea: {}, key });
  assert.equal(state.root.get("data-theme"), "dark");
  assert.equal(state.control.value, "dark");
});

test("an invalid selection is rejected rather than persisted", () => {
  const state = boot({ values: new Map([[key, "light"]]) });
  state.choose("invalid");
  assert.equal(state.root.get("data-theme"), "light");
  assert.equal(state.control.value, "light");
  assert.equal(state.values.get(key), "light");
  assert.equal(state.warnings.length, 1);
  assert.deepEqual(state.writes, []);
});

test("unexpected programming errors are not swallowed as storage failures", () => {
  assert.throws(() => boot({ readError: new Error("Unexpected read bug") }), /Unexpected read bug/);
  const state = boot({ writeError: new Error("Unexpected write bug") });
  assert.throws(() => state.choose("dark"), /Unexpected write bug/);
  assert.deepEqual(state.warnings, []);
});
