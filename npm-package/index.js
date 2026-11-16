"use strict";

// Resolves the native `uncomment` binary for this host.
//
// Two sources, in order:
//
// 1. The platform package. Each of the five packages listed under
//    `optionalDependencies` ships exactly one prebuilt binary, and npm installs
//    only the one whose `os`/`cpu`/`libc` match the host. No network is needed
//    beyond the registry, so this works in sandboxes and offline mirrors, and
//    the registry's integrity hashes cover the binary.
// 2. The download fallback. When no platform package is present (optional
//    dependencies were skipped, or the host has no package, such as musl Linux
//    or Windows arm64), `install.js` fetches the release archive from GitHub,
//    verifies it against the release checksums and places the binary in `bin/`.

const fs = require("node:fs");
const path = require("node:path");

// One entry per release target. `libc` only matters on Linux: the Linux
// binaries are glibc-linked and fail to start on musl.
const PLATFORM_PACKAGES = [
  { pkg: "@polylint/uncomment-darwin-arm64", platform: "darwin", arch: "arm64", libc: null },
  { pkg: "@polylint/uncomment-darwin-x64", platform: "darwin", arch: "x64", libc: null },
  { pkg: "@polylint/uncomment-linux-arm64-gnu", platform: "linux", arch: "arm64", libc: "glibc" },
  { pkg: "@polylint/uncomment-linux-x64-gnu", platform: "linux", arch: "x64", libc: "glibc" },
  { pkg: "@polylint/uncomment-win32-x64", platform: "win32", arch: "x64", libc: null },
];

const IS_WINDOWS = process.platform === "win32";

// Name of the binary inside a platform package's bin/ directory.
const PLATFORM_BINARY_NAME = IS_WINDOWS ? "uncomment.exe" : "uncomment";

// Where the download fallback puts the binary. It sits beside the launcher stub
// (bin/uncomment) under a distinct name so extraction never overwrites the stub.
const DOWNLOADED_BINARY_PATH = path.join(__dirname, "bin", IS_WINDOWS ? "uncomment.exe" : "uncomment-bin");

/**
 * Report whether this Linux host runs glibc or musl.
 *
 * `process.report.getReport().header.glibcVersionRuntime` is present only when
 * the running Node was linked against glibc; checking it inline keeps this
 * package free of a libc-detection dependency.
 */
function detectLibc() {
  if (process.platform !== "linux") return null;
  try {
    const report = typeof process.report?.getReport === "function" ? process.report.getReport() : null;
    if (report && report.header && report.header.glibcVersionRuntime) return "glibc";
    if (report) return "musl";
  } catch {
    // Fall through to the default below.
  }
  return "glibc";
}

/** The platform packages that could serve this host. */
function candidatePackages() {
  const libc = detectLibc();
  return PLATFORM_PACKAGES.filter(
    (entry) =>
      entry.platform === process.platform &&
      entry.arch === process.arch &&
      (entry.libc === null || entry.libc === libc),
  ).map((entry) => entry.pkg);
}

/** Absolute path of the binary from an installed platform package, or `null`. */
function resolvePlatformBinary() {
  for (const pkg of candidatePackages()) {
    let packageJson;
    try {
      packageJson = require.resolve(`${pkg}/package.json`);
    } catch {
      continue;
    }
    const candidate = path.join(path.dirname(packageJson), "bin", PLATFORM_BINARY_NAME);
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

/** Absolute path of the binary the download fallback placed, or `null`. */
function resolveDownloadedBinary() {
  return fs.existsSync(DOWNLOADED_BINARY_PATH) ? DOWNLOADED_BINARY_PATH : null;
}

/** The binary to run: the platform package first, then the downloaded one. */
function resolveBinaryPath() {
  return resolvePlatformBinary() ?? resolveDownloadedBinary();
}

/** Explain why no binary was found and how to get one. */
function missingBinaryMessage() {
  const libc = detectLibc();
  const host = `${process.platform}/${process.arch}${libc ? ` (${libc})` : ""}`;
  const expected = candidatePackages();
  const source = expected.length === 0
    ? `No platform package is published for ${host}, and the download fallback did not install a binary.`
    : `The platform package for ${host} (${expected.join(", ")}) is not installed, ` +
      "and the download fallback did not install a binary.";

  return [
    `uncomment: the native binary is missing. ${source}`,
    "",
    "Reinstall with optional dependencies enabled (the platform package needs no download):",
    "  npm i -g @polylint/uncomment",
    "",
    "If the install ran with --ignore-scripts or without network access, the fallback",
    "download was skipped. Otherwise install from source: cargo install uncomment",
  ].join("\n");
}

module.exports = {
  DOWNLOADED_BINARY_PATH,
  PLATFORM_PACKAGES,
  candidatePackages,
  missingBinaryMessage,
  resolveBinaryPath,
  resolveDownloadedBinary,
  resolvePlatformBinary,
};
