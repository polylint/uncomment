"""The npm and PyPI packaging contract: platform packages first, download as the fallback."""

import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import tomllib
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/publish.yaml"
PIP_PACKAGE = ROOT / "pip-package"

PLATFORM_DIRS = ["darwin-arm64", "darwin-x64", "linux-arm64-gnu", "linux-x64-gnu", "win32-x64"]
TRIPLES = [
    "aarch64-apple-darwin",
    "x86_64-apple-darwin",
    "aarch64-unknown-linux-gnu",
    "x86_64-unknown-linux-gnu",
    "x86_64-pc-windows-gnu",
]


def load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through sys.modules on older Pythons.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def job_block(name: str) -> str:
    text = WORKFLOW.read_text()
    return text.split(f"  {name}:\n", 1)[1].split("\n  publish", 1)[0]


class VersionSynchronizationTests(unittest.TestCase):
    def test_every_published_manifest_carries_the_cargo_version(self) -> None:
        version = tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]["version"]
        umbrella = json.loads((ROOT / "npm-package/package.json").read_text())
        self.assertEqual(umbrella["version"], version)
        self.assertEqual(
            umbrella["optionalDependencies"],
            {f"@polylint/uncomment-{name}": version for name in PLATFORM_DIRS},
        )
        for name in PLATFORM_DIRS:
            manifest = json.loads((ROOT / f"npm-package/platforms/{name}/package.json").read_text())
            self.assertEqual(manifest["name"], f"@polylint/uncomment-{name}")
            self.assertEqual(manifest["version"], version)
        self.assertEqual(sorted(p.name for p in (ROOT / "npm-package/platforms").iterdir()), sorted(PLATFORM_DIRS))
        project = tomllib.loads((PIP_PACKAGE / "pyproject.toml").read_text())["project"]
        self.assertEqual(project["version"], version)
        self.assertIn('__version__ = "' + version + '"', (PIP_PACKAGE / "uncomment/__init__.py").read_text())

    def test_stage_script_and_wheel_builder_cover_every_release_target(self) -> None:
        stage = (ROOT / "npm-package/stage-binaries.sh").read_text()
        for name, triple in zip(PLATFORM_DIRS, TRIPLES, strict=True):
            self.assertIn(f'"{name}:{triple}"', stage)
        builder = load_module("build_wheels", PIP_PACKAGE / "build_wheels.py")
        self.assertEqual(sorted(target.triple for target in builder.TARGETS), sorted(TRIPLES))


class WheelBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = load_module("build_wheels", PIP_PACKAGE / "build_wheels.py")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def target(self, triple: str) -> object:
        return next(target for target in self.builder.TARGETS if target.triple == triple)

    def test_platform_tags_match_what_the_binaries_require(self) -> None:
        binary = self.root / "uncomment"
        binary.write_bytes(b"\0GLIBC_2.17\0GLIBC_2.28\0GLIBC_2.25\0")
        expected = {
            "aarch64-apple-darwin": "macosx_11_0_arm64",
            "x86_64-apple-darwin": "macosx_10_12_x86_64",
            "aarch64-unknown-linux-gnu": "manylinux_2_28_aarch64",
            "x86_64-unknown-linux-gnu": "manylinux_2_28_x86_64",
            "x86_64-pc-windows-gnu": "win_amd64",
        }
        for triple, tag in expected.items():
            with self.subTest(triple=triple):
                self.assertEqual(self.builder.platform_tag(self.target(triple), binary), tag)

    def test_linux_tag_follows_the_highest_glibc_symbol(self) -> None:
        binary = self.root / "uncomment"
        binary.write_bytes(b"GLIBC_2.34 GLIBC_2.2")
        tag = self.builder.platform_tag(self.target("x86_64-unknown-linux-gnu"), binary)
        self.assertEqual(tag, "manylinux_2_34_x86_64")

    def test_archives_must_match_the_release_checksums(self) -> None:
        archive = self.root / "uncomment-x86_64-apple-darwin.tar.gz"
        archive.write_bytes(b"archive")
        manifest = self.root / "uncomment_1.2.3_checksums.txt"
        manifest.write_text(f"{hashlib.sha256(b'archive').hexdigest()}  {archive.name}\n")
        self.builder.verify_checksum(archive, manifest)
        archive.write_bytes(b"tampered")
        with self.assertRaisesRegex(SystemExit, "checksum mismatch"):
            self.builder.verify_checksum(archive, manifest)
        manifest.write_text("")
        with self.assertRaisesRegex(SystemExit, "lists no checksum"):
            self.builder.verify_checksum(archive, manifest)

    def test_release_version_maps_pep440_candidates_to_tags(self) -> None:
        self.assertEqual(self.builder.release_version("3.11.1"), "3.11.1")
        self.assertEqual(self.builder.release_version("3.12.0rc2"), "3.12.0-rc.2")


