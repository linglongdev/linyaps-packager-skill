import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "build_from_project.py"

spec = importlib.util.spec_from_file_location("build_from_project", MODULE_PATH)
build_from_project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_from_project)


class CommandRequirementTests(unittest.TestCase):
    def test_require_command_reports_package_hint(self):
        with mock.patch.object(build_from_project.shutil, "which", return_value=None):
            with self.assertRaisesRegex(
                RuntimeError,
                r"Install the `linglong-bin` package first",
            ):
                build_from_project.require_command(
                    "ll-cli",
                    "linglong-bin",
                    "query remote base/runtime versions",
                )

    def test_latest_remote_ref_stops_when_ll_cli_is_missing(self):
        with mock.patch.object(build_from_project.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, r"`ll-cli` is required"):
                build_from_project.latest_remote_ref("org.deepin.base/25.2.1")


class DeleteSafetyTests(unittest.TestCase):
    def test_delete_guard_allows_paths_inside_workdir(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workdir = Path(tempdir)
            managed = workdir / "nested"
            managed.mkdir()
            build_from_project.ensure_managed_delete_path(managed, workdir)

    def test_delete_guard_blocks_paths_outside_workdir(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workdir = Path(tempdir)
            outside = Path(tempfile.mkdtemp())
            try:
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"Deleting user data requires explicit confirmation",
                ):
                    build_from_project.ensure_managed_delete_path(outside, workdir)
            finally:
                outside.rmdir()


if __name__ == "__main__":
    unittest.main()
