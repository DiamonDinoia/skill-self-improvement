"""Tests for skills/self-improvement/SKILL.md: frontmatter and the non-destructive rules."""

import re
from pathlib import Path

SKILL_MD = Path(__file__).resolve().parents[1] / "skills" / "self-improvement" / "SKILL.md"
LESSONS_MD = SKILL_MD.parent / "references" / "lessons.md"
PROMPTS_MD = SKILL_MD.parent / "references" / "prompts.md"
COMPONENTS = (
    "system prompt", "guardrails", "memory", "tool guidance",
    "subagents", "skills", "scripts", "plugins",
)
HARNESS2_TERMS = ("parallel", "sequential", "general", "domain")
HEADING = "## Non-destructive rules"
KEY_PHRASES = {
    1: ("run on copies",),
    2: ("new branch", "no force-push"),
    3: ("without approval", "backup"),
    4: ("proposed diffs only",),
    5: ("append-only",),
    6: ("baseline wins ties",),
    7: ("removed rule",),
}


def parse_frontmatter(text):
    assert text.startswith("---\n"), "frontmatter must start at byte 0"
    end = text.index("\n---\n", 3)
    fields = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def parse_rules(text):
    assert f"\n{HEADING}\n" in text, f"missing heading {HEADING!r}"
    section = text.split(f"\n{HEADING}\n", 1)[1].split("\n## ", 1)[0]
    items, current = {}, None
    for line in section.splitlines():
        m = re.match(r"(\d+)\.\s+(.*)", line)
        if m:
            current = int(m.group(1))
            items[current] = m.group(2).strip()
        elif current is not None and line.strip():
            items[current] += " " + line.strip()
    return items


def check(text):
    """Return the list of violations. An empty list means the file passes."""
    errors = []
    fm = parse_frontmatter(text)
    if fm.get("name") != "self-improvement":
        errors.append(f"name: {fm.get('name')!r}")
    if fm.get("version") != "0.3.0":
        errors.append(f"version: {fm.get('version')!r}")
    if "MIT" not in fm.get("license", ""):
        errors.append(f"license: {fm.get('license')!r}")
    if not fm.get("description", "").startswith("Use when"):
        errors.append(f"description: {fm.get('description')!r}")
    items = parse_rules(text)
    if sorted(items) != list(range(1, 8)):
        errors.append(f"expected rules 1-7, got {sorted(items)}")
    for number, phrases in KEY_PHRASES.items():
        item = items.get(number, "")
        for phrase in phrases:
            if phrase not in item:
                errors.append(f"rule {number} misses {phrase!r}")
    return errors


def test_frontmatter():
    fm = parse_frontmatter(SKILL_MD.read_text())
    assert fm["name"] == "self-improvement"
    assert fm["version"] == "0.3.0"
    assert "MIT" in fm["license"]
    assert fm["description"].startswith("Use when")


def test_seven_rules_with_key_phrases():
    items = parse_rules(SKILL_MD.read_text())
    assert sorted(items) == [1, 2, 3, 4, 5, 6, 7]
    for number, phrases in KEY_PHRASES.items():
        for phrase in phrases:
            assert phrase in items[number], f"rule {number} misses {phrase!r}"


def test_check_passes_on_the_repo_file():
    assert check(SKILL_MD.read_text()) == []


def test_mutation_delete_rule_4_fails(tmp_path):
    text = SKILL_MD.read_text()
    head, sep, section = text.partition(f"\n{HEADING}\n")
    lines = section.splitlines(keepends=True)
    kept = [ln for ln in lines if not re.match(r"4\.\s", ln)]
    assert len(kept) == len(lines) - 1, "rule 4 line not found exactly once"
    mutated = tmp_path / "SKILL.md"
    mutated.write_text(head + sep + "".join(kept))
    errors = check(mutated.read_text())
    print(f"mutation: rule 4 deleted -> check {'FAIL' if errors else 'PASS'}: {errors}")
    assert errors, "the check must fail when rule 4 is deleted"


def test_harness2_terms_appear():
    text = SKILL_MD.read_text()
    for term in HARNESS2_TERMS + COMPONENTS:
        assert term in text, f"missing {term!r}"


