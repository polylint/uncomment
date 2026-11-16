// The npm launcher contract: the matching platform package wins and needs no
// download; the postinstall download is only a fallback; a failed fallback never
// fails the install, and the launcher then explains how to get the binary.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "../..");
const packageDir = path.join(root, "npm-package");
const { PLATFORM_PACKAGES } = await import(path.join(packageDir, "index.js"));

const hostPackage = PLATFORM_PACKAGES.find(
  (entry) => entry.platform === process.platform && entry.arch === process.arch,
);
const posixHost = process.platform !== "win32" && hostPackage !== undefined;

// A preload that makes every HTTPS request fail and records that one was made,
// so the tests never touch the network.
const OFFLINE_PRELOAD = `
const https = require("node:https");
const { EventEmitter } = require("node:events");
https.get = (url) => {
  require("node:fs").writeFileSync(process.env.UNCOMMENT_TEST_NETWORK_LOG, String(url));
  const req = new EventEmitter();
  req.setTimeout = () => req;
  req.destroy = () => {};
  process.nextTick(() => req.emit("error", new Error("network disabled in test")));
  return req;
};
`;

const scratch = [];
test.after(() => {
  for (const dir of scratch) fs.rmSync(dir, { recursive: true, force: true });
});

function installLayout() {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), "uncomment-npm-test-"));
  scratch.push(project);
  const umbrella = path.join(project, "node_modules/@polylint/uncomment");
  fs.mkdirSync(path.join(umbrella, "bin"), { recursive: true });
  for (const file of ["package.json", "index.js", "install.js", "bin/uncomment"]) {
    fs.copyFileSync(path.join(packageDir, file), path.join(umbrella, file));
  }
  const preload = path.join(project, "offline.cjs");
  fs.writeFileSync(preload, OFFLINE_PRELOAD);
  return { project, umbrella, preload, networkLog: path.join(project, "network.log") };
}

function fakeBinary(file, label) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `#!/bin/sh\necho "${label} $*"\nexit 7\n`);
  fs.chmodSync(file, 0o755);
}

function addPlatformPackage(layout) {
  const dir = path.join(layout.project, "node_modules", hostPackage.pkg);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "package.json"), JSON.stringify({ name: hostPackage.pkg, version: "0.0.0" }));
  fakeBinary(path.join(dir, "bin/uncomment"), "platform");
}

function run(layout, script, args = []) {
  return spawnSync(process.execPath, ["--require", layout.preload, path.join(layout.umbrella, script), ...args], {
    encoding: "utf8",
    env: { ...process.env, UNCOMMENT_TEST_NETWORK_LOG: layout.networkLog },
  });
}

test("every release target has exactly one platform package and an exact pin", () => {
  const umbrella = JSON.parse(fs.readFileSync(path.join(packageDir, "package.json"), "utf8"));
  const names = PLATFORM_PACKAGES.map((entry) => entry.pkg).toSorted();
  assert.deepEqual(Object.keys(umbrella.optionalDependencies).toSorted(), names);
  for (const entry of PLATFORM_PACKAGES) {
    const dir = path.join(packageDir, "platforms", entry.pkg.replace("@polylint/uncomment-", ""));
    const manifest = JSON.parse(fs.readFileSync(path.join(dir, "package.json"), "utf8"));
    assert.equal(manifest.name, entry.pkg);
    assert.equal(manifest.version, umbrella.version);
    assert.equal(umbrella.optionalDependencies[entry.pkg], umbrella.version);
    assert.deepEqual(manifest.os, [entry.platform]);
    assert.deepEqual(manifest.cpu, [entry.arch]);
    assert.deepEqual(manifest.libc, entry.libc ? [entry.libc] : undefined);
    assert.ok(manifest.files.includes("bin/"));
  }
});

test("platform package present: postinstall makes no request and the launcher runs it", { skip: !posixHost }, () => {
  const layout = installLayout();
  addPlatformPackage(layout);

  const install = run(layout, "install.js");
  assert.equal(install.status, 0, install.stderr);
  assert.equal(install.stdout + install.stderr, "");
  assert.equal(fs.existsSync(layout.networkLog), false);
  assert.equal(fs.existsSync(path.join(layout.umbrella, "bin/uncomment-bin")), false);

  const launched = run(layout, "bin/uncomment", ["--version"]);
  assert.equal(launched.stdout, "platform --version\n");
  assert.equal(launched.status, 7);
});

test(
  "no platform package: postinstall tries the download, and a failure does not fail the install",
  { skip: !posixHost },
  () => {
    const layout = installLayout();

    const install = run(layout, "install.js");
    assert.equal(install.status, 0, install.stderr);
    assert.match(
      fs.readFileSync(layout.networkLog, "utf8"),
      /^https:\/\/github\.com\/polylint\/uncomment\/releases\/download\//u,
    );
    assert.match(install.stderr, /fallback download failed: network disabled in test/u);

    const launched = run(layout, "bin/uncomment", ["--version"]);
    assert.equal(launched.status, 1);
    assert.match(launched.stderr, /the native binary is missing/u);
    assert.match(launched.stderr, new RegExp(hostPackage.pkg.replace("/", "\\/"), "u"));
  },
);

test("no platform package: the launcher runs the binary the download fallback placed", { skip: !posixHost }, () => {
  const layout = installLayout();
  fakeBinary(path.join(layout.umbrella, "bin/uncomment-bin"), "downloaded");

  const launched = run(layout, "bin/uncomment", ["scan"]);
  assert.equal(launched.stdout, "downloaded scan\n");
  assert.equal(launched.status, 7);
});

test("the platform package wins over a previously downloaded binary", { skip: !posixHost }, () => {
  const layout = installLayout();
  addPlatformPackage(layout);
  fakeBinary(path.join(layout.umbrella, "bin/uncomment-bin"), "downloaded");

  const launched = run(layout, "bin/uncomment", []);
  assert.equal(launched.stdout, "platform \n");
});
