#!/usr/bin/env python3
"""Build the wheels for the ``uncomment`` distribution.

    python build_wheels.py --artifacts <dir> [--out dist] [--only <triple>|fallback]
    python build_wheels.py --local <path-to-uncomment> [--out dist]

``--artifacts`` points at the release archives exactly as published, together
with ``uncomment_<version>_checksums.txt``; every archive is verified against it
before it is unpacked. Building a binary here instead would ship bytes the
release checksums do not describe.

``--local`` stages a single locally built binary for the host platform, which is
how the packaging is exercised without a release.

Besides one platform wheel per release target, this builds a pure-Python
``py3-none-any`` fallback wheel. pip ranks platform wheels above ``any``, so the
fallback is only chosen on a host no platform wheel matches; it then downloads
the release binary on first run (``uncomment/downloader.py``).

Requires ``build`` and ``hatchling`` on the interpreter running this script.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

# The earliest macOS each Rust target supports by default; the release binaries
# carry exactly these as their minimum OS version. Claiming an older one would
# let pip install a binary the host cannot load.
MACOS_ARM64_MIN = "11_0"
MACOS_X86_64_MIN = "10_12"

# The Linux archives are built in manylinux_2_28 containers. The tag is read out
# of the binary's GLIBC_2.x symbol versions; this is only the fallback when the
# binary references none.
MANYLINUX_FALLBACK_MINOR = 28

GLIBC_SYMBOL = re.compile(rb"GLIBC_2\.(\d+)")


@dataclass(frozen=True)
class Target:
    """One release triple and how it maps onto a wheel platform tag."""

    triple: str
    archive_suffix: str
    binary_name: str

    @property
    def archive_name(self) -> str:
        return f"uncomment-{self.triple}.{self.archive_suffix}"


TARGETS = (
    Target("aarch64-apple-darwin", "tar.gz", "uncomment"),
    Target("x86_64-apple-darwin", "tar.gz", "uncomment"),
    Target("aarch64-unknown-linux-gnu", "tar.gz", "uncomment"),
    Target("x86_64-unknown-linux-gnu", "tar.gz", "uncomment"),
    Target("x86_64-pc-windows-gnu", "zip", "uncomment.exe"),
)

TAG_VARIABLE = "UNCOMMENT_WHEEL_TAG"
BINARY_VARIABLE = "UNCOMMENT_WHEEL_BINARY"


def project_version() -> str:
    """The version declared in pyproject.toml."""
    text = (PACKAGE_DIR / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    if match is None:
        message = "pyproject.toml has no [project] version"
        raise SystemExit(message)
    return match.group(1)


def release_version(python_version: str) -> str:
    """The release (tag) version for a PEP 440 version: ``3.2.0rc1`` -> ``3.2.0-rc.1``."""
    match = re.fullmatch(r"(\d+\.\d+\.\d+)rc(\d+)", python_version)
    return f"{match[1]}-rc.{match[2]}" if match else python_version


def required_glibc_minor(binary: Path) -> int:
    """Highest ``GLIBC_2.x`` symbol version the binary references.

    Read from the binary rather than hardcoded from the builder image, so the tag
    never claims an older glibc than the binary actually needs.
    """
    versions = [int(match) for match in GLIBC_SYMBOL.findall(binary.read_bytes())]
    return max(versions) if versions else MANYLINUX_FALLBACK_MINOR


def platform_tag(target: Target, binary: Path) -> str:
    """The PEP 425 platform tag for a target's wheel."""
    if target.triple == "aarch64-apple-darwin":
        return f"macosx_{MACOS_ARM64_MIN}_arm64"
    if target.triple == "x86_64-apple-darwin":
        return f"macosx_{MACOS_X86_64_MIN}_x86_64"
    if target.triple == "x86_64-pc-windows-gnu":
        return "win_amd64"
    machine = "aarch64" if target.triple.startswith("aarch64") else "x86_64"
    return f"manylinux_2_{required_glibc_minor(binary)}_{machine}"


def verify_checksum(archive: Path, manifest: Path) -> None:
    """Fail unless ``archive`` matches its line in the release checksum manifest."""
    expected = None
    for line in manifest.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == archive.name:
            expected = fields[0]
            break
    if expected is None:
        message = f"{manifest.name} lists no checksum for {archive.name}"
        raise SystemExit(message)
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        message = f"checksum mismatch for {archive.name}: expected {expected}, got {actual}"
        raise SystemExit(message)


def extract_binary(archive: Path, target: Target, destination: Path) -> Path:
    """Unpack the binary out of a published release archive."""
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / target.binary_name

    if target.archive_suffix == "zip":
        with zipfile.ZipFile(archive) as zf:
            try:
                source = zf.open(target.binary_name)
            except KeyError:
                message = f"{archive} contains no {target.binary_name}"
                raise SystemExit(message) from None
            with source, output.open("wb") as sink:
                shutil.copyfileobj(source, sink)
    else:
        with tarfile.open(archive, "r:gz") as tf:
            member = tf.extractfile(target.binary_name) if target.binary_name in tf.getnames() else None
            if member is None:
                message = f"{archive} contains no {target.binary_name}"
                raise SystemExit(message)
            with member, output.open("wb") as sink:
                shutil.copyfileobj(member, sink)

    output.chmod(0o755)
    return output