def section(text, heading):
    """Return the body under a heading, or None when the heading is gone."""
    marker = f"\n{heading}\n"
    if marker not in text:
        return None
    return text.split(marker, 1)[1].split("\n## ", 1)[0]


def pin_improvement_harness(text):
    body = section(text, "## Improvement library")
    if body is None:
        return ["missing '## Improvement library' section"]
    return [f"improvement library misses {w!r}"
            for w in ("harnessing-level recursion", "EXPERIENCE.md") if w not in body]


def pin_branch_name(text):
    return [] if "selfimprove/YYYY-MM-DD" in text else ["missing branch 'selfimprove/YYYY-MM-DD'"]


def pin_data_dir(text):
    body = section(text, "## Data dir")
    if body is None:
        return ["missing '## Data dir' section"]
    return [f"data dir misses {w!r}"
            for w in ("SELF_IMPROVEMENT_DATA", "library/", "runs/", "probes/baseline/base1/",
                      "probes/baseline/basek/", "checkpoints/", "winner.diff",
                      "candidates/", "verdicts/", "adoption.md") if w not in body]


def pin_fork_rule(text):
    body = section(text, "## Fork rule")
    if body is None:
        return ["missing '## Fork rule' section"]
    return ["fork rule misses 'fork'"] if "fork" not in body.lower() else []


MAPPING = {
    "system prompt": "SKILL.md",
    "guardrails": "SKILL.md",
    "tool guidance": "SKILL.md",
    "memory": "references/memory.md",
    "subagents": "agents/",
    "skills": "`SKILL.md` in `SKILL_DIR` and `SKILL_DIR/references/`",
    "scripts": "templates/",
    "plugins": "plugins/",
}


def pin_component_mapping(text):
    errors = []
    for component, target in MAPPING.items():
        row = next((ln for ln in text.splitlines() if ln.startswith(f"| {component} |")), "")
        if not row:
            errors.append(f"no mapping row for {component!r}")
        elif target not in row:
            errors.append(f"mapping row for {component!r} misses {target!r}")
    return errors


def pin_baseline_step(text):
    errors = []
    for phrase in ("unmodified clone at HEAD", "probes/baseline/"):
        if phrase not in text:
            errors.append(f"baseline step misses {phrase!r}")
    return errors

def pin_k_baseline_schedule(text):
    phrases = ("Make k baseline runs",
               "k baseline runs + 2k candidate probes + k checkpoint runs = 4k rollouts")
    return [f"schedule misses {p!r}" for p in phrases if p not in text]

def pin_final_gate(text):
    phrases = ("the checkpoint's diff against the baseline skill state", "drops the checkpoint",
               "keeps the gate at `k` 1 on purpose", "winner-versus-baseline")
    return [f"final gate misses {p!r}" for p in phrases if p not in text]

# The gate wording, shared with prompts.md. The gate compares to the best baseline result.
GATE_HEAD = (
    "The baseline result on a check is the best result over `base1`..`basek`. An exit-code "
    "check passes when any baseline run passes. A count check takes the best baseline count. "
)
# The tie order of the gate: a tie does not drop out, the blind review settles it.
NEW_TIE_ORDER = (
    "A candidate or a checkpoint that is worse than that result drops out. A tie does not "
    "drop out. It goes to the blind review, which decides the tie. When the review prefers "
    "neither, the baseline wins."
)
# The old tie order. It dropped a tied candidate before the blind review ran.
OLD_TIE_ORDER = (
    "A candidate or a checkpoint must be strictly better than that result. Ties go to the "
    "baseline, unless the blind review prefers the candidate on an equal result. A candidate "
    "that fails this gate drops out."
)
GATE_BASELINE = GATE_HEAD + NEW_TIE_ORDER

def pin_best_baseline_gate(text):
    errors = []
    if GATE_BASELINE not in text:
        errors.append("the gate misses the best-baseline rule")
    if "Ties go to the baseline" in text:
        errors.append("the gate still drops a tie before the blind review")
    if "worse than the baseline result on the same check" in text:
        errors.append("the gate still compares to one baseline result")
    if "the same as the baseline runs" not in text:
        errors.append("the probe step still cites one baseline run")
    return errors

