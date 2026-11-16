"""Hatchling hooks that turn the wheel into a platform wheel or the download fallback.

``build_wheels.py`` invokes the backend once per release target with
``UNCOMMENT_WHEEL_TAG`` and ``UNCOMMENT_WHEEL_BINARY`` set: the build hook
stamps the wheel with that platform tag and embeds the binary, and the metadata
hook declares no dependencies. With neither set, the result is the pure-Python
``py3-none-any`` fallback wheel, which downloads the binary on first run and so
depends on ``certifi``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.metadata.plugin.interface import MetadataHookInterface

TAG_VARIABLE = "UNCOMMENT_WHEEL_TAG"
BINARY_VARIABLE = "UNCOMMENT_WHEEL_BINARY"

FALLBACK_DEPENDENCIES = ["certifi>=2026.10.23"]


def _platform_build() -> tuple[str, str] | None:
    tag = os.environ.get(TAG_VARIABLE)
    binary = os.environ.get(BINARY_VARIABLE)
    if not tag and not binary:
        return None
    if not (tag and binary):
        message = f"{TAG_VARIABLE} and {BINARY_VARIABLE} must be set together"
        raise ValueError(message)
    return tag, binary


class CustomMetadataHook(MetadataHookInterface):
    """Declare the downloader's dependency only on the fallback wheel."""

    PLUGIN_NAME = "custom"

    def update(self, metadata: dict[str, Any]) -> None:
        metadata["dependencies"] = [] if _platform_build() else list(FALLBACK_DEPENDENCIES)


class CustomBuildHook(BuildHookInterface):
    """Stamp the wheel with a platform tag and embed the prebuilt binary."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        platform_build = _platform_build()
        if platform_build is None:
            return
        tag, binary = platform_build

        if not Path(binary).is_file():
            message = f"{BINARY_VARIABLE} does not exist: {binary}"
            raise FileNotFoundError(message)

        target_name = "uncomment.exe" if tag.startswith("win") else "uncomment"

        build_data["pure_python"] = False
        build_data["infer_tag"] = False
        build_data["tag"] = f"py3-none-{tag}"
        build_data["force_include"][binary] = f"uncomment/bin/{target_name}"
