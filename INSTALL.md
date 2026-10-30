# Install

An agent follows these steps to install the self-improvement skill in the harnesses that the user chooses. The agent detects the environment, asks the user in one message, shows the plan, and installs after the user approves the plan. The report lists the result for each chosen harness.

## Hard rules

1. Never fork a repository that you own. GitHub blocks a fork of your own repository. When the login of `gh api user --jq .login` is `DiamonDinoia`, use the existing clone. Check: the clone is the fork clone or the existing clone of your own repository.
2. Name the harness that runs this agent, and tell the user. If the agent cannot tell which harness runs it, ask the user and stop until the user answers. Check: the report names one harness of Claude Code, Codex CLI, Gemini CLI, OpenCode, or Hermes.
3. Ask all questions in one message before the plan. Wait for the answers. Each question carries its detected default: which harnesses (default: only the harness that runs this agent), fork or clone (default: fork), link or plugin route where both exist (default: link). Check: the message shows the three questions with their detected defaults.
4. Show the plan and wait for the user approval. Change nothing before the approval. Check: the plan names each link and each plugin command.
5. Install in the chosen harnesses only. Install only by a symlink of the skill folder. Do not edit a harness config file by hand. There is one exception. A harness plugin command writes a harness config file. Run it only after the user approves the shown plan. Otherwise print it for the user. The user runs the command. Check: the plan names each plugin command that the agent runs.
6. If anything else is at the link name, stop and tell the user the path. Do not move, back up or delete it. This stop ends that harness only. Continue with the next chosen harness. Check: the report names the path.
7. Tell the user to restart the harness. Check: the report names the harness.
8. If a command that changes state exits non-zero, stop and report. Keep all paths as they are. A detection probe only reads state. Its non-zero exit is an absent result, not a command failure.

## Steps

1. Detect the environment, and tell the user. Run `gh api user --jq .login` for the GitHub login. Run `git remote -v` in the clone when a clone exists. Run `test -d` on the parent folder of each link name in the table below. Name the harness that runs this agent (hard rule 2). Every command here only reads state (hard rule 8), so an absent login, clone or folder is an answer. Check: the report shows the login, the remotes and the folders that exist.
2. Ask all questions in one message (hard rule 3), and wait for the answers.
3. Show the plan and wait for the user approval (hard rule 4). Change nothing before the approval. Check: the plan names each link and each plugin command.
4. Get the source after the user approves the plan, as the user answered in step 2. When the login is `DiamonDinoia`, use the existing clone (hard rule 1). Check: `git remote -v` runs in that clone. When the answer is fork, fork `DiamonDinoia/skill-self-improvement` and clone the fork. Check: `git remote -v` shows the fork as `origin`. When the answer is clone, clone `DiamonDinoia/skill-self-improvement`. Then run each approved plugin command. Print the other plugin commands for the user.
5. For each chosen harness, get the link name in the table below. Enclose each path argument in ordinary shell double quotes. Do not add backslashes. Resolve the source `skills/self-improvement` in the clone with `realpath`. Keep the result as the absolute source. Check: the result starts with `/`. Test the link name with `test -L`. If `test -L` exits non-zero, continue at step 6. If `test -L` exits 0, print `readlink -f` of the link name. If the result equals the absolute source and `test -e` of the link name exits 0, do no more for this harness. Report this. Continue with the next chosen harness.
6. If the parent folder of the link name is absent, make it with `mkdir -p "$(dirname "<link name>")"`. If that command exits non-zero, stop and report. Check: `test -d` of the parent folder exits 0.
7. If nothing is at the link name (`test -e` and `test -L` exit non-zero), make the link. Example: `ln -sTn "<absolute source>" "<link name>"`. Check: `readlink -f` of the link name equals the absolute source and `test -e` of the link name exits 0.
8. If anything else is at the link name, stop and tell the user the path. Do not move, back up or delete it. Continue with the next chosen harness. Check: the report names the path.
9. Tell the user to restart the harness. Check: the report names the harness and the result for each chosen harness.

## Link name for each harness

| Harness | Link name |
|---|---|
| Claude Code | `$HOME/.claude/skills/self-improvement` |
| Codex CLI | `${CODEX_HOME:-$HOME/.codex}/skills/self-improvement` |
| OpenCode | `${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills/self-improvement` |
| Hermes | `${HERMES_HOME:-$HOME/.hermes}/skills/self-improvement` |

The Codex CLI folder route is observed on one machine (`$HOME/.codex/skills` exists there). It is not documented by Codex CLI. When that folder is absent, use the plugin route for Codex CLI. Gemini CLI has no link name in this table. Use its plugin route. A plugin route is the native install command in the README. For Claude Code and Codex CLI both routes exist. Hard rule 3 asks which route. Hard rule 5 covers who runs a plugin command.
