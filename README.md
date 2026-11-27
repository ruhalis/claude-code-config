# claude-code-config

Personal agent configuration for **Claude Code**, installed from one source of truth — plus the **VS Code** extension set.

```bash
git clone --recurse-submodules https://github.com/ruhalis/claude-code-config ~/projects/claude-code-config
cd ~/projects/claude-code-config
./install.sh
```

```bash
./install.sh                     # every tool detected on this machine
./install.sh claude              # one tool
./install.sh claude vscode       # several
./install.sh vscode              # merge VS Code settings, install missing extensions
./install.sh skills              # only the skills: global ones and the per-project optional ones
./install.sh all                 # both, detected or not
./install.sh --dry-run all       # print the plan, change nothing
```

**Updating another machine:** `git pull`, then `./install.sh` before opening a Claude Code session. A session reads its hooks at start, and one started on the old settings calls the hook paths those settings name. For that reason `~/.claude/hooks/guard-kicad-edit.sh`, the hook removed on 2026-11-27, stays behind as a no-op file (`install.sh` turns a leftover link there into one): an old session still calls it with `onFailure: block`, and a missing script would block every Edit, Write and Bash. Delete it once every session has restarted.

## Layout

```
core/                  source of truth: agents and skills
  agents/*.md            the specialists, in Claude's format
  skills/*/              global SKILL.md skills: esp-idf, rl-advisor, shopping, anatomy, deep-research
  skills/anatomy/        submodule: wheresryan22/anatomy, pinned (Claude Code only)
  skills/deep-research/  gitignored local copy (see below)
  skills/shopping/       read-only personal shopper for Kazakhstan: store reads (scripts/listing.py), landed cost in KZT, Artifact comparison pages (written for Claude Code: uses Agent and Artifact)
  optional-skills/*/     skills linked only into the projects that use them: isaac, led-animation, motor-bench, pcb-design
  optional-skills/projects.txt   which project directories each optional skill is linked into
adapters/
  claude/                CLAUDE.md + output-styles/ + statusline.sh + settings.json + keybindings.json + hooks/ + mods/ + bin/clangd
  vscode/                extensions.txt — extension IDs to install; settings.json — user settings (merged)
scripts/               bench.sh, check-skills.sh, cleanup.sh
```

## What lands where

| | Claude Code |
| --- | --- |
| Instructions | `~/.claude/CLAUDE.md` (symlink to `adapters/claude/CLAUDE.md`): the rules for every agent |
| Output style | `~/.claude/output-styles/orchestrator.md` (symlink to `adapters/claude/output-styles/orchestrator.md`), selected by `"outputStyle": "orchestrator"` in `settings.json`: the main session's rules. The folder is not swept, so styles of your own stay |
| Agents | `~/.claude/agents/*.md` |
| Skills | `~/.claude/skills/` (global), `<project>/.claude/skills/<name>` (optional, see Skills) |
| Settings | `settings.json` (merged copy) |
| Keybindings | `keybindings.json` (merged copy) |
| Status line | `~/.claude/statusline.sh` (symlink to `adapters/claude/statusline.sh`): model (effort), folder@branch, context %, 5-hour and 7-day usage with reset times. It reads only the JSON Claude Code pipes to it; no network call, no credential. It replaced a third-party submodule that read the login token to fetch usage; that one's "extra usage" segment has no replacement |
| Hooks | `~/.claude/hooks/guard-main-session.sh` and `~/.claude/hooks/guard-git-write.sh` (symlinks to `adapters/claude/hooks/`) |
| clangd wrapper | `~/.local/bin/clangd` (symlink to `adapters/claude/bin/clangd`; `~/.local/bin` must come before `/usr/bin` on `PATH`; a clangd already at that path that is not this link is left alone with a warning). The `clangd-lsp` plugin starts the first `clangd` on `PATH` with a fixed command line, so the wrapper picks the binary by workspace: with an ESP-IDF project (`sdkconfig` or `sdkconfig.defaults` up to three levels down) it runs Espressif's clangd from `~/.espressif/tools/esp-clang` with `--query-driver` for the cross compilers and the system compilers; anywhere else, or without esp-clang, the system clangd unchanged. The project still needs a `.clangd` that removes the GCC-only `-f*`/`-m*` flags and one `idf.py build` for `build/compile_commands.json` |
| Subagent rows | `~/.claude/mods/agent-rows` (symlink to `adapters/claude/mods/agent-rows`): a mod whose `AgentRow` render hook makes the agent list show `type model effort · task · tokens` per running subagent, loaded through `CLAUDE_CODE_PLUGIN_DIRS` in the `env` of settings.json. It replaced the `subagentStatusLine` setting, which Claude Code deprecated in favour of mods; check it with `claude plugin validate` and `claude plugin test` on the folder |

