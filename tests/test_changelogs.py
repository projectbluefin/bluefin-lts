"""
Unit tests for .github/changelogs.py

Run with: pytest tests/test_changelogs.py -v
"""

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Ensure the .github directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent / ".github"))

from changelogs import (  # noqa: E402
    ChangelogError,
    ChangelogGenerator,
    Config,
    GitHubReleaseError,
    ManifestFetchError,
    TagDiscoveryError,
    check_github_release_exists,
    get_last_published_release_tag,
    load_config,
    write_github_output,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_CONFIG: Dict = {
    "os_name": "bluefin-lts",
    "targets": ["lts", "dx"],
    "registry_url": "ghcr.io/test-org",
    "package_blacklist": ["firefox"],
    "image_variants": ["", "-dx"],
    "patterns": {
        "centos": r"\.el\d\d",
        "start_pattern": r"{target}\.\d\d\d+",
    },
    "templates": {
        "pattern_add": "\n| ✨ | {name} | | {version} |",
        "pattern_change": "\n| 🔄 | {name} | {prev} | {new} |",
        "pattern_remove": "\n| ❌ | {name} | {version} | |",
        "pattern_pkgrel_changed": "{prev} ➡️ {new}",
        "pattern_pkgrel": "{version}",
        "common_pattern": "### {title}\n| | Name | Previous | New |\n{changes}\n\n",
        "commits_format": "### Commits\n{commits}\n\n",
        "commit_format": "\n| **[{short}](...)** | {subject} |",
        "changelog_title": "{os} {tag}: {pretty}",
        "handwritten_placeholder": "Auto-generated for `{curr}`.",
        "hwe_kernel_table": "### HWE\n{changes}",
    },
    "sections": {"centos": "CentOS packages", "common": "Common packages"},
    "defaults": {
        "retries": 3,
        "retry_wait": 5,
        "timeout_seconds": 30,
        "output_file": "changelog.md",
        "env_output_file": "output.env",
        "enable_commits": True,
    },
}


@pytest.fixture
def config():
    return Config(**MINIMAL_CONFIG)


@pytest.fixture
def config_yaml_file(tmp_path):
    """Write MINIMAL_CONFIG to a temp YAML file and return its path."""
    cfg_path = tmp_path / "test_changelog_config.yaml"
    cfg_path.write_text(yaml.dump(MINIMAL_CONFIG))
    return str(cfg_path)


@pytest.fixture
def generator(config):
    return ChangelogGenerator(config=config)


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

class TestConfig:
    def test_config_creation(self, config):
        assert config.os_name == "bluefin-lts"
        assert config.targets == ["lts", "dx"]
        assert config.registry_url == "ghcr.io/test-org"

    def test_config_package_blacklist(self, config):
        assert "firefox" in config.package_blacklist

    def test_config_image_variants(self, config):
        assert "" in config.image_variants
        assert "-dx" in config.image_variants

    def test_config_patterns_keys(self, config):
        assert "centos" in config.patterns
        assert "start_pattern" in config.patterns

    def test_config_defaults_keys(self, config):
        assert "retries" in config.defaults
        assert "timeout_seconds" in config.defaults


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_config_from_file(self, config_yaml_file):
        loaded = load_config(config_yaml_file)
        assert loaded.os_name == "bluefin-lts"
        assert loaded.targets == ["lts", "dx"]

    def test_load_config_missing_file_exits(self):
        with pytest.raises(SystemExit):
            load_config("/nonexistent/path/config.yaml")

    def test_load_config_invalid_yaml_exits(self, tmp_path):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [unclosed bracket\n")
        with pytest.raises(SystemExit):
            load_config(str(bad_yaml))

    def test_load_config_preserves_targets(self, config_yaml_file):
        loaded = load_config(config_yaml_file)
        assert set(loaded.targets) == {"lts", "dx"}


# ---------------------------------------------------------------------------
# write_github_output
# ---------------------------------------------------------------------------

class TestWriteGithubOutput:
    def test_writes_key_value_pairs(self, tmp_path):
        out = tmp_path / "output.env"
        out.touch()
        write_github_output(str(out), {"FOO": "bar", "BAZ": "qux"})
        content = out.read_text()
        assert "FOO=bar\n" in content
        assert "BAZ=qux\n" in content

    def test_appends_to_existing_file(self, tmp_path):
        out = tmp_path / "output.env"
        out.write_text("EXISTING=1\n")
        write_github_output(str(out), {"NEW": "val"})
        content = out.read_text()
        assert "EXISTING=1\n" in content
        assert "NEW=val\n" in content

    def test_writes_empty_dict_without_error(self, tmp_path):
        out = tmp_path / "output.env"
        out.touch()
        write_github_output(str(out), {})
        assert out.read_text() == ""

    def test_handles_write_error_gracefully(self, tmp_path):
        """write_github_output logs the error but does not raise."""
        write_github_output("/nonexistent/dir/output.env", {"KEY": "val"})
        # If we reach here, no exception was raised — that's the expected behaviour


# ---------------------------------------------------------------------------
# check_github_release_exists
# ---------------------------------------------------------------------------

class TestCheckGithubReleaseExists:
    def test_returns_true_when_gh_exits_zero(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("changelogs.subprocess.run", return_value=mock_result):
            assert check_github_release_exists("v1.0.0") is True

    def test_returns_false_when_gh_exits_nonzero(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("changelogs.subprocess.run", return_value=mock_result):
            assert check_github_release_exists("v1.0.0") is False

    def test_returns_false_on_timeout(self):
        with patch(
            "changelogs.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=30),
        ):
            assert check_github_release_exists("v1.0.0") is False

    def test_returns_false_when_gh_not_found(self):
        with patch(
            "changelogs.subprocess.run", side_effect=FileNotFoundError
        ):
            assert check_github_release_exists("v1.0.0") is False


# ---------------------------------------------------------------------------
# get_last_published_release_tag
# ---------------------------------------------------------------------------

class TestGetLastPublishedReleaseTag:
    def test_returns_tag_when_gh_succeeds(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "40.20260101\n"
        with patch("changelogs.subprocess.run", return_value=mock_result):
            tag = get_last_published_release_tag()
        assert tag == "40.20260101"

    def test_returns_none_when_gh_fails(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("changelogs.subprocess.run", return_value=mock_result):
            assert get_last_published_release_tag() is None

    def test_returns_none_on_timeout(self):
        with patch(
            "changelogs.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=30),
        ):
            assert get_last_published_release_tag() is None

    def test_strips_trailing_newline(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "40.20260101\n"
        with patch("changelogs.subprocess.run", return_value=mock_result):
            tag = get_last_published_release_tag()
        assert "\n" not in tag


# ---------------------------------------------------------------------------
# ChangelogGenerator.__init__
# ---------------------------------------------------------------------------

class TestChangelogGeneratorInit:
    def test_init_with_explicit_config(self, config):
        gen = ChangelogGenerator(config=config)
        assert gen.config is config

    def test_init_compiles_centos_pattern(self, config):
        gen = ChangelogGenerator(config=config)
        assert gen.centos_pattern.pattern == config.patterns["centos"]

    def test_init_compiles_start_patterns_for_all_targets(self, config):
        gen = ChangelogGenerator(config=config)
        assert set(gen.start_patterns.keys()) == set(config.targets)

    def test_init_empty_manifest_cache(self, config):
        gen = ChangelogGenerator(config=config)
        assert gen._manifest_cache == {}

    def test_centos_pattern_matches_el10(self, generator):
        assert generator.centos_pattern.search("foo-1.0.el10.x86_64")

    def test_centos_pattern_does_not_match_fc40(self, generator):
        assert not generator.centos_pattern.search("foo-1.0.fc40.x86_64")


# ---------------------------------------------------------------------------
# ChangelogGenerator.get_images
# ---------------------------------------------------------------------------

class TestGetImages:
    def test_get_images_returns_list(self, generator):
        images = generator.get_images("lts")
        assert isinstance(images, list)
        assert len(images) > 0

    def test_get_images_tuples_have_two_elements(self, generator):
        for img, target in generator.get_images("lts"):
            assert isinstance(img, str)
            assert isinstance(target, str)

    def test_get_images_hwe_returns_single_entry(self, generator):
        """HWE target short-circuits after first match."""
        images = generator.get_images("lts-hwe")
        assert len(images) == 1

    def test_get_images_dx_experience_appended(self, generator):
        """'-dx' variant should appear in images for 'dx' target."""
        images = generator.get_images("dx")
        image_names = [img for img, _ in images]
        assert any("-dx" in name for name in image_names)

    def test_get_images_base_name_is_bluefin(self, generator):
        """Base image name is always 'bluefin'."""
        images = generator.get_images("lts")
        for img, _ in images:
            assert img.startswith("bluefin")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class TestCustomExceptions:
    def test_changelog_error_is_exception(self):
        with pytest.raises(ChangelogError):
            raise ChangelogError("test error")

    def test_manifest_fetch_error_is_changelog_error(self):
        with pytest.raises(ChangelogError):
            raise ManifestFetchError("manifest error")

    def test_tag_discovery_error_is_changelog_error(self):
        with pytest.raises(ChangelogError):
            raise TagDiscoveryError("tag error")

    def test_github_release_error_is_changelog_error(self):
        with pytest.raises(ChangelogError):
            raise GitHubReleaseError("release error")
