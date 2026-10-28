# Install

An agent follows these steps to install the self-improvement skill in the harness that runs the agent. The agent installs in its own harness only, by one symlink of the skill folder.

## Hard rules

1. Fork this repository first, and clone the fork. Check: the clone has the fork as its remote.
2. Name the harness that runs this agent, and tell the user. If the agent cannot tell which harness runs it, ask the user and stop until the user answers. Check: the report names one harness of Claude Code, Codex CLI, Gemini CLI, OpenCode, or Hermes.
3. Install in that harness only. Install only by a symlink of the skill folder. Do not run a command that writes a harness config file. Do not edit a harness config file by hand. Check: the plan names one link and no config file.
4. If anything else is at the link name, stop and tell the user the path. Do not move, back up or delete it. Check: the report names the path.
5. Tell the user to restart the harness. Check: the report names the harness.
6. If a command exits non-zero, stop and report. Keep all paths as they are.

## Steps

1. Fork the repository `DiamonDinoia/skill-self-improvement` on GitHub, and clone the fork. Check: `git remote -v` shows the fork as `origin`.
2. Name the harness that runs this agent, and tell the user. If the agent cannot tell which harness runs it, ask the user and stop until the user answers. Check: the report names one of the five harness names.
3. Get the link name of that harness in the table below. Enclose each path argument in ordinary shell double quotes. Do not add backslashes.
4. Resolve the source `skills/self-improvement` in the clone with `realpath`. Keep the result as the absolute source. Check: the result starts with `/`.
5. Test the link name with `test -L`. If `test -L` exits non-zero, continue at step 6. If `test -L` exits 0, print `readlink -f` of the link name. If the result equals the absolute source and `test -e` of the link name exits 0, do no more. Report this and stop.
6. If the parent folder of the link name is absent, make it with `mkdir -p "$(dirname "<link name>")"`. If that command exits non-zero, stop and report. Check: `test -d` of the parent folder exits 0.
7. If nothing is at the link name (`test -e` and `test -L` exit non-zero), make the link. Example: `ln -sTn "<absolute source>" "<link name>"`. Check: `readlink -f` of the link name equals the absolute source and `test -e` of the link name exits 0.
8. If anything else is at the link name, stop and tell the user the path. Do not move, back up or delete it. Check: the report names the path.
9. Tell the user to restart the harness. Check: the report names the harness.

## Link name for each harness

| Harness | Link name |
|---|---|
| Claude Code | `$HOME/.claude/skills/self-improvement` |
| OpenCode | `${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills/self-improvement` |
| Hermes | `${HERMES_HOME:-$HOME/.hermes}/skills/self-improvement` |

The Claude Code path comes from the "by hand" row of the README install table. This repository documents no user skill folder for Codex CLI and Gemini CLI. For them the agent prints the native install command in the README for the user. The user runs the command. The agent does not run it.
