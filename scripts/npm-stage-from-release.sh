#!/usr/bin/env bash
# Pack the npm platform packages for an existing GitHub release, without publishing.
#
#   scripts/npm-stage-from-release.sh <version> <outdir>
#
# npm trusted publishing can only be configured for a package that already exists,
# so each new @polylint/uncomment-<platform> package needs one manual first publish.
# This script produces those tarballs: it downloads the release archives of
# polylint/uncomment v<version>, verifies them against the release checksums,
# stages each platform package from a scratch copy of npm-package/ (the working
# tree is not touched) and runs `npm pack` into <outdir>. Publish them by hand:
#
#   for tgz in <outdir>/*.tgz; do npm publish "$tgz" --access public; done
set -euo pipefail

REPO="polylint/uncomment"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

[[ $# -eq 2 ]] || {
  echo "usage: $0 <version> <outdir>" >&2
  exit 2
}
VERSION="${1#v}"
OUTDIR="$2"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]] || {
  echo "error: not a release version: $1" >&2
  exit 2
}
mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/uncomment-npm-stage.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

ASSETS=(
  "uncomment-aarch64-apple-darwin.tar.gz"
  "uncomment-x86_64-apple-darwin.tar.gz"
  "uncomment-aarch64-unknown-linux-gnu.tar.gz"
  "uncomment-x86_64-unknown-linux-gnu.tar.gz"
  "uncomment-x86_64-pc-windows-gnu.zip"
  "uncomment_${VERSION}_checksums.txt"
)

mkdir "$WORK/artifacts"
echo "Downloading $REPO v$VERSION release archives"
for asset in "${ASSETS[@]}"; do
  curl -fsSL --proto '=https' --tlsv1.2 --retry 3 \
    -o "$WORK/artifacts/$asset" \
    "https://github.com/$REPO/releases/download/v$VERSION/$asset"
done

# A scratch copy of the packaging, pinned to the requested version, so the
# bootstrap can pack an older release from a newer checkout.
mkdir "$WORK/repo"
cp "$ROOT/LICENSE" "$WORK/repo/LICENSE"
cp -R "$ROOT/npm-package" "$WORK/repo/npm-package"
rm -rf "$WORK/repo/npm-package/node_modules" "$WORK/repo/npm-package/platforms"/*/bin
node - "$WORK/repo/npm-package" "$VERSION" <<'JS'
const fs = require("node:fs");
const path = require("node:path");
const [root, version] = process.argv.slice(2);
const write = (file, mutate) => {
  const pkg = JSON.parse(fs.readFileSync(file, "utf8"));
  mutate(pkg);
  fs.writeFileSync(file, `${JSON.stringify(pkg, null, 2)}\n`);
};
write(path.join(root, "package.json"), (pkg) => {
  pkg.version = version;
  for (const name of Object.keys(pkg.optionalDependencies)) pkg.optionalDependencies[name] = version;
});
for (const dir of fs.readdirSync(path.join(root, "platforms"))) {
  write(path.join(root, "platforms", dir, "package.json"), (pkg) => {
    pkg.version = version;
  });
}
JS

"$WORK/repo/npm-package/stage-binaries.sh" --artifacts "$WORK/artifacts"

echo "Packing into $OUTDIR"
for dir in "$WORK/repo/npm-package/platforms"/*/; do
  (cd "$dir" && npm pack --silent --pack-destination "$OUTDIR" >/dev/null)
done
ls -l "$OUTDIR"/*.tgz
