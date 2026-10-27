---
name: self-improvement
description: "Use when a run shows a skill fault. Non-destructive."
version: 0.1.0
license: MIT
---

# Self-improvement

Make one skill better with the Propose-Probe-Compose method of harness2, arXiv 2610.14224.
The loop changes a skill clone. A candidate run writes to its worktree and the data dir only.

## When to use

- A run shows a fault in one skill, and the user wants a tested change.
- The user wants one improvement round and a checkable winner.
- Do not use for: an urgent change, or a change to the agent memory store.

## The loop

Task-level recursion covers one run. Harnessing-level recursion moves the result into the next run. The steps are `Propose`, `Probe`, `Compose`, `Final Selection` (when `k` is more than 1), `Reflect`, and `Update`.

1. Read the improvement library from the data dir first. The target is a skill clone. It is the owner's clone or the installer's fork.
2. Make k baseline runs. Run the unmodified clone at HEAD in its own worktree on the same task, once per baseline run. Record the trajectory and the deliverable of each in `probes/baseline/base1/` to `probes/baseline/basek/` of the run dir before the candidate runs.
3. `Propose` candidate changes. Make general candidates and domain candidates. Put each candidate in its own git worktree.
4. `Probe` each candidate on the same task. Keep the model and the environment the same as the baseline runs. Each probe has its own worktree of the target at the candidate's state. It gets the path of the `SKILL.md` there, reads and follows that file, and not the installed copy. Record its trajectory and its deliverable in `probes/CAND_ID/` of the run dir. Compare the trajectory and the deliverable with the best baseline result. This behavioral contrast is ground-truth-free. It shapes composition, and it does not show that the output is correct.
5. Use the task check command when the target has one. It gates the candidates. The baseline result on a check is the best result over `base1`..`basek`. An exit-code check passes when any baseline run passes. A count check takes the best baseline count. A candidate or a checkpoint that is worse than that result drops out. A tie does not drop out. It goes to the blind review, which decides the tie. When the review prefers neither, the baseline wins. Then compare each surviving candidate against the baseline in a provenance-blind adversarial review. On Hermes, use `hermes-adversarial-review`. When that launcher is missing on the harness in use, spawn a new no-context subagent with the reviewer prompt from `references/prompts.md`. The task check and this review gate on top of the contrast.
6. `Compose` one winner. Merge supported changes. Revise changes that do not agree. Keep the current skill when no change has support. Each composed state is a `checkpoint`, and its own `checkpoint run` gives the result. Gate that result with the step 5 task check. One provenance-blind adversarial review takes the checkpoint's diff against the baseline skill state. A bad check result or a failing judge drops the checkpoint back to revision or to the current skill. When `k` is more than 1, `Final Selection` compares anonymized deliverables and gives one back. Selection adds no revision. When `k` is 1, the single checkpoint is the winner and there is no selection.
7. Stop at `winner ready`. The winner is a checkpoint whose checkpoint run passed both gates of step 6. The baseline wins ties and failing gates (rule 6). This holds in both modes and at `k` 1. Upstream harness2 delivers at `k` 1 without a selector session. This loop keeps the gate at `k` 1 on purpose. The user requirement puts the task check and the blind review on top. Print the winner diff, its run evidence, and the approval request (rule 7). Write nothing before user approval.
8. On user approval, run `python3 scripts/si.py backup SRC --dest DIR` on the installed skill. The script is `scripts/si.py` in the directory that holds this `SKILL.md`. The adoption report prints the `restore: ` line it gives (rule 3). Then `Reflect` as in step 9, and commit the winner and the appended lessons as one commit on branch `selfimprove/YYYY-MM-DD`. Update the installed skill.
9. `Reflect` appends each lesson to `references/lessons.md` of the target skill and to `SKILL_NAME/library/` in the data dir. The append goes into the adoption commit of step 8 on branch `selfimprove/YYYY-MM-DD`. Update the improvement library with the adopted skill tree and its `EXPERIENCE.md`. Write the run evidence to the data dir.

## Modes and schedule

`k` is a parameter. The default is `k=1` to bound cost. The user sets `k`.

- `parallel`: `Probe` `k` general candidates and `k` domain candidates, then make `k` compositions.
- `sequential`: refine the skill in `k` successive rounds, with one general candidate and one domain candidate in each round.

One run follows this schedule. From the harness2 clone at `1cfe254e`, `harness2/core/recursion.py` L15-19 and `harness2/core/ledger.py` L27-34:

```
Each mode schedules 4k rollouts and 3k improvement stages, including shared base
executions. Invalid proposals receive one retry before inheriting the current harness.
P = 3k: k INV + k DOM + k compositions (parallel: agg1..aggk; sequential: c1..ck).
```

One run is k baseline runs + 2k candidate probes + k checkpoint runs = 4k rollouts and 3k improvement stages.

These counts are for one run, not for the repo (`recursion.py` L15-19). `INV` names the general dimension and `DOM` names the domain dimension in the harness2 code. In that quote, an invalid proposal is one the stage rejects. Its worktree is missing or empty, a file is off the editable surface, or the tree check fails. The retry is one more proposer run on the same evidence. After two attempts the stage keeps the current state. One run at `k=1` costs several subagent hours, so set a deadline for each subagent.

## Improvement library

The improvement library is the harnessing-level recursion of harness2. The paper calls it the improvement harness. It is continuous, it lives in the data dir, and each run reads it at the start. Each entry holds the adopted skill tree, an id `E-NNN` in sequence, and an `EXPERIENCE.md`. The `EXPERIENCE.md` records the applicable condition, the lesson, and the supporting run evidence. An index lists the entries. When no contrast supports a lesson, add no entry.

## Edit targets

