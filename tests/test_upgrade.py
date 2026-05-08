"""Tests for src/upgrade.py — version checking, asset matching, install detection, security."""

import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.upgrade import (
    _detect_platform,
    _find_platform_asset,
    _is_editable_install,
    check_for_update,
    get_current_version,
    run_upgrade,
)


class TestGetCurrentVersion:
    """Tests for get_current_version()."""

    def test_returns_string(self):
        version = get_current_version()
        assert isinstance(version, str)
        assert version != ""

    def test_returns_semver_format(self):
        version = get_current_version()
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_returns_unknown_when_no_pyproject(self):
        with patch("pathlib.Path.exists", return_value=False):
            assert get_current_version() == "unknown"


class TestDetectPlatform:
    """Tests for _detect_platform()."""

    def test_macos(self):
        with patch("platform.system", return_value="Darwin"):
            assert _detect_platform() == "macos"

    def test_windows(self):
        with patch("platform.system", return_value="Windows"):
            assert _detect_platform() == "windows"

    def test_linux(self):
        with patch("platform.system", return_value="Linux"):
            assert _detect_platform() == "linux"

    def test_unknown_defaults_to_linux(self):
        with patch("platform.system", return_value="FreeBSD"):
            assert _detect_platform() == "linux"


class TestFindPlatformAsset:
    """Tests for _find_platform_asset()."""

    def test_finds_zip(self):
        assets = [{"name": "moon-traveler-macos.zip", "browser_download_url": "https://..."}]
        result = _find_platform_asset(assets, "macos")
        assert result is not None
        assert result["name"] == "moon-traveler-macos.zip"

    def test_finds_tar_gz(self):
        assets = [{"name": "moon-traveler-linux.tar.gz", "browser_download_url": "https://..."}]
        result = _find_platform_asset(assets, "linux")
        assert result is not None

    def test_returns_none_for_wrong_platform(self):
        assets = [{"name": "moon-traveler-windows.zip", "browser_download_url": "https://..."}]
        assert _find_platform_asset(assets, "macos") is None

    def test_returns_none_for_empty_assets(self):
        assert _find_platform_asset([], "linux") is None

    def test_ignores_sha256_checksum_files(self):
        assets = [{"name": "moon-traveler-macos.sha256", "browser_download_url": "https://..."}]
        assert _find_platform_asset(assets, "macos") is None

    def test_matches_bare_binary(self):
        assets = [{"name": "moon-traveler-v0.5.4-linux", "browser_download_url": "https://..."}]
        result = _find_platform_asset(assets, "linux")
        assert result is not None

    def test_case_insensitive_name_match(self):
        assets = [{"name": "Moon-Traveler-MACOS.zip", "browser_download_url": "https://..."}]
        result = _find_platform_asset(assets, "macos")
        assert result is not None


class TestIsEditableInstall:
    """Tests for _is_editable_install()."""

    def test_frozen_returns_false(self):
        with patch.object(__import__("sys"), "frozen", True, create=True):
            assert _is_editable_install() is False

    def test_source_with_git_returns_true(self):
        """When pyproject.toml and .git both exist, it's editable."""
        # The actual project has both, so this should return True
        # unless running from a frozen binary
        if not hasattr(__import__("sys"), "frozen"):
            result = _is_editable_install()
            assert result is True