def pin_checkpoint_terms(text):
    phrases = ("composed skill state", "checkpoint run", "one per aggregate")
    return [f"checkpoint terms miss {p!r}" for p in phrases if p not in text]

def pin_step_order(text):
    """The baseline run must precede `Propose`: proposals need its run evidence."""
    body = section(text, "## The loop")
    if body is None:
        return ["missing '## The loop' section"]
    steps = {}
    for line in body.splitlines():
        m = re.match(r"(\d+)\.\s+(.*)", line)
        if m:
            steps[int(m.group(1))] = m.group(2)
    baseline = min((n for n, t in steps.items() if "baseline run" in t), default=None)
    propose = min((n for n, t in steps.items() if "`Propose`" in t), default=None)
    if baseline is None or propose is None:
        return ["the loop misses the baseline step or the Propose step"]
    return [] if baseline < propose else [
        f"the baseline run is step {baseline} but `Propose` is step {propose}"
    ]


def pin_lessons(text):
    errors = []
    if "Supersedes" not in text:
        errors.append("lessons.md misses the Supersedes rule")
    if "L-NNN" not in text:
        errors.append("lessons.md misses the L-NNN id rule")
    return errors

def pin_candidate_ids(text):
    return [f"candidate id scheme misses {w!r}"
            for w in ("s1g", "s1d", "skg", "skd") if w not in text]

def pin_prompts_mirror(text):
    """prompts.md must carry the same edit targets and the same layout lines as SKILL.md."""
    errors = [f"prompts.md misses mapping target {t!r}" for t in MAPPING.values() if t not in text]
    for w in ("probes/baseline/", "probes/CAND_ID/", "candidates/", "verdicts/", "adoption.md"):
        if w not in text:
            errors.append(f"prompts.md misses layout line {w!r}")
    return errors


def drop_section(text, heading):
    start = text.index(heading)
    end = text.find("\n## ", start)
    end = len(text) if end == -1 else end + 1
    return text[:start] + text[end:]


def drop_lines(text, *needles):
    lines = text.splitlines(keepends=True)
    kept = [ln for ln in lines if not any(n in ln for n in needles)]
    assert kept != lines, f"no line matched {needles}"
    return "".join(kept)


def drop_table(text):
    lines = text.splitlines(keepends=True)
    kept = [ln for ln in lines if not ln.startswith("|")]
    assert kept != lines, "no table lines found"
    return "".join(kept)

def old_step_order(text):
    """Put `Propose` back at step 2 and the baseline run at step 3."""
    lines = text.splitlines(keepends=True)
    hits = {}
    for i, ln in enumerate(lines):
        m = re.match(r"(\d+)\.\s+(.*)", ln)
        if not m:
            continue
        if "baseline run" in m.group(2) and "base" not in hits:
            hits["base"] = (i, m.group(1), m.group(2).rstrip("\n"))
        if "`Propose`" in m.group(2) and "prop" not in hits:
            hits["prop"] = (i, m.group(1), m.group(2).rstrip("\n"))
    (bi, bn, btxt), (pi, pn, ptxt) = hits["base"], hits["prop"]
    lines[bi] = f"{bn}. {ptxt}\n"
    lines[pi] = f"{pn}. {btxt}\n"
    return "".join(lines)


