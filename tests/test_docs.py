"""README checks: the Fork first policy, one install command per harness, the
component mapping and the per-run schedule wording."""
import re
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"

# One install command per harness the sibling repos support.
INSTALL_COMMANDS = {
    "Claude Code": "claude plugin marketplace add",
    "Codex": "codex plugin marketplace add",
    "Gemini": "gemini extensions install",
    "Hermes": "install.sh",
    "opencode": "install.sh",
    "by hand": "ln -s",
}

# The component mapping of SKILL.md, in its own words.
COMPONENT_MAPPING = (
    "references/memory.md",
    "agents/*.md",
    "plugin files and the hook files",
    "proposed diff only",
)
SCHEDULE_WORDING = "One run schedules 4k rollouts and 3k improvement stages"
BASELINE_WORDING = "Baseline runs show the current skill at work"
WINNER_GATE_WORDING = "gate the candidates and the composed winner"

# Rule glosses must keep the tail clauses of the SKILL.md rules.
RULE_1_GLOSS = "does not edit the live skill tree or the live config"
RULE_TAILS = (
    "Use `git revert` to cancel an adoption.",
    "An incorrect lesson gets a new entry with `Supersedes: L-NNN`.",
)


def readme_findings(text):
    """Return one finding per missing README element; empty when complete."""
    findings = []
    if not re.search(r"^## Fork first\s*$", text, re.MULTILINE):
        findings.append("missing the '## Fork first' section")
    if "fork" not in text.lower():
        findings.append("missing the word fork")
    if "upstream" not in text:
        findings.append("missing the word upstream")
    for harness, command in INSTALL_COMMANDS.items():
        if harness not in text:
            findings.append(f"missing install row for {harness}")
        if command not in text:
            findings.append(f"missing install command for {harness}: {command}")
    for term in COMPONENT_MAPPING:
        if term not in text:
            findings.append(f"missing component mapping term: {term}")
    if SCHEDULE_WORDING not in text:
        findings.append("missing the per-run schedule wording")
    if BASELINE_WORDING not in text:
        findings.append("missing the baseline-runs wording")
    if WINNER_GATE_WORDING not in text:
        findings.append("missing the winner gate wording")
    if RULE_1_GLOSS not in text:
        findings.append(f"missing rule gloss: {RULE_1_GLOSS}")
    for tail in RULE_TAILS:
        if tail not in text:
            findings.append(f"missing rule tail clause: {tail}")
    return findings


def drop_fork_first(text):
    return re.sub(
        r"^## Fork first\s*$.*?(?=^## |\Z)", "", text, flags=re.MULTILINE | re.DOTALL
    )


def test_readme_has_fork_policy_and_install_commands():
    assert readme_findings(README.read_text()) == []


def test_missing_fork_first_section_fails():
    stripped = drop_fork_first(README.read_text())
    findings = readme_findings(stripped)
    assert findings, "the check must fail without the Fork first section"
    assert any("Fork first" in f for f in findings)


def test_component_mapping_pin_fails_when_mapping_deleted(tmp_path):
    copy = tmp_path / "README.md"
    text = README.read_text()
    for term in COMPONENT_MAPPING:
        text = text.replace(term, "")
    copy.write_text(text)
    findings = readme_findings(copy.read_text())
    assert any("component mapping" in f for f in findings)


def test_schedule_pin_fails_when_wording_deleted(tmp_path):
    copy = tmp_path / "README.md"
    copy.write_text(README.read_text().replace(SCHEDULE_WORDING, ""))
    findings = readme_findings(copy.read_text())
    assert any("schedule" in f for f in findings)

def test_baseline_and_winner_gate_pins_fail_when_deleted(tmp_path):
    text = README.read_text()
    for phrase in (BASELINE_WORDING, WINNER_GATE_WORDING):
        assert phrase in text, f"the README must keep {phrase!r}"
        copy = tmp_path / "README.md"
        copy.write_text(text.replace(phrase, ""))
        findings = readme_findings(copy.read_text())
        assert findings, f"the check must pin {phrase!r}"


def test_rule_1_gloss_pin_fails_when_deleted(tmp_path):
    text = README.read_text()
    assert RULE_1_GLOSS in text, "the README must keep the rule 1 gloss"
    copy = tmp_path / "README.md"
    copy.write_text(text.replace(RULE_1_GLOSS, ""))
    findings = readme_findings(copy.read_text())
    assert any("rule gloss" in f for f in findings)


def test_rule_tail_pins_fail_when_deleted(tmp_path):
    text = README.read_text()
    for tail in RULE_TAILS:
        assert tail in text, "the README must keep the rule tail clause"
        copy = tmp_path / "README.md"
        copy.write_text(text.replace(tail, ""))
        findings = readme_findings(copy.read_text())
        assert any("rule tail" in f for f in findings), f"the check must pin {tail}"
