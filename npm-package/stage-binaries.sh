#!/usr/bin/env bash
# Stage the prebuilt release binaries into the five npm platform packages.
#
#   ./stage-binaries.sh --artifacts <dir>   # the release archives + checksums, as published
#   ./stage-binaries.sh --local <binary>    # one locally built uncomment, host platform only
#
# The archives are the *published* ones: the files attached to the GitHub release
# and hashed into uncomment_<version>_checksums.txt. Every archive is verified
# against that file before anything is unpacked. Re-building a binary here instead
# would ship bytes the release checksums do not cover.
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
INVOCATION_DIR="$PWD"
LICENSE_FILE="$PACKAGE_DIR/../LICENSE"

VERSION="$(node -p "require('$PACKAGE_DIR/package.json').version")"

# platform-package-dir:release-triple
TARGETS=(
  "darwin-arm64:aarch64-apple-darwin"
  "darwin-x64:x86_64-apple-darwin"
  "linux-arm64-gnu:aarch64-unknown-linux-gnu"
  "linux-x64-gnu:x86_64-unknown-linux-gnu"
  "win32-x64:x86_64-pc-windows-gnu"
)

usage() {
  echo "usage: $0 --artifacts <dir> | --local <path-to-uncomment>" >&2
  exit 2
}

MODE=""
ARG=""
case "${1:-}" in
--artifacts | --local)
  MODE="$1"
  ARG="${2:-}"
  [[ -n "$ARG" ]] || usage
  ;;
*) usage ;;
esac

# Resolve the caller's path against the directory the script was invoked from,
# before anything changes directory.
[[ "$ARG" == /* ]] || ARG="$INVOCATION_DIR/$ARG"

# Every platform package and every optionalDependencies pin must carry the
# umbrella's version, or the umbrella would install binaries from another release.
check_versions() {
  node - "$PACKAGE_DIR" "$VERSION" "${TARGETS[@]}" <<'JS'
const path = require("node:path");
const [root, version, ...targets] = process.argv.slice(2);
const umbrella = require(path.join(root, "package.json"));
const pins = umbrella.optionalDependencies || {};
const errors = [];
const names = new Set();
for (const target of targets) {
  const dir = target.split(":")[0];
  const pkg = require(path.join(root, "platforms", dir, "package.json"));
  names.add(pkg.name);
  if (pkg.version !== version) errors.push(`${pkg.name} is ${pkg.version}, expected ${version}`);
  if (pins[pkg.name] !== version) errors.push(`optionalDependencies pins ${pkg.name}@${pins[pkg.name]}, expected ${version}`);
}
for (const name of Object.keys(pins)) {
  if (!names.has(name)) errors.push(`optionalDependencies names ${name}, which has no platform package`);
}
if (errors.length > 0) {
  console.error(errors.map((e) => `error: ${e}`).join("\n"));
  process.exit(1);
}
JS
}

sha256_check() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum -c -
  else
    shasum -a 256 -c -
  fi
}

verify_checksums() {
  local archive_dir="$1"
  local manifest="$archive_dir/uncomment_${VERSION}_checksums.txt"
  [[ -f "$manifest" ]] || {
    echo "error: missing checksum manifest $manifest" >&2
    return 1
  }
  local target triple archive line
  for target in "${TARGETS[@]}"; do
    triple="${target##*:}"
    if [[ "$triple" == *windows* ]]; then archive="uncomment-$triple.zip"; else archive="uncomment-$triple.tar.gz"; fi
    line="$(awk -v name="$archive" '$2 == name || $2 == "*" name { print; exit }' "$manifest")"
    [[ -n "$line" ]] || {
      echo "error: $manifest lists no checksum for $archive" >&2
      return 1
    }
    (cd "$archive_dir" && sha256_check <<<"$line" >/dev/null) || {
      echo "error: $archive does not match $manifest" >&2
      return 1
    }
  done
  echo "  ✓ every archive matches uncomment_${VERSION}_checksums.txt"
}

prepare_dest() {
  local name="$1"
  local dest="$PACKAGE_DIR/platforms/$name/bin"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp "$LICENSE_FILE" "$PACKAGE_DIR/platforms/$name/LICENSE"
  echo "$dest"
}

stage_from_archive() {
  local name="$1" triple="$2" archive_dir="$3"
  local dest
  dest="$(prepare_dest "$name")"

  if [[ "$triple" == *windows* ]]; then
    local archive="$archive_dir/uncomment-$triple.zip"
    unzip -q -o "$archive" uncomment.exe -d "$dest"
    [[ -f "$dest/uncomment.exe" ]] || {
      echo "error: $archive contained no uncomment.exe" >&2
      return 1
    }
  else
    local archive="$archive_dir/uncomment-$triple.tar.gz"
    tar xzf "$archive" -C "$dest" uncomment
    [[ -x "$dest/uncomment" ]] || {
      echo "error: $archive contained no executable uncomment" >&2
      return 1
    }
  fi
  echo "  ✓ $name ← uncomment-$triple"
}

check_versions

if [[ "$MODE" == "--artifacts" ]]; then
  [[ -d "$ARG" ]] || {
    echo "error: not a directory: $ARG" >&2
    exit 1
  }
  ARCHIVE_DIR="$(cd "$ARG" && pwd)"
  echo "Staging uncomment $VERSION binaries from $ARCHIVE_DIR"
  verify_checksums "$ARCHIVE_DIR"
  for target in "${TARGETS[@]}"; do
    stage_from_archive "${target%%:*}" "${target##*:}" "$ARCHIVE_DIR"
  done
  exit 0
fi

# --local: one binary, for testing the packaging end to end without a release.
[[ -x "$ARG" ]] || {
  echo "error: not an executable: $ARG" >&2
  exit 1
}
case "$(uname -s)/$(uname -m)" in
Darwin/arm64) name="darwin-arm64" ;;
Darwin/x86_64) name="darwin-x64" ;;
Linux/aarch64) name="linux-arm64-gnu" ;;
Linux/x86_64) name="linux-x64-gnu" ;;
*)
  echo "error: --local has no platform package for $(uname -s)/$(uname -m)" >&2
  exit 1
  ;;
esac
dest="$(prepare_dest "$name")"
cp "$ARG" "$dest/uncomment"
chmod +x "$dest/uncomment"
echo "  ✓ $name ← $ARG (local build; host platform only)"