@unittest.skipIf(importlib.util.find_spec("hatchling") is None, "hatchling is not installed")
class HatchHookTests(unittest.TestCase):
    def test_only_the_fallback_wheel_depends_on_certifi(self) -> None:
        hooks = load_module("hatch_build", PIP_PACKAGE / "hatch_build.py")
        hook = hooks.CustomMetadataHook.__new__(hooks.CustomMetadataHook)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(hooks.TAG_VARIABLE, None)
            os.environ.pop(hooks.BINARY_VARIABLE, None)
            metadata: dict = {}
            hook.update(metadata)
            self.assertEqual(metadata["dependencies"], ["certifi>=2026.10.23"])
        with mock.patch.dict(os.environ, {hooks.TAG_VARIABLE: "win_amd64", hooks.BINARY_VARIABLE: "x"}):
            metadata = {}
            hook.update(metadata)
            self.assertEqual(metadata["dependencies"], [])


class PythonLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(PIP_PACKAGE))
        self.addCleanup(sys.path.remove, str(PIP_PACKAGE))
        for name in [name for name in sys.modules if name == "uncomment" or name.startswith("uncomment.")]:
            del sys.modules[name]
        # The downloader imports certifi, which only the fallback wheel installs.
        self.enterContext(mock.patch.dict(sys.modules, {"certifi": types.SimpleNamespace(where=lambda: None)}))
        from uncomment import cli

        self.cli = cli
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.bin_dir = Path(self.temporary.name)
        self.enterContext(mock.patch.object(cli, "_BIN_DIR", self.bin_dir))
        self.enterContext(mock.patch.object(sys, "argv", ["uncomment", "--version"]))

    def test_platform_wheel_execs_the_bundled_binary_without_the_downloader(self) -> None:
        binary = self.bin_dir / self.cli._BINARY_NAME
        binary.write_text("")
        with (
            mock.patch("os.execv") as execv,
            mock.patch("subprocess.run") as run,
            mock.patch("uncomment.downloader.run_uncomment") as download,
        ):
            run.return_value = types.SimpleNamespace(returncode=0)
            try:
                self.cli.main()
            except SystemExit as exit_:
                self.assertEqual(exit_.code, 0)
        download.assert_not_called()
        called = execv.call_args or run.call_args
        self.assertIn(str(binary), str(called))
        self.assertIn("--version", str(called))

    def test_fallback_wheel_hands_off_to_the_downloader(self) -> None:
        with mock.patch("uncomment.downloader.run_uncomment") as download, mock.patch("os.execv") as execv:
            self.cli.main()
        download.assert_called_once_with(["--version"])
        execv.assert_not_called()


class PublishWorkflowTests(unittest.TestCase):
    def test_npm_publishes_every_platform_package_before_the_umbrella(self) -> None:
        block = job_block("publish_npm")
        self.assertIn("id-token: write", block)
        self.assertIn("unset NODE_AUTH_TOKEN", block)
        self.assertIn("./npm-package/stage-binaries.sh --artifacts artifacts", block)
        self.assertIn("--provenance", block)
        self.assertNotIn("environment:", block)
        loop = block.index('for dir in "${platforms[@]}"; do')
        umbrella = block.index("publish_one npm-package")
        self.assertLess(loop, umbrella)
        self.assertIn(".optionalDependencies | length", block)

    def test_pypi_builds_platform_wheels_plus_fallback_without_sdist(self) -> None:
        block = job_block("publish_pypi")
        self.assertIn("environment: pypi", block)
        self.assertIn("id-token: write", block)
        self.assertIn("python pip-package/build_wheels.py --artifacts artifacts --out pip-package/dist", block)
        self.assertIn('[ "$count" -eq 6 ]', block)
        self.assertIn("pypa/gh-action-pypi-publish@", block)
        self.assertNotIn("python -m build\n", block)

    def test_registry_jobs_download_the_release_archives_and_checksums(self) -> None:
        for name in ("publish_npm", "publish_pypi"):
            block = job_block(name)
            for pattern in (
                "uncomment-*-apple-darwin.tar.gz",
                "uncomment-*-linux-gnu.tar.gz",
                "uncomment-*-windows-gnu.zip",
                "uncomment_*_checksums.txt",
            ):
                with self.subTest(job=name, pattern=pattern):
                    self.assertIn(f"--pattern '{pattern}'", block)

    def test_meta_rejects_platform_package_version_drift(self) -> None:
        text = WORKFLOW.read_text()
        meta = text.split("  meta:\n", 1)[1].split("  create_release:\n", 1)[0]
        self.assertTrue(re.search(r"for manifest in npm-package/platforms/\*/package\.json", meta))
        self.assertIn(".optionalDependencies[$name]", meta)


if __name__ == "__main__":
    unittest.main()
