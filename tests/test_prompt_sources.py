"""Source checks for skills/self-improvement/references/prompts.md."""
import os
import pathlib
import re
import subprocess

import pytest

PROMPTS = (
    pathlib.Path(__file__).resolve().parents[1]
    / "skills"
    / "self-improvement"
    / "references"
    / "prompts.md"
)

# Every prompt pack found in harness2, one block each.
PACKS = (
    "Shared guards",
    "Surface pack",
    "Generalize rule",
    "Keep-base rule",
    "INV proposer pack",
    "DOM proposer pack",
    "TTS surface heads",
    "TTS proposer pack",
    "TTS propose mission",
    "TTS aggregate mission",
    "TTS select mission",
    "Propose mission",
    "Assembly header shells",
    "Aggregate mission",
    "Compose round, sequential mode",
    "Selection conformance",
    "Select mission",
    "Experience mission",
    "Selector assets note",
    "Selector evidence tail",
    "Reflection record tail",
    "Proposal retry",
    "Runner follow note",
    "Runner wrapper",
    "Library entry",
    "Experience gate",
    "Library index rows",
)
# Blocks with no upstream prompt text.
ORIGINAL_BLOCKS = ("Prober", "Reviewer")

SOURCE_LINE = re.compile(
    r"Source: (?:original|harness2/core/[a-z_]+\.py L\d+-\d+ @[0-9a-f]{8,40} "
    r"\([A-Za-z_][A-Za-z0-9_]*(?:, [A-Za-z_][A-Za-z0-9_]*)*\) \"[^\"]+\")"
)
CITATION = re.compile(
    r"^Source: harness2/core/([a-z_]+)\.py L(\d+)-(\d+) @([0-9a-f]{8,40}) "
    r"\(([A-Za-z_][A-Za-z0-9_]*(?:, [A-Za-z_][A-Za-z0-9_]*)*)\) \"([^\"]+)\"$",
    re.M,
)
# Module-level prompt constants in prompts.py: NAME = """ or NAME = (
PROMPT_CONST = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*) = (?:"""|\()')


def test_apache_notice():
    head = PROMPTS.read_text(encoding="utf-8").split("## ", 1)[0]
    assert "Copyright 2026 Google LLC" in head
    assert "Apache License, Version 2.0" in head
    assert "Modified for skill-self-improvement" in head


def test_packs_exist_and_each_block_has_one_source_line():
    text = PROMPTS.read_text(encoding="utf-8")
    for name in PACKS + ORIGINAL_BLOCKS:
        assert re.search(rf"(?m)^## {re.escape(name)}\s*$", text), name
    blocks = re.split(r"(?m)^## ", text)[1:]
    assert len(blocks) == len(PACKS) + len(ORIGINAL_BLOCKS)
    for block in blocks:
        title = block.splitlines()[0]
        lines = [ln for ln in block.splitlines() if ln.startswith("Source: ")]
        assert len(lines) == 1, title
        assert SOURCE_LINE.fullmatch(lines[0]), title
        match = CITATION.fullmatch(lines[0])
        if match:
            words = match.group(6).split()
            assert 4 <= len(words) <= 10, f"{title}: anchor has {len(words)} words"


def _clone_root():
    root = os.environ.get("HARNESS2_SRC")
    if not root:
        pytest.skip("HARNESS2_SRC is not set")
    path = pathlib.Path(root)
    if not path.is_dir():
        pytest.skip("HARNESS2_SRC does not name a directory")
    try:
        run = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("git cannot read HARNESS2_SRC")
    if run.returncode != 0:
        pytest.skip("HARNESS2_SRC is not a git checkout")
    return path


def _symbol_defined(lines, symbol, start, end):
    """True when SYMBOL is defined in the range or is the enclosing def."""
    local = re.compile(rf"^\s*(?:def\s+{symbol}\b|class\s+{symbol}\b|{symbol}\s*=)")
    top = re.compile(r"^(?:def\s+|class\s+)")
    defs = [i for i, line in enumerate(lines, 1) if local.match(line)]
    if any(start <= i <= end for i in defs):
        return True
    for i in defs:
        if i <= start:
            nxt = next(
                (j for j in range(i + 1, len(lines) + 1) if top.match(lines[j - 1])),
                len(lines) + 1,
            )
            if end < nxt:
                return True
    return False


def _range_errors(text, root):
    errors = []
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    for match in CITATION.finditer(text):
        name, start, end, sha = (
            match.group(1),
            int(match.group(2)),
            int(match.group(3)),
            match.group(4),
        )
        symbols, anchor = match.group(5), match.group(6)
        path = root / "harness2" / "core" / f"{name}.py"
        if not path.is_file():
            errors.append(f"{name}.py not found at the cited path")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if not 1 <= start <= end <= len(lines):
            errors.append(f"{name}.py L{start}-{end} is outside 1-{len(lines)}")
            continue
        if not head.startswith(sha):
            errors.append(f"HEAD {head[:12]} does not start with cited sha {sha}")
        for symbol in symbols.split(", "):
            if not _symbol_defined(lines, symbol, start, end):
                errors.append(
                    f"{symbol} is not defined in {name}.py L{start}-{end} or its enclosing def"
                )
        errors.extend(_anchor_errors(lines, name, start, end, anchor))
    return errors


# A def, class or module-level assignment starts a definition window.
_DEF = re.compile(r"^\s*(?:def\s|class\s)|^[A-Za-z_][A-Za-z0-9_]*\s*=")


def _anchor_errors(lines, name, start, end, anchor):
    """The anchor must sit in the cited range, and only there in its def window."""
    probe = " ".join(anchor.split())
    if probe not in " ".join(" ".join(lines[start - 1 : end]).split()):
        return [f"{name}.py L{start}-{end} does not hold the anchor {anchor!r}"]
    lo = next((i for i in range(start, 0, -1) if _DEF.match(lines[i - 1])), 1)
    hi = next(
        (j for j in range(end + 1, len(lines) + 1) if _DEF.match(lines[j - 1])),
        len(lines) + 1,
    )
    outside = " ".join(
        " ".join(lines[lo - 1 : start - 1] + lines[end : hi - 1]).split()
    )
    if probe in outside:
        return [
            f"{name}.py L{start}-{end} anchor {anchor!r} also occurs outside the range "
            f"in its def window L{lo}-{hi - 1}"
        ]
    return []


def _norm(text):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _heading_errors(text, root):
    """The block's first heading must appear in the cited range."""
    errors = []
    for block in re.split(r"(?m)^## ", text)[1:]:
        title = block.splitlines()[0]
        match = CITATION.search(block)
        if not match:
            continue
        heading = next(
            (ln for ln in block.splitlines()[1:] if ln.startswith("# ")), None
        )
        if heading is None:
            continue
        name, start, end = match.group(1), int(match.group(2)), int(match.group(3))
        path = root / "harness2" / "core" / f"{name}.py"
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if not 1 <= start <= end <= len(lines):
            continue
        rng = _norm(" ".join(lines[start - 1 : end]))
        words = _norm(heading).split()
        probe = " ".join(words[:4] if len(words) > 4 else words)
        if probe not in rng:
            errors.append(f"{title}: heading {heading!r} does not appear in cited range")
    return errors


def test_source_ranges_match_clone():
    root = _clone_root()
    errors = _range_errors(PROMPTS.read_text(encoding="utf-8"), root)
    assert not errors, errors


def test_block_headings_appear_in_cited_ranges():
    root = _clone_root()
    errors = _heading_errors(PROMPTS.read_text(encoding="utf-8"), root)
    assert not errors, errors


def test_prompt_constants_are_covered():
    """Every prompt constant in prompts.py sits in a cited range."""
    root = _clone_root()
    lines = (root / "harness2" / "core" / "prompts.py").read_text(
        encoding="utf-8"
    ).splitlines()
    cited = [
        (int(m.group(2)), int(m.group(3)))
        for m in CITATION.finditer(PROMPTS.read_text(encoding="utf-8"))
        if m.group(1) == "prompts"
    ]
    missing = []
    for i, line in enumerate(lines, 1):
        match = PROMPT_CONST.match(line)
        if match and not any(start <= i <= end for start, end in cited):
            missing.append(f"{match.group(1)} at L{i}")
    assert not missing, missing


def test_mutation_beyond_file_length_fails(tmp_path):
    root = _clone_root()
    text = PROMPTS.read_text(encoding="utf-8")
    match = CITATION.search(text)
    assert match
    name, symbols, sha, anchor = (
        match.group(1), match.group(5), match.group(4), match.group(6),
    )
    src = root / "harness2" / "core" / f"{name}.py"
    bad_end = len(src.read_text(encoding="utf-8").splitlines()) + 1
    mutated = (
        text[: match.start()]
        + f'Source: harness2/core/{name}.py L{match.group(2)}-{bad_end} @{sha} '
        f'({symbols}) "{anchor}"'
        + text[match.end() :]
    )
    copy = tmp_path / "prompts.md"
    copy.write_text(mutated, encoding="utf-8")
    errors = _range_errors(copy.read_text(encoding="utf-8"), root)
    assert any("outside" in error for error in errors), errors


def test_mutation_wrong_range_fails(tmp_path):
    """A wrong-but-in-bounds range must fail: L1-2 holds neither the symbol nor the anchor."""
    root = _clone_root()
    text = PROMPTS.read_text(encoding="utf-8")
    match = CITATION.search(text)
    assert match
    name, symbols, sha, anchor = (
        match.group(1), match.group(5), match.group(4), match.group(6),
    )
    mutated = (
        text[: match.start()]
        + f'Source: harness2/core/{name}.py L1-2 @{sha} ({symbols}) "{anchor}"'
        + text[match.end() :]
    )
    copy = tmp_path / "prompts.md"
    copy.write_text(mutated, encoding="utf-8")
    errors = _range_errors(copy.read_text(encoding="utf-8"), root)
    assert any(symbols.split(", ")[0] in error for error in errors), errors

def block(text, name):
    match = re.search(rf"(?m)^## {re.escape(name)}\s*$\n([\s\S]*?)(?=\n## |\Z)", text)
    return match.group(1) if match else None

# The current REPO_ROOT and SKILL_DIR definitions. The check deletes them as a unit, so it
# must fail without them.
CURRENT_ROOT_DEFS = (
    "`REPO_ROOT` is the git top level of the target repo. `SKILL_DIR` holds the target "
    "`SKILL.md`.\nIt equals `REPO_ROOT` or `REPO_ROOT/skills/NAME`. Skill paths are relative "
    "to `SKILL_DIR`.\nPlugin and manifest paths are relative to `REPO_ROOT`. No root "
    "`SKILL.md` is created when\n`SKILL_DIR` differs from `REPO_ROOT`. Every mission gets "
    "both paths.\n"
)
# The old wording each fix replaced. A check must fail on it.
OLD_SELECT_LIST = (
    "    SKILL_NAME/runs/RUN_ID/task.md               the request, verbatim\n"
    "    SKILL_NAME/runs/RUN_ID/probes/CAND_ID/       what that run produced, and the "
    "material it\n"
    "                                                 worked from in its trajectory.md\n"
    "    SKILL_NAME/runs/RUN_ID/candidates/CAND_ID.diff  the edit its state carried\n"
)
NEW_SELECT_LIST = (
    "    SKILL_NAME/runs/RUN_ID/selection/               the shuffled, output-only directory\n"
    "    SKILL_NAME/runs/RUN_ID/selection/task.md        the request, verbatim\n"
    "    SKILL_NAME/runs/RUN_ID/selection/source/        the shared task source material\n"
    "    SKILL_NAME/runs/RUN_ID/selection/candidates/<id>.md  one untrimmed deliverable per\n"
    "                                                    anonymous id, and its declared assets\n"
)
OLD_TAIL_LIST = (
    "    SKILL_NAME/runs/RUN_ID/task.md     the instructions\n"
    "    SKILL_NAME/runs/RUN_ID/probes/CAND_ID/   one per candidate: <ids>, the deliverable "
    "and\n"
    "                                     its trajectory.md, the material worked from\n"
)
NEW_TAIL_LIST = (
    "    SKILL_NAME/runs/RUN_ID/selection/task.md     the instructions\n"
    "    SKILL_NAME/runs/RUN_ID/selection/source/     task source materials, when supplied\n"
    "    SKILL_NAME/runs/RUN_ID/selection/candidates/<id>.md  one file per candidate: <ids>\n"
)
OLD_TRIGGER_INV = (
    "Name its\n  trigger in the skill description, and carry any helper it requires."
)
NEW_TRIGGER_INV = (
    "Name its\n  trigger in the trigger sentence of the text that loads the skill, or in the "
    "skill's\n  `description` when the target repo has no text that loads skills, and carry "
    "any helper it\n  requires."
)
OLD_TRIGGER_DOM = (
    "Every skill\nneeds a trigger line you add in the loading text, naming its situation "
    "precisely and narrowly."
)
NEW_TRIGGER_DOM = (
    "Every skill\nneeds a trigger sentence in the text that loads it, or in the skill's\n"
    "`description` when the target repo has no text that loads skills. Name its situation\n"
    "precisely and narrowly."
)

def surface_root_errors(text):
    errors = []
    if "git top level of the target repo" not in text or "`SKILL_DIR` holds the target `SKILL.md`" not in text:
        errors.append("the REPO_ROOT and SKILL_DIR definitions are missing")
    for name in ("Surface pack", "TTS surface heads"):
        body = block(text, name)
        if body is None:
            errors.append(f"missing the {name} block")
            continue
        rows = [ln for ln in body.splitlines() if ln.startswith("| `")]
        if not any("`SKILL_DIR/" in ln for ln in rows):
            errors.append(f"{name} table has no SKILL_DIR row")
        if not any("`REPO_ROOT/" in ln for ln in rows):
            errors.append(f"{name} table has no REPO_ROOT row")
    return errors

def selector_path_errors(text):
    bad = []
    for name in ("TTS select mission", "Select mission", "Selector evidence tail",
                 "Selector assets note"):
        body = block(text, name)
        if body is None:
            bad.append(f"missing the {name} block")
            continue
        for line in body.splitlines():
            entry = line.strip()
            if entry.startswith("SKILL_NAME/runs/") and ("diff" in entry or "trajectory" in entry):
                bad.append(f"{name} input list holds {entry!r}")
    return bad

def trigger_placement_errors(text):
    errors = []
    if text.count("no text that loads skills") < 3:
        errors.append("fewer than three trigger lines carry the no-loading-text fallback")
    for stale in ("you add in the loading text", "trigger in the skill description"):
        if stale in text:
            errors.append(f"stale trigger wording {stale!r}")
    return errors

def library_index_id_errors(text):
    body = block(text, "Library index rows")
    if body is None:
        return ["missing the Library index rows block"]
    if "- id:" not in body or "E-NNN" not in body:
        return ["the library index rows have no E-NNN id column"]
    return []

def test_skill_dir_and_repo_root_in_surface_tables(tmp_path):
    text = PROMPTS.read_text(encoding="utf-8")
    assert surface_root_errors(text) == []
    old = text.replace(CURRENT_ROOT_DEFS, "").replace("`SKILL_DIR/", "`").replace("`REPO_ROOT/", "`")
    copy = tmp_path / "prompts.md"
    copy.write_text(old, encoding="utf-8")
    assert surface_root_errors(old), "the check must fail on the old allowed-paths tables"

def test_selector_inputs_have_no_diff_or_trajectory(tmp_path):
    text = PROMPTS.read_text(encoding="utf-8")
    assert selector_path_errors(text) == []
    old = text.replace(NEW_SELECT_LIST, OLD_SELECT_LIST).replace(NEW_TAIL_LIST, OLD_TAIL_LIST)
    copy = tmp_path / "prompts.md"
    copy.write_text(old, encoding="utf-8")
    assert selector_path_errors(old), "the check must fail on the old selector input lists"

def test_trigger_placement_matches_the_surface_rule(tmp_path):
    text = PROMPTS.read_text(encoding="utf-8")
    assert trigger_placement_errors(text) == []
    old = text.replace(NEW_TRIGGER_INV, OLD_TRIGGER_INV).replace(NEW_TRIGGER_DOM, OLD_TRIGGER_DOM)
    copy = tmp_path / "prompts.md"
    copy.write_text(old, encoding="utf-8")
    assert trigger_placement_errors(old), "the check must fail on the old trigger lines"

def test_library_index_rows_carry_the_entry_id(tmp_path):
    text = PROMPTS.read_text(encoding="utf-8")
    assert library_index_id_errors(text) == []
    old = text.replace("    - id:      `E-NNN`\n", "")
    copy = tmp_path / "prompts.md"
    copy.write_text(old, encoding="utf-8")
    assert library_index_id_errors(old), "the check must fail without the id row"

# The gate wording of the SKILL.md step 5, in the same words.
GATE_BASELINE = (
    "The baseline result on a check is the best result over `base1`..`basek`. An exit-code "
    "check passes when any baseline run passes. A count check takes the best baseline count. "
    "A candidate or a checkpoint that is worse than that result drops out. A tie does not "
    "drop out. It goes to the blind review, which decides the tie. When the review prefers "
    "neither, the baseline wins."
)

def gate_baseline_errors(text):
    errors = []
    flat = _norm(text)
    if _norm(GATE_BASELINE) not in flat:
        errors.append("the gate misses the best-baseline rule")
    if "worse than the baseline result" in flat:
        errors.append("the gate still compares to one baseline result")
    if re.search(r"as the baseline run\b|from the baseline run\b", flat):
        errors.append("the prober still cites one baseline run")
    return errors

def test_gate_uses_the_best_baseline_result(tmp_path):
    text = PROMPTS.read_text(encoding="utf-8")
    assert gate_baseline_errors(text) == []
    # The old text: no gate rule, and one unnamed baseline run at 1084 and 1090.
    old = re.sub(r"The baseline result on a check[\s\S]*?the baseline wins\.\n\n", "", text)
    old = old.replace("as the baseline runs.", "as the baseline run.").replace(
        "from the baseline runs,", "from the baseline run,")
    assert old != text, "the gate mutation did nothing"
    copy = tmp_path / "prompts.md"
    copy.write_text(old, encoding="utf-8")
    assert gate_baseline_errors(old), "the check must fail on the old gate wording"

def c6_skill_target_errors(text):
    errors = []
    for stale in ("the target repo's `SKILL.md` files", "SKILL.md files and references/"):
        if stale in text:
            errors.append(f"stale c6 skill wording {stale!r}")
    # Each c6 site pins the SKILL.md to SKILL_DIR. The three known sites must exist.
    flat = re.sub(r"\s+", " ", text)
    sites = [m.start() for m in re.finditer(r"- skills:|c6 skills are the", flat)]
    if len(sites) < 3:
        errors.append("a c6 skills site is missing")
    for start in sites:
        end = flat.find(". ", start)
        sentence = flat[start : len(flat) if end < 0 else end]
        if "`SKILL.md` in `SKILL_DIR`" not in sentence:
            errors.append(f"c6 site without the SKILL.md pin: {sentence[:50]!r}")
    return errors

def test_c6_skills_pin_the_skill_md_to_skill_dir(tmp_path):
    text = PROMPTS.read_text(encoding="utf-8")
    assert c6_skill_target_errors(text) == []
    # The old c6 wording at 36, 272-273 and 372.
    old = text.replace(
        "skills: the `SKILL.md` in `SKILL_DIR` and `SKILL_DIR/references/`.",
        "skills: the target repo's `SKILL.md` files and `SKILL_DIR/references/`.",
    ).replace(
        "c6 skills are the\n`SKILL.md` in `SKILL_DIR` and `SKILL_DIR/references/`.",
        "c6 skills are the\nSKILL.md files and references/.",
    ).replace(
        "c6 skills are the `SKILL.md` in `SKILL_DIR` and\n`SKILL_DIR/references/`.",
        "c6 skills are the SKILL.md files and references/.",
    )
    assert old != text, "the c6 mutation did nothing"
    copy = tmp_path / "prompts.md"
    copy.write_text(old, encoding="utf-8")
    assert c6_skill_target_errors(old), "the check must fail on the old c6 skill wording"

def trigger_term_errors(text):
    errors = []
    if re.search(r"trigger line", text, re.I):
        errors.append("the old term 'trigger line' survives")
    if "EVERY SKILL NEEDS A TRIGGER SENTENCE" not in text:
        errors.append("rule 1 does not name the trigger sentence")
    return errors

def test_trigger_sentence_is_the_one_term(tmp_path):
    text = PROMPTS.read_text(encoding="utf-8")
    assert trigger_term_errors(text) == []
    # The old term at 303, 419 and 534.
    old = text.replace("EVERY SKILL NEEDS A TRIGGER SENTENCE", "EVERY SKILL NEEDS A TRIGGER LINE")
    old = old.replace("needs a trigger sentence in the text that loads it",
                      "needs a trigger line in the trigger sentence of the text that loads it")
    old = old.replace("trigger sentence narrow", "trigger line narrow")
    assert old != text, "the trigger-term mutation did nothing"
    copy = tmp_path / "prompts.md"
    copy.write_text(old, encoding="utf-8")
    assert trigger_term_errors(old), "the check must fail on the old 'trigger line' term"
