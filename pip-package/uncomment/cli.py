"""
CLI entry point for uncomment

The binary comes from one of two places, in order:

1. The platform wheel. Each published platform wheel carries the prebuilt
   binary under ``uncomment/bin/``, so nothing is downloaded and the binary is
   covered by the wheel hash pip already verified.
2. The download fallback. The pure-Python ``py3-none-any`` wheel, which pip
   picks only when no platform wheel matches the host, carries no binary;
   ``downloader.py`` fetches the release archive on first run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_BIN_DIR = Path(__file__).resolve().parent / "bin"
_BINARY_NAME = "uncomment.exe" if os.name == "nt" else "uncomment"


def bundled_binary() -> Path | None:
    """Return the binary shipped in this platform wheel, or ``None`` for the fallback wheel."""
    candidate = _BIN_DIR / _BINARY_NAME
    return candidate if candidate.is_file() else None


def _run(binary: Path, args: list[str]) -> None:
    argv = [str(binary), *args]
    if os.name == "nt":
        # Windows has no exec that keeps Ctrl-C and job control intact, so spawn
        # and forward the exit status instead.
        try:
            completed = subprocess.run(argv, check=False)
        except OSError as exc:
            print(f"uncomment: failed to run {binary}: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        raise SystemExit(completed.returncode)

    # execv replaces this process, so the exit status and any terminating signal
    # reach the caller exactly as from the standalone binary.
    try:
        os.execv(str(binary), argv)
    except OSError as exc:
        print(f"uncomment: failed to exec {binary}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def main():
    """Main entry point for the CLI."""
    args = sys.argv[1:]
    binary = bundled_binary()
    if binary is not None:
        _run(binary, args)
        return

    from .downloader import run_uncomment

    run_uncomment(args)


if __name__ == "__main__":
    main()