# One mutation per pin: name, repo file, pin, mutator that deletes the pin target.
MUTATIONS = [
    ("improvement library section", SKILL_MD, pin_improvement_harness,
     lambda t: drop_section(t, "## Improvement library")),
    ("selfimprove/YYYY-MM-DD branch name", SKILL_MD, pin_branch_name,
     lambda t: t.replace("selfimprove/YYYY-MM-DD", "selfimprove/YYYYMMDD")),
    ("data dir section", SKILL_MD, pin_data_dir,
     lambda t: drop_section(t, "## Data dir")),
    ("fork rule section", SKILL_MD, pin_fork_rule,
     lambda t: drop_section(t, "## Fork rule")),
    ("component mapping table", SKILL_MD, pin_component_mapping, drop_table),
    ("baseline step", SKILL_MD, pin_baseline_step,
     lambda t: drop_lines(t, "unmodified clone at HEAD", "Record its trajectory")),
    ("baseline-before-Propose step order", SKILL_MD, pin_step_order, old_step_order),
    ("references/lessons.md Supersedes rule", LESSONS_MD, pin_lessons,
     lambda t: drop_lines(t, "Supersedes")),
    ("sequential CAND_ID scheme", SKILL_MD, pin_candidate_ids,
     lambda t: t.replace("and `s1g`, `s1d` up to `skg`, `skd` in `sequential` mode",
                         "and `s1`..`sk` in `sequential` mode")),
    ("prompts.md mapping targets", PROMPTS_MD, pin_prompts_mirror,
     lambda t: drop_lines(t, *sorted(set(MAPPING.values())))),
    ("prompts.md layout lines", PROMPTS_MD, pin_prompts_mirror,
     lambda t: drop_lines(t, "probes/baseline/", "candidates/", "verdicts/", "adoption.md")),
]


def test_pins_pass_on_the_repo_files():
    for name, path, pin, _ in MUTATIONS:
        assert pin(path.read_text()) == [], f"the {name} pin fails on the repo file"


def test_pins_fail_when_the_target_is_deleted(tmp_path):
    for i, (name, path, pin, mutate) in enumerate(MUTATIONS):
        original = path.read_text()
        mutated = mutate(original)
        assert mutated != original, f"the {name} mutation did nothing"
        copy = tmp_path / f"copy-{i}{path.suffix}"
        copy.write_text(mutated)
        errors = pin(copy.read_text())
        state = "failed-loud" if errors else "SILENT PASS"
        print(f"mutation: {name} deleted -> {state}: {errors}")
        assert errors, f"the {name} pin must fail when its target is deleted"

# The old wording each fix replaced. A pin must fail on it.
OLD_BASELINE_STEP = (
    "2. Make a baseline run. Run the unmodified clone at HEAD in its own worktree on the same "
    "task. Record its trajectory and its deliverable in `probes/baseline/` of the run dir "
    "before the candidate runs."
)
# The current schedule sentence. The pin deletes it, so it must fail without it.
CURRENT_SCHEDULE_SENTENCE = (
    "One run is k baseline runs + 2k candidate probes + k checkpoint runs = 4k rollouts "
    "and 3k improvement stages.\n"
)
NEW_BASELINE_STEP = (
    "2. Make k baseline runs. Run the unmodified clone at HEAD in its own worktree on the "
    "same task, once per baseline run. Record the trajectory and the deliverable of each in "
    "`probes/baseline/base1/` to `probes/baseline/basek/` of the run dir before the candidate "
    "runs."
)
NEW_STEP6 = (
    "6. `Compose` one winner. Merge supported changes. Revise changes that do not agree. Keep "
    "the current skill when no change has support. Each composed state is a `checkpoint`, and "
    "its own `checkpoint run` gives the result. Gate that result with the step 5 task check. "
    "One provenance-blind adversarial review takes the checkpoint's diff against the baseline "
    "skill state. A bad check "
    "result or a failing judge drops the checkpoint back to revision or to the current skill. "
    "When `k` is more than 1, `Final Selection` compares anonymized deliverables and gives one "
    "back. Selection adds no revision. When `k` is 1, the single checkpoint is the winner and "
    "there is no selection."
)
OLD_STEP6 = (
    "6. `Compose` one winner. Merge supported changes. Revise changes that do not agree. Keep "
    "the current skill when no change has support. When `k` is more than 1, `Final Selection` "
    "compares anonymized deliverables and gives one back. Selection adds no revision. When "
    "`k` is 1, the single checkpoint is the winner and there is no selection."
)
NEW_STEP7 = (
    "7. Stop at `winner ready`. The winner is a checkpoint whose checkpoint run passed both "
    "gates of step 6. The baseline wins ties and failing gates (rule 6). This holds in both "
    "modes and at `k` 1. Upstream harness2 delivers at `k` 1 without a selector session. This "
    "loop keeps the gate at `k` 1 on purpose. The user requirement puts the task check and the "
    "blind review on top. Print the winner diff, its run evidence, and the approval request "
    "(rule 7). Write nothing before user approval."
)
OLD_STEP7 = (
    "7. Stop at `winner ready`. Print the winner diff, its run evidence, and the approval "
    "request (rule 7). Write nothing before user approval."
)
NEW_CHECKPOINT_TERMS = (
    "A `checkpoint` is the composed skill state of one round. Its rollout is the `checkpoint "
    "run`. A checkpoint takes the id `c1`..`ck` in `sequential` mode, one per round, or "
    "`agg1`..`aggk` in `parallel` mode, one per aggregate."
)
OLD_CHECKPOINT_TERMS = (
    "The `checkpoint` is the composed run of one round. It takes the id `c1`..`ck` in "
    "`sequential` mode, or `agg1`..`aggk` in `parallel` mode."
)