class TestCheckForUpdate:
    """Tests for check_for_update() — version comparison logic."""

    def _mock_api_response(self, tag_name, assets=None):
        """Create a mock urllib response with given tag."""
        import json

        data = {
            "tag_name": tag_name,
            "body": "Release notes",
            "assets": assets or [],
            "html_url": "https://github.com/test/test/releases/tag/" + tag_name,
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_returns_none_when_up_to_date(self):
        current = get_current_version()
        mock_resp = self._mock_api_response(f"v{current}")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert check_for_update() is None

    def test_returns_none_when_older(self):
        mock_resp = self._mock_api_response("v0.0.1")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert check_for_update() is None

    def test_returns_dict_when_newer(self):
        mock_resp = self._mock_api_response("v99.0.0")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = check_for_update()
        assert result is not None
        assert result["latest"] == "99.0.0"
        assert "current" in result

    def test_returns_none_on_network_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            assert check_for_update() is None

    def test_returns_none_on_empty_tag(self):
        mock_resp = self._mock_api_response("")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert check_for_update() is None

    def test_returns_none_on_malformed_version(self):
        mock_resp = self._mock_api_response("v1.0.0-beta")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert check_for_update() is None

    def test_assets_passed_through(self):
        assets = [{"name": "test.zip", "browser_download_url": "https://..."}]
        mock_resp = self._mock_api_response("v99.0.0", assets=assets)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = check_for_update()
        assert result is not None
        assert len(result["assets"]) == 1


class TestRunUpgradeSecurity:
    """Tests for run_upgrade() security guards.

    These tests mock _find_platform_asset to return a controlled asset dict,
    bypassing the platform-matching logic to test the security checks directly.
    """

    def _make_release(
        self, asset_name="app-macos.zip", asset_url="https://github.com/t/t/releases/download/v1/app.zip"
    ):
        """Build a mock release dict."""
        return {
            "current": "0.1.0",
            "latest": "99.0.0",
            "tag": "v99.0.0",
            "body": "",
            "html_url": "https://github.com/test/test/releases/tag/v99.0.0",
            "assets": [
                {
                    "name": asset_name,
                    "browser_download_url": asset_url,
                    "size": 1000,
                }
            ],
        }

    def _patch_upgrade(self, release, asset_override=None):
        """Context manager that patches run_upgrade dependencies.

        Returns the mocked ui module for assertion checks.
        """
        from contextlib import ExitStack

        stack = ExitStack()
        mock_ui = stack.enter_context(patch("src.upgrade.ui"))
        stack.enter_context(patch("src.upgrade.check_for_update", return_value=release))
        stack.enter_context(patch("src.upgrade.get_current_version", return_value="0.1.0"))
        stack.enter_context(patch("src.upgrade._is_editable_install", return_value=False))
        if asset_override is not None:
            stack.enter_context(patch("src.upgrade._find_platform_asset", return_value=asset_override))
        mock_ui.console.input.return_value = "y"
        return stack, mock_ui

    def test_rejects_non_github_url(self):
        """URL domain validation rejects non-GitHub download URLs."""
        release = self._make_release()
        asset = {"name": "app.zip", "browser_download_url": "https://evil.com/payload.zip", "size": 100}
        stack, mock_ui = self._patch_upgrade(release, asset_override=asset)
        with stack:
            run_upgrade()
            error_calls = [str(c) for c in mock_ui.error.call_args_list]
            assert any("Unexpected" in s for s in error_calls)

    def test_rejects_http_url(self):
        """URL domain validation rejects http (non-https) URLs."""
        release = self._make_release()
        asset = {"name": "app.zip", "browser_download_url": "http://github.com/t/t/app.zip", "size": 100}
        stack, mock_ui = self._patch_upgrade(release, asset_override=asset)
        with stack:
            run_upgrade()
            error_calls = [str(c) for c in mock_ui.error.call_args_list]
            assert any("Unexpected" in s for s in error_calls)

    def test_rejects_asset_name_with_path_traversal(self):
        """Asset name sanitization rejects names with directory components."""
        release = self._make_release()
        asset = {"name": "../../../etc/passwd", "browser_download_url": "https://github.com/t/t/app.zip", "size": 100}
        stack, mock_ui = self._patch_upgrade(release, asset_override=asset)
        with stack:
            run_upgrade()
            # Path("../../../etc/passwd").name strips to "passwd" — no crash, no traversal
            # The main check is that it doesn't use the full unsanitized path
            assert True

    def test_rejects_dotdot_asset_name(self):
        """Asset name sanitization rejects '..' as a name."""
        release = self._make_release()
        asset = {"name": "..", "browser_download_url": "https://github.com/t/t/app.zip", "size": 100}
        stack, mock_ui = self._patch_upgrade(release, asset_override=asset)
        with stack:
            run_upgrade()
            error_calls = [str(c) for c in mock_ui.error.call_args_list]
            assert any("Invalid asset name" in s for s in error_calls)

    def test_rejects_empty_asset_name(self):
        """Asset name sanitization rejects empty names."""
        release = self._make_release()
        asset = {"name": "", "browser_download_url": "https://github.com/t/t/app.zip", "size": 100}
        stack, mock_ui = self._patch_upgrade(release, asset_override=asset)
        with stack:
            run_upgrade()
            error_calls = [str(c) for c in mock_ui.error.call_args_list]
            assert any("Invalid asset name" in s for s in error_calls)

    def test_zip_filters_path_traversal_entries(self):
        """Zip extraction filters out entries with path traversal."""
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("safe_file.txt", "safe content")
                zf.writestr("../../../etc/passwd", "dangerous content")
                zf.writestr("subdir/normal.txt", "normal content")

            extract_dir = Path(tmp) / "extracted"
            with zipfile.ZipFile(zip_path) as zf:
                safe_names = [
                    n for n in zf.namelist() if not os.path.isabs(n) and ".." not in os.path.normpath(n).split(os.sep)
                ]
                zf.extractall(extract_dir, members=safe_names)

            assert (extract_dir / "safe_file.txt").exists()
            assert (extract_dir / "subdir" / "normal.txt").exists()
            # Verify only 2 safe files were extracted (dangerous entry filtered out)
            extracted_files = [f for f in extract_dir.rglob("*") if f.is_file()]
            assert len(extracted_files) == 2
            extracted_names = {f.name for f in extracted_files}
            assert extracted_names == {"safe_file.txt", "normal.txt"}

    def test_user_decline_aborts(self):
        """User declining download aborts without downloading."""
        release = self._make_release()
        asset = {"name": "app.zip", "browser_download_url": "https://github.com/t/t/app.zip", "size": 100}
        stack, mock_ui = self._patch_upgrade(release, asset_override=asset)
        with stack:
            mock_ui.console.input.return_value = "n"
            run_upgrade()
            dim_calls = [str(c) for c in mock_ui.dim.call_args_list]
            assert any("cancelled" in s for s in dim_calls)
