"""README checks: the Fork first policy, one install command per harness, the
component mapping and the per-run schedule wording."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
INSTALL = REPO_ROOT / "INSTALL.md"

# One install command per harness the sibling repos support.
INSTALL_COMMANDS = {
    "Claude Code": "claude plugin marketplace add",
    "Codex": "codex plugin marketplace add",
    "Gemini": "gemini extensions install",
    "Hermes": "Follow INSTALL.md",
    "opencode": "Follow INSTALL.md",
    "by hand": "ln -s",
}
README_POINT = "Follow INSTALL.md in this repo"

# The hard rules of INSTALL.md. One pin per rule.
# The one `mkdir` INSTALL.md allows creates the parent folder of the link name.
MKDIR_CMD = 'mkdir -p "$(dirname "<link name>")"'
INSTALL_RULES = {
    "detect step": ("gh api user --jq .login", "`git remote -v`", "`test -d`"),
    "no self-fork": ("Never fork a repository that you own",
                     "GitHub blocks a fork of your own repository",
                     "use the existing clone"),
    "own harness name": ("Name the harness that runs this agent",),
    "ask if unsure": ("ask the user and stop until the user answers",),
    "batched questions": ("Ask all questions in one message", "Wait for the answers",
                          "default: only the harness that runs this agent",
                          "fork or clone", "link or plugin route where both exist"),
    "plan approval": ("Show the plan and wait for the user approval",
                      "Change nothing before the approval"),
    "chosen harnesses only": ("Install in the chosen harnesses only",),
    "link only install": ("Install only by a symlink of the skill folder",),
    "hand config ban": ("Do not edit a harness config file by hand",),
    "plugin commands after approval": ("A harness plugin command writes a harness config file",
                                       "Run it only after the user approves the shown plan",
                                       "Otherwise print it for the user"),
    "codex folder route": ("${CODEX_HOME:-$HOME/.codex}/skills/self-improvement",
                           "observed on one machine", "not documented by Codex CLI"),
    "stop when occupied": ("If anything else is at the link name",
                           "stop and tell the user the path",
                           "Do not move, back up or delete it"),
    "absolute source": ("Resolve the source `skills/self-improvement` in the clone with `realpath`",
                        "Keep the result as the absolute source"),
    "ordinary quotes": ("ordinary shell double quotes", "Do not add backslashes"),
    "correct link stops": ("do no more for this harness",),
    "probes accept absent results": ("A detection probe only reads state",
                                     "Its non-zero exit is an absent result, not a command failure"),
    "source after approval": ("Get the source after the user approves the plan",
                              "as the user answered"),
    "per-harness stop": ("Continue with the next chosen harness",
                         "The report lists the result for each chosen harness"),
    "state test first": ("Test the link name with `test -L`",
                         "If `test -L` exits non-zero, continue at step 6"),
    "link flags": ("ln -sTn",),
    "mkdir parent-only": (MKDIR_CMD,),
    "link resolves": ('`readlink -f` of the link name equals the absolute source',
                      '`test -e` of the link name exits 0'),
    "restart hint": ("Tell the user to restart the harness",),
    "failure rule": ("If a command that changes state exits non-zero, stop and report",
                     "Keep all paths as they are"),
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


# The INSTALL.md hard-rule pins and the README pointer pin.

# The old marker and the backup machinery tokens must stay out of INSTALL.md.
FORBIDDEN_TOKENS = {
    "no find -newer": ("MARKER", "-newer"),
    "no .bak-": (".bak-",),
    "no diff -r": ("diff -r",),
    "no cp -a": ("cp -a",),
    "no sha256sum": ("sha256sum",),
}

def install_findings(text):
    """Return one finding per missing hard rule; empty when complete."""
    findings = []
    for rule, phrases in INSTALL_RULES.items():
        for phrase in phrases:
            if phrase not in text:
                findings.append(f"INSTALL.md misses the {rule} rule: {phrase}")
    for rule, tokens in FORBIDDEN_TOKENS.items():
        for token in tokens:
            if token in text:
                findings.append(f"INSTALL.md breaks the {rule} rule: it keeps the token {token!r}")
    if "mkdir" in text.replace(MKDIR_CMD, ""):
        findings.append("INSTALL.md breaks the mkdir parent-only rule: it runs `mkdir` outside the parent folder of the link name")
    return findings


def install_file_findings(root):
    """Check INSTALL.md under root. Missing file is one finding."""
    path = Path(root) / "INSTALL.md"
    if not path.is_file():
        return ["INSTALL.md is missing"]
    return install_findings(path.read_text())


def readme_pointer_findings(text):
    return [] if README_POINT in text else ["README does not point to INSTALL.md"]


def drop_lines(text, *needles):
    lines = text.splitlines(keepends=True)
    kept = [ln for ln in lines if not any(n in ln for n in needles)]
    assert kept != lines, f"no line matched {needles}"
    return "".join(kept)


# One entry per pin: name, the file, the checker, the mutator that removes the rule.
def insert_token(token):
    """Put a forbidden token at the top of the text so the pin must fire."""
    return lambda root, t: t.replace("# Install\n", f"# Install\n\n{token}\n", 1)

INSTALL_MUTATIONS = [
    ("INSTALL.md exists", None, install_file_findings,
     lambda root, t: root),
    ("detect step", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, "gh api user --jq .login", "`git remote -v`", "`test -d`")),
    ("no self-fork", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["no self-fork"])),
    ("own harness name", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["own harness name"])),
    ("ask if unsure", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["ask if unsure"])),
    ("batched questions", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, "Ask all questions in one message", "Wait for the answers")),
    ("plan approval", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["plan approval"])),
    ("chosen harnesses only", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["chosen harnesses only"])),
    ("link only install", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["link only install"])),
    ("hand config ban", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["hand config ban"])),
    ("plugin commands after approval", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["plugin commands after approval"])),
    ("codex folder route", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["codex folder route"])),
    ("absolute source", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["absolute source"])),
    ("correct link stops", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["correct link stops"])),
    ("probes accept absent results", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["probes accept absent results"])),
    ("source after approval", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["source after approval"])),
    ("per-harness stop", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["per-harness stop"])),
    ("state test first", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, "Test the link name with `test -L`")),
    ("ordinary quotes", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, "ordinary shell double quotes")),
    ("link flags", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["link flags"])),
    ("link resolves", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["link resolves"])),
    ("restart hint", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["restart hint"])),
    ("failure rule", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, *INSTALL_RULES["failure rule"])),
    ("no find -newer", "INSTALL.md", install_findings,
     insert_token("MARKER -newer")),
    ("no .bak-", "INSTALL.md", install_findings,
     insert_token(".bak-")),
    ("mkdir parent-only", "INSTALL.md", install_findings,
     lambda root, t: drop_lines(t, MKDIR_CMD)),
    ("no diff -r", "INSTALL.md", install_findings,
     insert_token("diff -r")),
    ("no cp -a", "INSTALL.md", install_findings,
     insert_token("cp -a")),
    ("no sha256sum", "INSTALL.md", install_findings,
     insert_token("sha256sum")),
    ("README points to INSTALL.md", "README.md", readme_pointer_findings,
     lambda root, t: t.replace(README_POINT, "")),
]


def test_install_pins_pass_on_the_repo_files():
    assert install_file_findings(REPO_ROOT) == []
    assert readme_pointer_findings(README.read_text()) == []


def test_install_pins_fail_when_the_rule_is_removed(tmp_path):
    """One observed negative per pin. The line records the observation."""
    for name, rel, check, mutate in INSTALL_MUTATIONS:
        root = tmp_path / name.replace(" ", "-")
        root.mkdir()
        if rel is None:
            mutated_root = root
            findings = install_file_findings(mutated_root)
        else:
            original = (REPO_ROOT / rel).read_text()
            mutated = mutate(root, original)
            assert mutated != original, f"the {name} mutation did nothing"
            (root / rel).write_text(mutated)
            findings = check(mutated)
        state = "failed-loud" if findings else "SILENT PASS"
        print(f"mutation: {name} removed -> {state}: {findings}")
        assert findings, f"the {name} pin must fail when its rule is removed"
        if rel == "INSTALL.md":
            assert any(f"the {name} rule" in f for f in findings), f"the {name} pin did not fire"

# The defect wording from the field reports rd-1 and rd-4. The pins must fail on it.
OLD_FORK_RULE = "Fork this repository first, and clone the fork."
NEW_FORK_RULE = (
    "1. Never fork a repository that you own. GitHub blocks a fork of your own repository. "
    "When the login of `gh api user --jq .login` is `DiamonDinoia`, use the existing clone. "
    "Check: the clone is the fork clone or the existing clone of your own repository."
)
OLD_CODEX_CLAIM = (
    "This repository documents no user skill folder for Codex CLI and Gemini CLI."
)

def test_defect_wording_fails_the_new_pins(tmp_path):
    text = INSTALL.read_text()
    forked = text.replace(NEW_FORK_RULE, OLD_FORK_RULE)
    assert forked != text, "the rd-1 mutation did nothing"
    assert any("no self-fork" in f for f in install_findings(forked)), \
        "the pin must fail on the fork-first wording"
    codex = "\n".join(
        ln for ln in text.splitlines()
        if "Codex CLI folder route" not in ln and "Codex CLI |" not in ln
    ) + "\n" + OLD_CODEX_CLAIM + "\n"
    assert codex != text, "the rd-4 mutation did nothing"
    assert any("codex folder route" in f for f in install_findings(codex)), \
        "the pin must fail on the no-Codex-folder claim"

# The defect wording from the field reports r2, r3 and r4. The new pins must fail on it.
OLD_RULE_8 = "8. If a command exits non-zero, stop and report. Keep all paths as they are."
NEW_RULE_8 = ("8. If a command that changes state exits non-zero, stop and report. "
              "Keep all paths as they are. A detection probe only reads state. "
              "Its non-zero exit is an absent result, not a command failure.")
OLD_SOURCE_STEP = ("3. Get the source. When the login is not `DiamonDinoia`, "
                   "fork `DiamonDinoia/skill-self-improvement` and clone the fork. "
                   "Check: `git remote -v` shows the fork as `origin`. "
                   "When the login is `DiamonDinoia`, use the existing clone. "
                   "Check: `git remote -v` runs in that clone.")
NEW_SOURCE_STEP = ("4. Get the source after the user approves the plan, "
                   "as the user answered in step 2. "
                   "When the login is `DiamonDinoia`, use the existing clone (hard rule 1). "
                   "Check: `git remote -v` runs in that clone. "
                   "When the answer is fork, fork `DiamonDinoia/skill-self-improvement` "
                   "and clone the fork. Check: `git remote -v` shows the fork as `origin`. "
                   "When the answer is clone, clone `DiamonDinoia/skill-self-improvement`. "
                   "Then run each approved plugin command. "
                   "Print the other plugin commands for the user.")

def test_r2_probe_pin_fails_on_old_text():
    text = INSTALL.read_text()
    old = text.replace(NEW_RULE_8, OLD_RULE_8)
    assert old != text, "the r2 mutation did nothing"
    assert any("probes accept absent results" in f for f in install_findings(old)), \
        "the pin must fail on the stop-on-any-error wording"

def test_r3_source_order_pin_fails_on_old_text():
    text = INSTALL.read_text()
    old = text.replace(NEW_SOURCE_STEP, OLD_SOURCE_STEP)
    assert old != text, "the r3 mutation did nothing"
    assert any("source after approval" in f for f in install_findings(old)), \
        "the pin must fail on the source-before-approval wording"

def test_r4_per_harness_pin_fails_on_old_text():
    text = INSTALL.read_text()
    old = text.replace(" The report lists the result for each chosen harness.", "")
    old = old.replace(" Continue with the next chosen harness.", "")
    old = old.replace("do no more for this harness. Report this.",
                      "do no more. Report this and stop.")
    assert old != text, "the r4 mutation did nothing"
    assert any("per-harness stop" in f for f in install_findings(old)), \
        "the pin must fail on the global-stop wording"