def test_k_baseline_count_and_4k_schedule(tmp_path):
    assert pin_k_baseline_schedule(SKILL_MD.read_text()) == []
    old = SKILL_MD.read_text().replace(NEW_BASELINE_STEP, OLD_BASELINE_STEP)
    old = old.replace(CURRENT_SCHEDULE_SENTENCE, "")
    copy = tmp_path / "SKILL.md"
    copy.write_text(old)
    assert pin_k_baseline_schedule(copy.read_text()), "the pin must fail on the old text"

def test_final_gate_on_the_composed_winner_including_k1(tmp_path):
    assert pin_final_gate(SKILL_MD.read_text()) == []
    old = SKILL_MD.read_text().replace(NEW_STEP6, OLD_STEP6).replace(NEW_STEP7, OLD_STEP7)
    copy = tmp_path / "SKILL.md"
    copy.write_text(old)
    assert pin_final_gate(copy.read_text()), "the pin must fail on the old text"
    # The old review subject at SKILL.md:28. The pin must fail on it too.
    mid = SKILL_MD.read_text().replace(
        "Gate that result with the step 5 task check. One provenance-blind adversarial review "
        "takes the checkpoint's diff against the baseline skill state.",
        "Gate that result with the step 5 task check and one provenance-blind adversarial "
        "review against the baseline deliverable.",
    )
    assert mid != SKILL_MD.read_text(), "the review-subject mutation did nothing"
    copy.write_text(mid)
    assert pin_final_gate(copy.read_text()), "the pin must fail on the old review subject"

def test_checkpoint_state_and_run_terms(tmp_path):
    assert pin_checkpoint_terms(SKILL_MD.read_text()) == []
    old = SKILL_MD.read_text().replace(NEW_CHECKPOINT_TERMS, OLD_CHECKPOINT_TERMS)
    copy = tmp_path / "SKILL.md"
    copy.write_text(old)
    assert pin_checkpoint_terms(copy.read_text()), "the pin must fail on the old text"

# The old check gate at SKILL.md:27. The pin must fail on it.
OLD_CHECK_GATE = (
    "A check result is bad when it is worse than the baseline result on the same check. An "
    "exit-code check compares exit codes. A count check compares counts, including when the "
    "baseline count is nonzero. A candidate with a bad check result drops out."
)

def test_gate_compares_to_the_best_baseline_result(tmp_path):
    assert pin_best_baseline_gate(SKILL_MD.read_text()) == []
    old = SKILL_MD.read_text().replace(GATE_BASELINE, OLD_CHECK_GATE)
    old = old.replace("the same as the baseline runs.", "the same as the baseline run.")
    assert old != SKILL_MD.read_text(), "the check-gate mutation did nothing"
    copy = tmp_path / "SKILL.md"
    copy.write_text(old)
    assert pin_best_baseline_gate(copy.read_text()), "the pin must fail on the old check gate"
    # The old tie order drops a tied candidate before the blind review runs.
    tied = SKILL_MD.read_text().replace(NEW_TIE_ORDER, OLD_TIE_ORDER)
    assert tied != SKILL_MD.read_text(), "the tie-order mutation did nothing"
    copy.write_text(tied)
    assert any("drops a tie" in e for e in pin_best_baseline_gate(copy.read_text())), \
        "the pin must fail on the old 'drops out' order"
