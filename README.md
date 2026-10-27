# skill-self-improvement

Improve a skill with harness2's Propose-Probe-Compose loop. Non-destructive: candidates run on copies, nothing goes live without approval.

## What it does

The skill runs the self-improvement method of [harness2](https://github.com/google-research/harness2), described in the [paper](https://arxiv.org/abs/2610.14224). Each round is one task-level Propose-Probe-Compose step. Baseline runs show the current skill at work. The loop then proposes candidates, probes each candidate on the same task, and composes the next skill from the behavioral contrasts. A task check and a provenance-blind adversarial review gate the candidates and the composed winner on top of the contrasts. The loop proposes two types of candidate. General candidates target agent behavior that applies to all tasks, such as planning and tool use. Domain candidates target the knowledge and procedures of the skill domain. The loop has two modes, parallel and sequential, and a parameter k, default 1. One run schedules 4k rollouts and 3k improvement stages. The cost is linear in k. Harnessing-level recursion keeps one improvement library in the data dir for all rounds. That improvement library holds the adopted skill trees and the evidence-backed lessons its rounds support. The method can edit all eight harness components: system prompt, guardrails, memory, tool guidance, subagents, skills, scripts, and plugins. Memory is `references/memory.md` in the target skill repo. Subagents are role briefs in `agents/*.md` of the target repo. Plugins are the plugin files and the hook files of the target repo. Files that are not in the target repo get a proposed diff only (rule 4). The loop makes no code changes to your harness, the skill drives existing tools.

## Non-destructive rules

The loop obeys seven rules.

1. Candidates run on copies. A candidate does not edit the live skill tree or the live config.
2. Adoption is one commit on a new `selfimprove/YYYY-MM-DD` branch. The loop does not force-push, rewrite history, or delete a branch. Use `git revert` to cancel an adoption.
3. Nothing goes live without approval. Make a timestamped backup first. The adoption report shows the backup and the one-line restore command.
4. The loop proposes harness config changes as diffs only. It does not edit a harness config file.
5. Lessons and run evidence are append-only. An incorrect lesson gets a new entry with `Supersedes: L-NNN`. An incorrect library entry gets a new entry with `Supersedes: E-NNN`.
6. The baseline wins when scores are equal. A failing judge, a regressed task check, or an unclear result also keeps the baseline.
7. The approval request gives one line for each removed rule line and for each removed guardrail line, and labels a removed line that only cuts an example of a surviving rule.

## Install

| Harness | Command |
|---|---|
| Claude Code | `claude plugin marketplace add DiamonDinoia/skill-self-improvement && claude plugin install self-improvement@self-improvement --scope user` |
| Codex CLI | `codex plugin marketplace add DiamonDinoia/skill-self-improvement`, then `codex plugin add self-improvement@self-improvement` |
| Gemini CLI | `gemini extensions install https://github.com/DiamonDinoia/skill-self-improvement --consent` |
| Hermes | `git clone https://github.com/DiamonDinoia/skill-self-improvement && ./skill-self-improvement/install.sh` |
| opencode (by hand, scripted) | `git clone https://github.com/DiamonDinoia/skill-self-improvement && ./skill-self-improvement/install.sh` |
| by hand | `git clone https://github.com/DiamonDinoia/skill-self-improvement && ln -s "$PWD/skill-self-improvement/skills/self-improvement" ~/.claude/skills/self-improvement` |

The three harnesses with a native manifest have one in this repository: `.claude-plugin/` for Claude Code, `.codex-plugin/` for Codex, and `gemini-extension.json` for Gemini CLI. `install.sh` symlinks the skill into the opencode and Hermes skill directories and the `/self-improvement` command into opencode. For a harness not in this table, install by hand, see the last row.

## Fork first

Fork this repo. Fork each skill repo to improve. Then work from clones of the forks.

- Point the loop at the fork clone. The upstream clone stays read-only for the loop.
- The loop commits improvements and pushes to the fork remote only.
- Sending a fix upstream is a manual pull request. Only the fork owner opens it.

Run evidence goes to a configurable local data dir: the `SELF_IMPROVEMENT_DATA` environment variable, default `~/.local/share/self-improvement`. Each target skill gets one `library/` subtree for the improvement library and one `runs/` subtree for the run evidence.

## License

MIT for this repository. The improvement method and the adapted prompts derive from harness2, Apache-2.0. See `NOTICE`.
