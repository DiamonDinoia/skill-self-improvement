# Changelog

## 0.3.0

- `INSTALL.md` detects the environment and asks one batched question message with the detected defaults. It shows the plan. The agent acts after the user approves the plan.
- No self-fork: when the GitHub login owns `DiamonDinoia/skill-self-improvement`, the agent uses the existing clone.
- Codex CLI gets a link into `${CODEX_HOME:-$HOME/.codex}/skills` when that folder exists. That folder route is observed, not documented. The plugin route is the fallback.
- A harness plugin command runs only after the user approves the shown plan. Otherwise the agent prints it for the user.

## 0.2.0

- `install.sh` is replaced by agent install instructions in `INSTALL.md`.
- The agent installs the skill into its own harness by a link of the skill folder.
- The README tells the user to fork the repo, clone the fork, and tell the agent to follow `INSTALL.md`.

## 0.1.0

- First release.