Harness2 defines 8 components: system prompt, guardrails, memory, tool guidance, subagents, skills, scripts, plugins. All 8 components are edit targets of the loop. The loop makes no code change to Hermes or to other harnesses. It calls only the tools of the harness.

Each mission gets two paths at run start. `REPO_ROOT` is the git top level of the target repo. `SKILL_DIR` holds the target `SKILL.md`. It equals `REPO_ROOT` or `REPO_ROOT/skills/NAME`. Skill paths in the table are relative to `SKILL_DIR`. Plugin and manifest paths are relative to `REPO_ROOT`. Never create a root `SKILL.md` when `SKILL_DIR` differs from `REPO_ROOT`.

| component | edit target in the target repo |
|---|---|
| system prompt | sections of `SKILL_DIR/SKILL.md` |
| guardrails | sections of `SKILL_DIR/SKILL.md` |
| tool guidance | sections of `SKILL_DIR/SKILL.md` |
| memory | `SKILL_DIR/references/memory.md`. Make the file when it is missing. This is not the agent memory store. |
| subagents | role briefs in `SKILL_DIR/agents/<name>.md`. Make the files when they are missing. |
| skills | the `SKILL.md` in `SKILL_DIR` and `SKILL_DIR/references/` |
| scripts | `SKILL_DIR/scripts/` and `SKILL_DIR/templates/` |
| plugins | the plugin files and the hook files of the target repo: `REPO_ROOT/plugins/`, `REPO_ROOT/hooks/`, `REPO_ROOT/.claude-plugin/`, `REPO_ROOT/.codex-plugin/`, `REPO_ROOT/gemini-extension.json`, `REPO_ROOT/.opencode/` |

Files that are not in the target repo (`config.yaml` of the harness, `AGENTS.md`, `CLAUDE.md`, `SOUL.md`) get a proposed diff only (rule 4).

## Non-destructive rules

Each rule is a gate. The loop drops a candidate that breaks one rule.

1. `run on copies`. Each candidate gets its own git worktree or scratch tree. A candidate run does not touch the installed skill or the live config.
2. `new branch`, `no force-push`. Adoption is one commit on a new branch. Do not rewrite history and do not delete a branch. Use `git revert` to cancel an adoption.
3. `without approval`, `backup`. Nothing goes live without approval. Make a timestamped `backup` first, and print the one-line `restore` command.
4. `proposed diffs only`. A harness config change is a proposed diff. Do not write the file.
5. `append-only`. Lessons and run evidence are append-only. An incorrect lesson gets a new entry with `Supersedes: L-NNN`. An incorrect library entry gets a new entry with `Supersedes: E-NNN`.
6. `baseline wins ties`. A failing judge, a regressed task check or an unclear result means no adoption. The baseline stays. The rule covers the winner-versus-baseline review too.
7. `removed rule`. The approval request gives one line for each removed rule line and for each removed guardrail line. Label a removed line that only cuts an example of a surviving rule.

## Helper commands

The helper script is `scripts/si.py`.

- `python3 scripts/si.py backup SRC --dest DIR` copies SRC into DIR. It prints a line that starts `restore: `.
- `python3 scripts/si.py restore BACKUP SRC` copies the current `SRC` to a `backup` file first, then copies `BACKUP` onto `SRC`.
- `python3 scripts/si.py removed-rules DIFF` reads a unified diff file. Use `-` for stdin. It prints each removed line that has text as `path:line: text`.

## Fork rule

Installers fork this repo and each target skill. An installer pushes the changes to their own fork. Upstream PRs are manual.

## Data dir

`SELF_IMPROVEMENT_DATA` names the data dir. The default is `~/.local/share/self-improvement`. One subtree holds each target skill `SKILL_NAME`:

- `SKILL_NAME/library/index.md` and `SKILL_NAME/library/entries/`: the improvement library. It holds the adopted skill states and the evidence-backed lessons. Each run reads it at the start.
- `SKILL_NAME/runs/RUN_ID/task.md`: the task and its check command.
- `SKILL_NAME/runs/RUN_ID/probes/baseline/base1/` to `SKILL_NAME/runs/RUN_ID/probes/baseline/basek/` and `SKILL_NAME/runs/RUN_ID/probes/CAND_ID/`: the `trajectory.md` and the deliverable for each run.
- `SKILL_NAME/runs/RUN_ID/checkpoints/CHECKPOINT_ID/`: the `trajectory.md` and the deliverable of each checkpoint run.
- `SKILL_NAME/runs/RUN_ID/selection/`: the shuffled, output-only selection directory. It holds `task.md`, `source/`, and `candidates/<id>.md` with the declared assets. The id map is written after the verdict.
- `SKILL_NAME/runs/RUN_ID/winner.diff`: the winner diff of step 7.
- `SKILL_NAME/runs/RUN_ID/candidates/CAND_ID.diff`, `SKILL_NAME/runs/RUN_ID/verdicts/CAND_ID.md`, and `SKILL_NAME/runs/RUN_ID/adoption.md`: the candidate diff, its verdict, and the adoption record.

`RUN_ID` is a UTC timestamp. `CAND_ID` is `g1`..`gk` and `d1`..`dk` in `parallel` mode, and `s1g`, `s1d` up to `skg`, `skd` in `sequential` mode. Round `i` of `sequential` mode probes `s{i}g` and `s{i}d`. A `checkpoint` is the composed skill state of one round. Its rollout is the `checkpoint run`. A checkpoint takes the id `c1`..`ck` in `sequential` mode, one per round, or `agg1`..`aggk` in `parallel` mode, one per aggregate. `composition` names the act of composing. Do not write host names or home paths into text the loop adds to skill files. Do not cut target-skill text because of this rule. A path that documents the target skill's own locations stays.
