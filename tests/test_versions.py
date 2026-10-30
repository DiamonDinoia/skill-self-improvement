"""Every manifest must carry the same version string."""
import json
import re
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# shortcut: fixed manifest list, extend when a new manifest type appears
JSON_MANIFESTS = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    "gemini-extension.json",
)
TEXT_MANIFESTS = (
    "skills/self-improvement/SKILL.md",
)
LINE_VERSION = re.compile(r"^version:\s*[\"']?([^\"'\s]+)", re.MULTILINE)


def _walk_versions(node, where):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "version" and isinstance(value, str):
                yield where, value
            else:
                yield from _walk_versions(value, where)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_versions(item, where)


def collect_versions(root):
    """Return every (file, version) pair found under the repo root."""
    root = Path(root)
    found = []
    for rel in JSON_MANIFESTS:
        path = root / rel
        if path.is_file():
            found.extend(_walk_versions(json.loads(path.read_text()), rel))
    for rel in TEXT_MANIFESTS:
        path = root / rel
        if path.is_file():
            found.extend((rel, v) for v in LINE_VERSION.findall(path.read_text()))
    return found


def version_errors(root):
    """Return one error line per problem; empty when all versions match."""
    found = collect_versions(root)
    if not found:
        return [f"no version strings found under {root}"]
    if len({v for _, v in found}) > 1:
        listed = ", ".join(f"{rel}={v}" for rel, v in found)
        return [f"version mismatch: {listed}"]
    return []


def make_fixture(tmp_path):
    """Copy the real manifests and add a minimal SKILL.md at version 0.2.0."""
    for rel in JSON_MANIFESTS:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, dst)
    skill = tmp_path / "skills/self-improvement/SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        "---\n"
        "name: self-improvement\n"
        "description: test fixture\n"
        "version: 0.3.0\n"
        "---\n"
    )
    return tmp_path


def test_fixture_versions_agree(tmp_path):
    assert version_errors(make_fixture(tmp_path)) == []


def test_mismatched_manifest_version_is_reported(tmp_path):
    root = make_fixture(tmp_path)
    path = root / ".claude-plugin/plugin.json"
    data = json.loads(path.read_text())
    data["version"] = "0.1.1"
    path.write_text(json.dumps(data))
    errors = version_errors(root)
    assert errors, "the checker must report the mismatched version"
    assert "0.1.1" in errors[0]


@pytest.mark.skipif(
    not (REPO_ROOT / "skills/self-improvement/SKILL.md").is_file(),
    reason="skills/self-improvement/SKILL.md is absent in this checkout",
)
def test_real_repo_versions_agree():
    assert version_errors(REPO_ROOT) == []
