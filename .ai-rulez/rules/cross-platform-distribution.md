---
type: Decision
title: Cross Platform Distribution
x-ai-rulez:
  kind: rule
  id: cross-platform-distribution
  metadata:
    priority: high
---

## Cross-Platform Distribution

uncomment is distributed across multiple package ecosystems. All distribution channels must be kept consistent and functional.

### Distribution Channels

- **crates.io**: Published via `cargo publish`. Primary source of truth for the Rust binary.
- **npm** (package: `@polylint/uncomment`, bin `uncomment`; formerly `uncomment-cli`): Umbrella package in `npm-package/` that pins one platform package per release target as an exact-version `optionalDependency`: `@polylint/uncomment-darwin-arm64`, `-darwin-x64`, `-linux-arm64-gnu`, `-linux-x64-gnu` (`libc: ["glibc"]`) and `-win32-x64`, each in `npm-package/platforms/<platform>/` carrying one binary in `bin/`.
- **PyPI** (package: `uncomment`): `pip-package/build_wheels.py` builds one platform wheel per release target with the binary embedded (`macosx_11_0_arm64`, `macosx_10_12_x86_64`, `manylinux_2_28_aarch64`, `manylinux_2_28_x86_64`, `win_amd64`; the manylinux floor is read from the binary's glibc symbols) plus a pure-Python `py3-none-any` fallback wheel. No sdist.
- **Homebrew**: Formula in the `polylint/homebrew-tap` repo (`Formula/uncomment.rb`, `brew install polylint/tap/uncomment`), rendered from `scripts/publish/uncomment.rb.tmpl` by `xberg-io/actions/publish-homebrew-source-formulas` in the `publish-homebrew-formula` job and pushed by the polylint GitHub App; `homebrew-bottles` and `publish-homebrew-bottles` then build bottles and merge the bottle DSL.
- **Scoop**: Manifest in the `polylint/scoop-bucket` repo (`bucket/uncomment.json`), rendered from `scripts/publish/uncomment.json.tmpl` by the `publish-scoop-manifest` job.
- **GitHub Actions (release automation)**: Cross-platform binary builds and release automation live in `.github/workflows/publish.yaml` (a native per-platform build matrix — goreleaser was removed in v3.1.0).
- **GitHub Action (consumer-facing)**: Root `action.yml` is a composite action (`polylint/uncomment@vX.Y.Z`) that downloads and checksum-verifies the release asset matching the runner's OS/arch, caches it with `actions/cache`, and runs `uncomment`/`uncomment lint`. Install logic lives in `scripts/gh-action-*.sh`; annotations come from `problem-matcher.json`. Tested by `.github/workflows/action.yml`.

### Binary Resolution Order (npm and PyPI)

1. **Platform package first.** The npm launcher (`npm-package/index.js`) runs the binary from the installed platform package; the Python console script (`uncomment/cli.py`) runs the binary bundled in the platform wheel. This path needs no network beyond the registry, so it works in sandboxes and offline mirrors.
2. **Download as the fallback only.** When no platform package is present (optional dependencies skipped, or a host with no package, such as musl Linux or Windows arm64), npm's `postinstall` (`install.js`) downloads and checksum-verifies the release archive; it is a no-op when a platform package resolved, and a failed download never fails `npm install` (the launcher then prints the install hint). On PyPI, pip picks the fallback wheel only when no platform wheel matches; it carries `uncomment/downloader.py` and is the only wheel that depends on `certifi`.

### Release Workflow

1. Update version numbers in all manifests (see version-synchronization rule)
2. Commit and tag with `vX.Y.Z`
3. Push the tag to trigger `.github/workflows/publish.yaml`
4. The workflow creates a draft release, builds binaries for all platforms natively
   (macOS on `macos-26`/`macos-26-intel`, Windows cross-compiled with mingw-w64,
   Linux in `manylinux_2_28` containers), uploads them plus a checksums file, then
   promotes the draft to a published release
5. npm, PyPI, Homebrew, and Scoop publish from the finalized GitHub Release assets. The npm and PyPI jobs download the archives and `uncomment_<version>_checksums.txt`, verify every archive before unpacking it, and never rebuild a binary. npm publishes every platform package before the umbrella, so the umbrella never points at platform packages that do not exist; PyPI uploads the five platform wheels and the fallback wheel
6. npm publishes through trusted publishing (OIDC, `--provenance`, no environment) and PyPI through `pypa/gh-action-pypi-publish` with the `pypi` environment; both trust `polylint/uncomment` + `publish.yaml`. A new npm platform package needs one manual first publish before its trusted publisher can be configured: `scripts/npm-stage-from-release.sh <version> <outdir>` packs them from an existing release without publishing

### Guidelines

- Always test both resolution paths when modifying `npm-package/` or `pip-package/`: the platform package or wheel (no download) and the download fallback. `scripts/tests/npm-launcher.test.mjs` and `scripts/tests/test_distribution_packages.py` encode the contract
- Adding or removing a release target changes the platform package list in `npm-package/package.json`, `npm-package/index.js`, `npm-package/platforms/`, `npm-package/stage-binaries.sh`, `pip-package/build_wheels.py`, and the archive patterns in `publish.yaml` together
- Ensure binaries are built for: `x86_64-unknown-linux-gnu`, `aarch64-unknown-linux-gnu`, `x86_64-apple-darwin`, `aarch64-apple-darwin`, `x86_64-pc-windows-gnu`
- Every tree-sitter grammar is compiled into the binary by `tree-sitter-language-pack`. Nothing is fetched, built or cached at runtime, so the binary is large and self-contained, and a release asset needs no companion grammar download
- RC releases use `vX.Y.Z-rc.N` tags (note: PyPI uses `X.Y.ZrcN` format without hyphens)