def force_executable_bit(wheel: Path, member_prefix: str = "uncomment/bin/") -> None:
    """Rewrite the wheel so the bundled binary unpacks with mode 0755.

    pip honours the mode stored in each entry's external attributes. Setting it
    here rather than trusting the build backend to preserve the source file's
    mode means a wheel can never install a binary that is not executable. RECORD
    hashes file contents, which are untouched, so the wheel stays consistent.
    """
    rewritten = wheel.with_suffix(".whl.tmp")
    with zipfile.ZipFile(wheel) as source, zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as sink:
        for info in source.infolist():
            data = source.read(info.filename)
            new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            if info.filename.startswith(member_prefix):
                new_info.external_attr = (0o100755 << 16) | (info.external_attr & 0xFFFF)
            sink.writestr(new_info, data)
    rewritten.replace(wheel)


def run_build(out_dir: Path, env_overrides: dict[str, str]) -> Path:
    """Invoke the wheel backend once and return the wheel it produced."""
    before = set(out_dir.glob("*.whl"))
    # Clear both hook variables first, so a stale value in the ambient
    # environment cannot turn the fallback wheel into a platform one.
    env = dict(os.environ)
    env.pop(TAG_VARIABLE, None)
    env.pop(BINARY_VARIABLE, None)
    env.update(env_overrides)

    subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(out_dir)],
        cwd=PACKAGE_DIR,
        check=True,
        env=env,
    )

    produced = set(out_dir.glob("*.whl")) - before
    if len(produced) != 1:
        message = f"expected exactly one new wheel, got {sorted(p.name for p in produced)}"
        raise SystemExit(message)
    return produced.pop()


def build_platform_wheel(target: Target, binary: Path, out_dir: Path) -> Path:
    tag = platform_tag(target, binary)
    wheel = run_build(out_dir, {TAG_VARIABLE: tag, BINARY_VARIABLE: str(binary)})
    force_executable_bit(wheel)
    print(f"  ✓ {target.triple:28} → {wheel.name}")
    return wheel


def build_fallback_wheel(out_dir: Path) -> Path:
    """The ``py3-none-any`` wheel that downloads the binary on first run."""
    wheel = run_build(out_dir, {})
    print(f"  ✓ {'fallback (downloader)':28} → {wheel.name}")
    return wheel


def host_target() -> Target:
    machine = platform.machine().lower()
    system = platform.system()
    triples = {
        ("Darwin", "arm64"): "aarch64-apple-darwin",
        ("Darwin", "x86_64"): "x86_64-apple-darwin",
        ("Linux", "aarch64"): "aarch64-unknown-linux-gnu",
        ("Linux", "x86_64"): "x86_64-unknown-linux-gnu",
        ("Windows", "amd64"): "x86_64-pc-windows-gnu",
    }
    triple = triples.get((system, machine))
    if triple is None:
        message = f"--local has no target mapping for {system}/{machine}"
        raise SystemExit(message)
    return next(target for target in TARGETS if target.triple == triple)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--artifacts", type=Path, help="directory holding the published release archives")
    source.add_argument("--local", type=Path, help="a locally built uncomment binary (host platform only)")
    parser.add_argument("--out", type=Path, default=PACKAGE_DIR / "dist", help="output directory")
    parser.add_argument("--only", help="build just this triple (or 'fallback')")
    parser.add_argument("--no-fallback", action="store_true", help="skip the py3-none-any fallback wheel")
    args = parser.parse_args()

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    version = project_version()
    print(f"Building uncomment {version} wheels into {out_dir}")

    with tempfile.TemporaryDirectory() as staging_root:
        staging = Path(staging_root)

        if args.local is not None:
            target = host_target()
            binary = staging / target.triple / target.binary_name
            binary.parent.mkdir(parents=True)
            shutil.copy2(args.local, binary)
            binary.chmod(0o755)
            build_platform_wheel(target, binary, out_dir)
        else:
            artifacts = args.artifacts.resolve()
            manifest = artifacts / f"uncomment_{release_version(version)}_checksums.txt"
            if not manifest.is_file():
                message = f"missing checksum manifest: {manifest}"
                raise SystemExit(message)
            for target in TARGETS:
                if args.only and args.only != target.triple:
                    continue
                archive = artifacts / target.archive_name
                if not archive.is_file():
                    message = f"missing release archive: {archive}"
                    raise SystemExit(message)
                verify_checksum(archive, manifest)
                binary = extract_binary(archive, target, staging / target.triple)
                build_platform_wheel(target, binary, out_dir)

        if not args.no_fallback and args.only in (None, "fallback"):
            build_fallback_wheel(out_dir)

    print(f"\nWheels in {out_dir}:")
    for wheel in sorted(out_dir.glob("*.whl")):
        print(f"  {wheel.name}")


if __name__ == "__main__":
    main()