Symlinked items track repo edits live. The two copies — `settings.json` and `keybindings.json` — are copies precisely because Claude Code rewrites `settings.json` in place when you change the theme or model, and a symlink would push those edits back into the repo. Re-run `install.sh` to update them: it backs up the live file, then merges the repo over it, so the repo wins on every key it declares and the live file keeps the rest, with `model`, `modelSettings`, `effortLevel` and `autoMode` staying as Claude Code last wrote them (the repo only seeds them when absent). The merge deletes only the retired keys `JQ_SETTINGS` in `install.sh` names (`subagentStatusLine`, and the plugins and marketplaces removed on 2026-11-27); remove any other key that left the repo by hand or with `/config`. If `jq` is missing, or a live file cannot be merged (invalid JSON, or a top level that is not an object), `install.sh` stops before it changes anything; it never replaces a live file it could not merge.

### Plugin updates

Each plugin updates on its own channel:

| Plugin | How it updates | Why |
| --- | --- | --- |
| `claude-plugins-official` (clangd-lsp, frontend-design, skill-creator; added 2026-11-21: pyright-lsp, claude-md-management, nvidia-skills, session-report) | Claude Code auto-update, on by default for that marketplace. First install on a new machine: `claude plugin install <name>@claude-plugins-official` for each. The two LSP plugins only wire a server that must be on `PATH`: `clangd`, and `pyright-langserver` from `uv tool install pyright` | official marketplace. `nvidia-skills` is one router skill (`nvidia-skill-finder`) that looks NVIDIA's catalogue up over the network (`npx skills add nvidia/skills --list`) and installs nothing without approval |
| `text-to-cad` | Its own CAD server: patch releases (0.11.x) install themselves once nothing is running; minor releases wait for `cad update` or the installer again. `cad update auto off` stops it. As seen on 2026-11-21 (0.11.15), Claude Code installs the plugin as `text-to-cad@earthtojake` from the GitHub marketplace `earthtojake/text-to-cad` at the moving ref `latest` (the `earthtojake` entry in `extraKnownMarketplaces`, no `autoUpdate`); the older local catalog in `~/Library/Application Support/cad/plugin` (`text-to-cad@text-to-cad`) is no longer registered. First install, or moving to a new minor: `curl -fsSL https://texttocad.dev/install.sh \| sh -s -- --only claude --no-telemetry` | before 1.0 a minor release renames commands (0.8 to 0.11 renamed `cadgen`, skills and env vars) |
| `cloudflare` (Cloudflare skills + MCP servers, added 2026-11-15 to deploy and manage sites) | manual: `claude plugin marketplace update cloudflare`, then `claude plugin update cloudflare@cloudflare`. First install on a new machine: `claude plugin marketplace add cloudflare/skills`, `claude plugin install cloudflare@cloudflare`, `/reload-plugins`; the account login is per machine (browser OAuth on the first Cloudflare tool call) | installed as Cloudflare's setup prompt gives it (`developers.cloudflare.com/agent-setup/prompt.md`), with no `autoUpdate`; its MCP servers act on a live account, so updates are taken deliberately: the marketplace is pinned by `ref` to a reviewed commit in `settings.json`, so move that SHA and re-run `install.sh` before the update commands |
| `knowledge-work-plugins` (Anthropic's `data`, `design`, `engineering` and `pdf-viewer`, added 2026-11-16) | Claude Code auto-update: `"autoUpdate": true` on its `extraKnownMarketplaces` entry. First install on a new machine: `claude plugin marketplace add anthropics/knowledge-work-plugins`, then `claude plugin install <name>@knowledge-work-plugins` for each of the four | Anthropic's own marketplace, and the same plugins the claude.ai account sync used to deliver. An update can add a connector server to a plugin; add it to `deniedMcpServers` if it shows up in `/mcp` |
| `anthropic-agent-skills` (`document-skills`: docx, pdf, pptx, xlsx, added 2026-11-16) | Claude Code auto-update: `"autoUpdate": true` on its `extraKnownMarketplaces` entry. First install on a new machine: `claude plugin marketplace add anthropics/skills`, then `claude plugin install document-skills@anthropic-agent-skills` | Anthropic's skills repository; the plugin loads only its four document skills |
| `chrome-devtools` MCP server (not a plugin, added 2026-11-21 for page measurement: performance traces, Lighthouse audits, throttling; `cloudflare:web-perf` is written around its tools) | manual and pinned: it lives in `~/.claude.json`, outside `install.sh`. First install on a new machine, and the way to move the version: `claude mcp remove --scope user chrome-devtools`, then `claude mcp add --scope user chrome-devtools -e CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1 -e CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1 -- npx -y chrome-devtools-mcp@1.11.0 --no-usage-statistics --no-performance-crux` | added by hand instead of the `chrome-devtools-mcp` plugin, whose fixed arguments cannot carry the two opt-outs: by default the server sends usage statistics to Google and looks trace URLs up in Google's CrUX API. It drives its own Chrome profile (`~/.cache/chrome-devtools-mcp/chrome-profile`), not the logged-in browser |

Claude Code's own updater, and with it the plugin pass, is off under `DISABLE_AUTOUPDATER=1`, `DISABLE_UPDATES=1` or `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` unless `FORCE_AUTOUPDATE_PLUGINS=1` is also set.

The `kicad-happy`, `desktop-commander` and `rea` plugins were removed on 2026-11-27 with their marketplaces and permission rules. A copy still installed on a machine is removed through `/plugin`.

### Engineering only: connectors, blocked skills, restored basics

Claude Code on this Mac is for engineering; the Claude app (Chat and Cowork) is the assistant for everything else. Three things keep the two apart:

- **claude.ai connectors are off in terminal sessions.** `~/.zshrc` (not managed by `install.sh`) exports `ENABLE_CLAUDEAI_MCP_SERVERS=false`, so Gmail, Google Calendar, Linear and Claude Docs do not load. Two shell functions there start a session with them on: `claude-all` (any folder) and `masters` (`~/projects/masters`, whose deadlines sync to Linear). Renee's `scripts/brief.sh` and the personal lane of `scripts/station.py` set the variable to `true` for their own `claude -p` runs. `disableClaudeAiConnectors` is not used: a `true` in any settings source wins everywhere, and it would cut Renee off. On a new machine, add the export and the two functions to the shell profile by hand.
- **Plugin connector servers are denied.** The `data`, `design` and `engineering` plugins declare 27 remote connector servers (Slack, Notion, GitHub, Snowflake and the rest) that would each try to connect at session start. `deniedMcpServers` in `settings.json` names every one as `plugin:<plugin>:<server>`; delete a line to use that connector.
- **Unused plugin skills are blocked, not hidden.** `skillOverrides` hides only personal skills (tested on 2.1.325: a plugin skill stays listed under either its full or its bare name), so the nine plugin skills nobody here uses are denied with `Skill(...)` rules instead: cloudflare's `basin`, `k2`, `gateway-workers`, `cloudflare-one-migrations`, `sandbox-stable`, `sandbox-next` and `sandbox-migrate-to-next`; text-to-cad's `sendcutsend` and `pcb` (kept denied on purpose: it saves boards in KiCad's nightly format). They still appear in the skill list but cannot be loaded.

The basics that used to arrive through claude.ai sync are installed from their public marketplaces instead: `data`, `design`, `engineering` and `pdf-viewer` (`anthropics/knowledge-work-plugins`), `document-skills` for docx, pdf, pptx and xlsx (`anthropics/skills`), and `skill-creator` (`claude-plugins-official`). `permissions.ask` holds Cloudflare's `execute`, which acts on the live account. `deep-research` has no public source: `core/skills/deep-research/` is a local copy of the claude.ai skill as it was downloaded in October 2026, gitignored because it is Anthropic's to publish, so a fresh clone does not have it. The `docs` skill is not restored: it only points at the Claude Docs connector, which a `claude-all` session has.

## Skills

`core/skills/` and `core/optional-skills/` are the only places skills are edited. The installed skill folders hold symlinks to them, so an edit is live the moment it's made. After adding or renaming a skill, `./install.sh skills` relinks just the skills (no settings copy) and names any global skill still missing from `~/.claude/skills/`.

**Optional skills** are the ones only one or two projects use, so they stay out of every other session's skill listing. `core/optional-skills/projects.txt` names each one and its project directories, one line per skill (`isaac ~/projects/aquila ~/projects/berkley`). `./install.sh skills` (or any `claude` install) links each into `<project>/.claude/skills/<name>`, skips a project that is not on the machine, and adds the link to that project's `.git/info/exclude`, since the link holds this machine's path and is not for committing. Claude Code loads a project skill only in sessions under that project. To move a skill between global and optional, move its folder, edit `projects.txt`, and re-run `./install.sh skills`; references to `~/.claude/skills/<name>/` in other repos then need the project path (`check-skills.sh` names them).

These skills are for Claude Code only. `settings.json` sets `syncClaudeAiSkills: false` and `syncClaudeAiPlugins: false`, so no skill or plugin from the claude.ai account loads into Claude Code, and nothing here is uploaded there: the Claude app (Chat and Cowork) keeps its own set. Old downloads from before the switch may still sit in `~/.claude/skills/.trash/` and `~/.claude/plugins/.trash/`; Claude Code does not load them.

```bash
scripts/check-skills.sh                # lint every skill; exit 1 on any FAIL
scripts/bench.sh                       # does the installed setup behave as claimed; --live adds claude -p runs
```

`core/skills/anatomy` is the exception: a submodule pinned to an upstream commit (40 MB, needs Node 20.10+ and Chrome), so it is Claude Code only. Don't edit it in place; update it with `git -C core/skills/anatomy fetch && git -C core/skills/anatomy checkout <commit>`, then commit the new pin.

- `check-skills.sh` needs only bash and python3. It lints `core/skills/` and `core/optional-skills/` alike: it fails a skill whose frontmatter breaks the Agent Skills spec (a key outside `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`; `name` not the directory name; `description` over 1024 characters; `compatibility` over 500; a non-string `metadata` value), a script that does not parse or whose `--help` breaks, a bundled path `SKILL.md` names that does not exist, or a missing version-pin file. It warns about `__pycache__` and `.DS_Store`. Last it checks the skill paths in the Markdown under `~/projects` (this repo's dated `reports/` and `research_notes/` excepted), because other repos call the bundled scripts by those paths: `~/.claude/skills/<name>/<path>` must resolve in `core/skills/`, a global path to an optional skill fails with where the skill lives now, and `.claude/skills/<name>/<path>` to an optional skill must resolve and sit in a project `projects.txt` names for it. The header of the script lists every rule.
- `install.sh` runs `check-skills.sh` after any install that links skills. It only reports.
- `bench.sh` checks that the install matches this README: every symlink points into the repo (the optional skills into their projects, never globally), the live settings carry the hooks, the output style, the deny list, the cache TTL and the subagent env and none of the removed plugins, every hook command exists, the status line is local-only and prints one line, the agent frontmatter pins the documented models and effort and no agent may call the advisor, CLAUDE.md and the output style still carry the rules the setup depends on, and the guard hooks decide correctly on synthetic input. `--live` adds nine headless `claude -p` sessions (API cost, a few minutes) in a throwaway repo whose CLAUDE.md holds a sentinel word: the main session and a general-purpose subagent must know it, the main session must know a CLAUDE.md rule and an output-style rule, an Explore subagent must not start, the guard hook must deny `pytest` in the main session and allow it in a subagent, `git clean -fd` must stay blocked under `bypassPermissions`, and `modelUsage` must show sonnet for general-purpose and fast-executor and opus for deep-reasoner. `--keep` leaves the transcripts and the hook-input log for inspection. Run it after an install or a settings change.

### What the skills read from a project

The skills hold workflow and boundaries; project facts live in the project, in `CLAUDE.md` (or `CLAUDE.local.md`) sections with one greppable `key: value` per line. A skill that finds its section missing works the facts out, then offers to write the section.

| Section | Read by | Keys |
|---|---|---|
| `## Boards` | esp-idf | `<board name>: <serial port>` |
| `## Motors` (optional) | motor-bench | what moves and its power, the interface and sending tool, how to recognise the program, the stop command and its confirmation, limits, user-only commands, the physical kill; without the section motor-bench asks and offers a draft |
| `## Hardware` | pcb-design | `kicad:` (the `.kicad_pro`), `pins:` (firmware pin header), `mcu:` (its reference designator), `fab:`, `note:` (the design note) |
| `## Experiments` | rl-advisor | `log:`, `run-id:`, `runs:`, `metric:`, `eval:`, `framework:` |

Keep `## Boards` short and first: esp-idf reads a fixed 12 lines after its heading. A flash or reset of a board wired to ESCs or drivers follows motor-bench as well as esp-idf. led-animation reads the free-form `CLAUDE.md` section on the renderer and the host tooling's README instead; isaac reads the project's `CLAUDE.md` first, which wins over its own version table. rl-advisor keeps a run's record where the project keeps it: a ledger for the moving state and a digest for the durable facts, found through `## Experiments` or a grep, else an entry in the template of `references/isaac-lab-log.md`.

## VS Code settings and extensions

`adapters/vscode/settings.json` holds the VS Code user settings this repo cares about (today: `workbench.secondarySideBar.defaultVisibility: hidden`, so the Chat / Claude Code side bar starts closed). `./install.sh vscode` merges it into `~/Library/Application Support/Code/User/settings.json` (`~/.config/Code/User/` on Linux) the way the Claude settings are merged: the repo wins on the keys it declares, every other live key stays, the old file goes to the backup folder, and on a fresh machine the file is simply copied. Keep the repo file plain JSON, with no comments: the merge runs through `jq`. A live file that `jq` can't parse (VS Code accepts comments and trailing commas), a symlinked one, or a live file on a machine without `jq` is left alone with a warning, never replaced. This step doesn't need the `code` CLI. Toolbar buttons hidden with a right-click are kept in VS Code's internal state database rather than `settings.json`, so they don't carry over.

`adapters/vscode/extensions.txt` lists extension IDs, one per line, `#` comments allowed. `./install.sh vscode` — or a bare `./install.sh` when VS Code is detected — installs whichever are missing in a single `code --install-extension` call, always at the latest marketplace version; nothing is pinned. Extensions already on the machine are never removed, including ones the list doesn't mention. Those are reported instead, so you can add them:

```
installed here but not in extensions.txt: publisher.name
```

To capture what you've installed since, append the new IDs from `code --list-extensions` to the file. The installer needs the `code` CLI: it looks on `PATH` first, then inside the macOS app bundle. If neither is found it warns and skips — run **Shell Command: Install 'code' command in PATH** from the Command Palette and re-run.

## Backups and safety

Anything pre-existing is backed up to `~/.agent-config-backups/<timestamp>/<tool>/`, never deleted.

**Swept** — `~/.claude/agents/` and `~/.claude/skills/` are owned by this repo. Anything not from here is backed up and removed, so after install they mirror the repo exactly. The exceptions are `~/.claude/skills/synced/` (skills Claude Code downloads from claude.ai) and `~/.claude/skills/.trash/`, which belong to Claude Code and are left alone. In a project only the optional skill's own path, `<project>/.claude/skills/<name>`, is touched: a real folder there goes to `projects/<project>/` in the backup, and the project's own skills stay.

Each `link` line says `new`, `exists` (already that link) or `replace`, so `--dry-run` shows what a run would change.

## Cleaning developer caches

`scripts/cleanup.sh` is opt-in and not run by `install.sh`. With no flags it only reports cache sizes. `--purge` clears the safe caches (brew, npm, uv, Xcode DerivedData, unavailable simulators). `--purge-heavy` also offers Docker images and model weights, each behind a y/N prompt unless `--yes` is given. Add `--dry-run` to print what would run.

## Agents & orchestration

The instructions come in two parts. `adapters/claude/CLAUDE.md` holds only the rules every agent follows (Git, Python, Web, Hardware, Pictures, Cloudflare, Advisor, Settings). The main session's rules (what it keeps, what goes to which agent, when to ask the advisor) are the `orchestrator` output style, `adapters/claude/output-styles/orchestrator.md`. An output style reaches the main conversation and forks but not subagents, so each subagent now reads about 3,700 characters of instructions instead of the 21,877 that CLAUDE.md held before 2026-11-27. `keep-coding-instructions: true` keeps Claude Code's own coding instructions in the system prompt next to the style.

The style makes the main session an orchestrator: it plans, decides and makes the edits whose shape is still open; checks (tests, builds, batches, benchmarks, smoke tests) go to verifier, which overrides the Agent tool's own advice to run a check inline; design rounds that must look at their output (CAD, LED sheets, figures) stay in a session that can load the skill; and on a Fable main session plans and design decisions stay there while deep-reasoner gathers the evidence. Opus 5.5 runs at `xhigh` and Fable 5.2 at `high` (`modelSettings`). A subagent on Opus or Fable that has no `effort` of its own takes the saved level, which is why the agents pin theirs. Each specialist has a pinned model so nothing inherits the session model (`CLAUDE_CODE_SUBAGENT_MODEL=sonnet` covers `general-purpose`; the built-in `Plan` ignores that variable and inherits the session model):

- **deep-reasoner** (Opus at xhigh, read-only) — any investigation that spans several files or runs, and complex debugging. On an Opus or Sonnet main session it also makes the hard design decisions, plans for large or risky changes and algorithm choices; on a Fable main session those stay with the orchestrator and deep-reasoner gathers the evidence.
- **fast-executor** (Sonnet at medium) — boilerplate, patterned edits across separate files, fixes whose shape is already decided, tests; it runs the targeted test for what it touched.
- **implementer** (Opus at high) — a specified part that still needs judgment: a module, a feature slice or a diagnosed fix with its own files, a spec and a check. It makes the local design choices, writes and runs the targeted tests and reports what it decided. It replaces `general-purpose` with a model override for this work, which ran at whatever effort was saved for that model.
- **verifier** (Sonnet at medium, read-only) — runs every test suite, build, batch and smoke test on the orchestrator's behalf and returns pass/fail with the decisive lines; at milestones, after long unattended work or on high-stakes changes it also checks the integrated result against the acceptance criteria.

The built-in **Explore** agent is switched off with `Agent(Explore)` in `permissions.deny` (2026-11-27: about nine calls in 1,837 sessions across all repos, the last on 2026-11-09). Deleting an agent file can't remove a built-in agent, only the deny rule can; searches run in the main session or in `deep-reasoner`.

`isolation: "worktree"` on an Agent call branches from the pushed default branch, not from the working tree, so it only suits work that starts from there.

The rule is enforced, not only stated: `adapters/claude/hooks/guard-main-session.sh` is a `PreToolUse` hook on `Bash` (wired in `settings.json` with `onFailure: block`) that denies test and build commands in the main session (`pytest`, `npm test`, `cargo test`/`build`, `go test`, `ctest`, `ninja`, `make test`/`check`/`all`, `cmake --build`, and `idf.py` build-type actions such as `build`, `app`, `bootloader` and `size` whatever options come first, so `idf.py -C "<dir>" build` is caught) and names the verifier in the denial. The runner is matched as a word anywhere in the command, so a path prefix (`.venv/bin/pytest`), a separator right after it (`pytest; echo done`, `idf.py build|tail`), arguments (`npm test -- --watch`) and a subshell (`x=$(pytest)`) are all caught; segments whose command only names or reads things (`grep pytest`, `which pytest`, `uv add --dev pytest`, `git log --grep pytest`) are dropped before matching, so they pass. Flash, monitor and menuconfig stay allowed. The hook ignores heredoc bodies and quoted strings when matching, so a commit message or note that mentions `pytest` passes; a test command hidden inside quotes (e.g. `bash -c "pytest"`) is not caught, which is acceptable since the guard backs up an instruction rather than resisting an adversary. Calls from subagents carry `agent_id` in the hook input and pass through. `GUARD_MAIN_SESSION_OFF=1` in settings `env` disables it. Without jq the hook fails closed: it exits 1, so `onFailure: block` stops the call. `settings.json` also carries a `permissions.deny` list (`git commit` and `git push`, also with `-C <dir>` when arguments follow; `gh pr create`; `git merge`, `rebase`, `cherry-pick`, `revert` and `tag` in their plain form, which also blocks listing tags, so read them with `git for-each-ref refs/tags`; the sweeping `git add` forms `-A`, `--all`, `-u`, `--update` and `.`; force pushes in any flag order, `git reset --hard`, `git clean -f` and `rm -rf` of `~` or `/`) that applies in every permission mode and to subagents. These rules cover the forms Claude usually writes, not every spelling: `git -c k=v commit`, a bare `git -C <dir> push` and the other verbs behind `-C` are not matched and rest on the second hook and the Git rule in CLAUDE.md. `settings.json` also sets `subagentPromptCacheTtl: "1h"` so long fan-outs keep their prompt cache, and `maxTurns` on fast-executor (60), implementer (100) and verifier (80) so a runaway run returns partial, resumable output.

`adapters/claude/hooks/guard-git-write.sh` (`PreToolUse` on `Bash`, `onFailure: block`, every agent) backs the never-commit rule. The `permissions.deny` patterns match the command text, so `git -C dir commit` or `git -c k=v push` slip past them; the hook finds the real subcommand behind git's global options, env prefixes, wrappers, chains, `$(...)` and `bash -c`, and denies `commit`, `push`, `merge`, `rebase`, `cherry-pick`, `revert`, `tag`, the sweeping `git add` forms and `gh pr create`. It does not see git aliases, `eval`, or history writers the rule doesn't name (`pull`, `am`, `update-ref`).

These are the only two hooks. No hook guards KiCad or Zener board files: the earlier PCB tooling (the `kicad-review`, `pcb-author` and `pcb-enclosure` skills, the KiCad guard hook and the `kicad-happy` plugin) was removed on 2026-11-27 and rebuilt the same day as one optional skill, `pcb-design`, linked into aquila. Its protection is at the output instead of the edit: `fab_export.sh` refuses to produce an order set while ERC, DRC with schematic parity or the firmware pin diff is failing, stale or not run.
Delegation is mandatory for validation because batch output is noise in the main thread: a session that runs its own batches buries the task under it and loses the thread, and that costs more than the extra tokens the agents spend. The specialists have no `Skill` tool, so a skill that covers delegated work hands them its rules instead: esp-idf through its "When delegating" block, isaac through `delegate.md`. Hardware actions (flashing, resets, motors) stay with the main session.

`settings.json` also turns on Claude Code's advisor tool with `advisorModel: fable`. The advisor reads only the transcript and re-reads all of it uncached on each call, so the output style keeps the main session's use to three moments: before committing to the plan for a large or risky change, when the same error returns after two attempts, and before handing over a written deliverable; a code milestone gets a verifier run instead. No subagent calls it: CLAUDE.md says so to every agent, each agent file carries the line, and `bench.sh` fails if one stops doing so. A Fable 5.2 main session accepts only Fable 5.2 as its advisor (Claude Code 2.1.321 or later), which is why the setting is `fable`: with `opus` a Fable session starts with no advisor and says so at launch. `/advisor` writes to the home settings copy, which the next `install.sh` run overwrites.

Agents are linked from `core/agents/*.md` as-is; `model:` and `effort:` in their frontmatter apply directly.
