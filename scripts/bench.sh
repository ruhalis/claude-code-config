#!/usr/bin/env bash
# Bench test for the installed Claude Code setup: does it behave the way
# adapters/claude/CLAUDE.md, the orchestrator output style and README.md claim?
#
#   scripts/bench.sh            static checks only (no API calls, a few seconds)
#   scripts/bench.sh --live     also run headless `claude -p` sessions (API cost,
#                               several minutes; needs `claude` logged in)
#   scripts/bench.sh --live --only L2,L5   run a subset of the live cases
#   scripts/bench.sh --keep     keep the live scratch dir for inspection
#   BENCH_GUARD=<file> BENCH_GITGUARD=<file> scripts/bench.sh
#                               run the synthetic hook cases against candidate
#                               copies of the two guard hooks. The live hooks are
#                               symlinks into this repo, so an edit in place is
#                               live at once and a broken one blocks every call:
#                               test a copy this way first, then copy it over.
#
# Static: symlinks point into this repo (optional skills into the projects
# projects.txt names, and nowhere else), live settings carry the hooks, the output style, the deny
# list, the cache TTL and the subagent env and none of the removed plugins; every
# hook command exists; the status line is local-only; agent frontmatter pins the
# models and effort the docs say are valid and no agent may call the advisor; the
# guard hooks decide correctly on synthetic input; skills pass check-skills.sh;
# CLAUDE.md and the output style still carry the rules the setup depends on.
#
# Live (L*), each a fresh `claude -p` run in a throwaway git repo whose project
# CLAUDE.md holds a random sentinel word:
#   L1  user CLAUDE.md reaches the main session (it names the settings key never to set)
#   L2  project CLAUDE.md reaches the main session (it knows the sentinel)
#   L3  a general-purpose subagent also gets CLAUDE.md (knows the sentinel)
#   L4  the built-in Explore is denied: asked to use it, no Explore subagent starts
#   L5  the guard hook denies `pytest` in the main session (marker file absent)
#   L6  the same command passes inside a subagent (marker file present)
#   L7  permissions.deny holds under bypassPermissions (`git clean -fd` blocked)
#   L8  model routing, from modelUsage of a haiku main session:
#       general-purpose + fast-executor -> a sonnet model, deep-reasoner -> opus
#   L9  the orchestrator output style reaches the main session (it names the
#       connector launcher and the agent that runs tests)
# A logging hook (PreToolUse + SubagentStart) records every call with agent_id
# and agent_type into hook-input.log so each verdict has evidence.
#
# Exit 1 if any check failed.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
LIVE=0; KEEP=0; ONLY=""
while [ $# -gt 0 ]; do
    case "$1" in
        --live) LIVE=1 ;;
        --keep) KEEP=1 ;;
        --only) ONLY="$2"; shift ;;
        -h|--help) sed -n '2,42p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

PASS=0; FAIL=0; SKIP=0
ok()   { PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; [ -z "${2:-}" ] || printf '        %s\n' "$2"; }
skip() { SKIP=$((SKIP+1)); printf '  SKIP  %s\n' "$1"; [ -z "${2:-}" ] || printf '        %s\n' "$2"; }
# check <label> <command...>: PASS when the command exits 0
check() { local label="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$label"; else bad "$label" "failed: $*"; fi; }

linked_to() {  # linked_to <link> <target>
    [ -L "$1" ] && [ "$(readlink "$1")" = "$2" ]
}
fm() {  # fm <agent.md> <key> -> frontmatter value
    awk -v k="$2" 'NR==1&&$0=="---"{f=1;next} f&&$0=="---"{exit} f&&index($0,k": ")==1{sub(k": ","");print;exit}' "$1"
}

echo "== Static checks (repo $REPO_DIR, config $CLAUDE_DIR)"

echo "-- tools"
check "jq installed (the guard hook needs it)" command -v jq
check "claude CLI installed" command -v claude

echo "-- symlinks from install.sh"
check "~/.claude/CLAUDE.md -> adapters/claude/CLAUDE.md" linked_to "$CLAUDE_DIR/CLAUDE.md" "$REPO_DIR/adapters/claude/CLAUDE.md"
for a in deep-reasoner fast-executor implementer verifier; do
    check "~/.claude/agents/$a.md -> core/agents" linked_to "$CLAUDE_DIR/agents/$a.md" "$REPO_DIR/core/agents/$a.md"
done
for d in "$REPO_DIR"/core/skills/*/; do
    n=$(basename "$d")
    check "~/.claude/skills/$n -> core/skills" linked_to "$CLAUDE_DIR/skills/$n" "${d%/}"
done
# optional skills: linked into the projects projects.txt names, never globally
MAP="$REPO_DIR/core/optional-skills/projects.txt"
check "core/optional-skills/projects.txt exists" test -f "$MAP"
mapped=" "
while read -r name dirs; do
    case "$name" in ''|'#'*) continue ;; esac
    mapped+="$name "
    check "projects.txt: $name is in core/optional-skills" test -d "$REPO_DIR/core/optional-skills/$name"
    for p in $dirs; do
        p="${p/#\~/$HOME}"
        if [ ! -d "$p" ]; then skip "$name -> $p" "project not on this machine"; continue; fi
        check "$p/.claude/skills/$name -> core/optional-skills" linked_to "$p/.claude/skills/$name" "$REPO_DIR/core/optional-skills/$name"
        excl=$(git -C "$p" rev-parse --git-path info/exclude 2>/dev/null) || continue
        case "$excl" in /*) ;; *) excl="$p/$excl" ;; esac
        check "$p: .claude/skills/$name is in .git/info/exclude" grep -Fxq ".claude/skills/$name" "$excl"
    done
done < <([ -f "$MAP" ] && cat "$MAP")
for d in "$REPO_DIR"/core/optional-skills/*/; do
    [ -d "$d" ] || continue
    n=$(basename "$d")
    check "optional skill $n is named in projects.txt" bash -c "case '$mapped' in *' $n '*) exit 0;; esac; exit 1"
    check "optional skill $n is not linked globally" bash -c "! [ -e '$CLAUDE_DIR/skills/$n' ] && ! [ -L '$CLAUDE_DIR/skills/$n' ]"
done
# no optional-skill link the map does not name: the scan install.sh's
# prune_optional_skills runs (every mapped project and the directories beside it)
physdir() { (cd "$1" 2>/dev/null && pwd -P); }
unmapped_optional_links() {
    local keep=$'\n' seen=$'\n' cands="" name dirs p d c e n
    while read -r name dirs; do
        case "$name" in ''|'#'*) continue ;; esac
        for p in $dirs; do
            p="${p/#\~/$HOME}"
            if [ -d "$p" ]; then keep+="$name"$'\t'"$(physdir "$p")"$'\n'; fi
            for d in "$p" "$(dirname "$p")"/*/; do
                [ -d "$d" ] || continue
                c=$(physdir "$d") || continue
                case "$seen" in *$'\n'"$c"$'\n'*) continue ;; esac
                seen+="$c"$'\n'; cands+="$c"$'\n'
            done
        done
    done < <([ -f "$MAP" ] && cat "$MAP")
    while IFS= read -r c; do
        [ -n "$c" ] || continue
        for e in "$c"/.claude/skills/* "$c"/.claude/skills/.[!.]*; do
            [ -L "$e" ] || continue
            case "$(readlink "$e")" in "$REPO_DIR"/core/optional-skills/*) ;; *) continue ;; esac
            n="${e##*/}"
            case "$keep" in *$'\n'"$n"$'\t'"$c"$'\n'*) continue ;; esac
            printf '%s ' "$e"
        done
    done <<< "$cands"
}
stale=$(unmapped_optional_links)
if [ -z "$stale" ]; then ok "no optional-skill link that projects.txt does not name"
else bad "no optional-skill link that projects.txt does not name (install.sh removes them)" "unmapped: ${stale% }"; fi
check "~/.claude/hooks/guard-main-session.sh -> adapters/claude/hooks" linked_to "$CLAUDE_DIR/hooks/guard-main-session.sh" "$REPO_DIR/adapters/claude/hooks/guard-main-session.sh"
check "guard hook is executable" test -x "$REPO_DIR/adapters/claude/hooks/guard-main-session.sh"
check "guard hook passes bash -n" bash -n "$REPO_DIR/adapters/claude/hooks/guard-main-session.sh"
check "~/.claude/hooks/guard-git-write.sh -> adapters/claude/hooks" linked_to "$CLAUDE_DIR/hooks/guard-git-write.sh" "$REPO_DIR/adapters/claude/hooks/guard-git-write.sh"
check "git-write guard hook is executable" test -x "$REPO_DIR/adapters/claude/hooks/guard-git-write.sh"
# Retired 2026-11-27. Sessions started before the settings merge still call this
# path with onFailure: block, so it may stay as a no-op file until they restart.
OLDK="$CLAUDE_DIR/hooks/guard-kicad-edit.sh"
if [ -e "$OLDK" ] || [ -L "$OLDK" ]; then
    check "retired guard-kicad-edit.sh is a no-op (exit 0, no output; delete once every session restarted)" \
        bash -c 'o=$(printf "{}" | "$1"); [ $? -eq 0 ] && [ -z "$o" ]' _ "$OLDK"
else
    ok "retired guard-kicad-edit.sh is gone"
fi
check "~/.claude/output-styles/orchestrator.md -> adapters/claude/output-styles" linked_to "$CLAUDE_DIR/output-styles/orchestrator.md" "$REPO_DIR/adapters/claude/output-styles/orchestrator.md"

echo "-- status line"
SL="$REPO_DIR/adapters/claude/statusline.sh"
check "~/.claude/statusline.sh -> adapters/claude/statusline.sh" linked_to "$CLAUDE_DIR/statusline.sh" "$SL"
check "status line is executable" test -x "$SL"
check "status line passes bash -n" bash -n "$SL"
one_line() { local o; o=$(printf '%s' "$1" | "$SL"); [ -n "$o" ] && [ "$(printf '%s\n' "$o" | wc -l | tr -d ' ')" = 1 ]; }
now=$(date +%s)
SL_JSON=$(jq -nc --arg cwd "$REPO_DIR" --argjson t "$now" '{model:{display_name:"Opus"},effort:{level:"high"},cwd:$cwd,context_window:{used_percentage:42.7},rate_limits:{five_hour:{used_percentage:12,resets_at:($t+3600)},seven_day:{used_percentage:30.2,resets_at:($t+86400)}}}')
check "status line prints one line for a full sample" one_line "$SL_JSON"
check "status line prints one line for {}" one_line '{}'
check "status line makes no network call and reads no credential (no curl, security, oauth)" bash -c "! grep -qiE 'curl|security |oauth' '$SL'"

echo "-- settings"
LIVE_S="$CLAUDE_DIR/settings.json"; REPO_S="$REPO_DIR/adapters/claude/settings.json"
check "repo settings.json is valid JSON" jq -e . "$REPO_S"
check "live settings.json is valid JSON" jq -e . "$LIVE_S"
for f in "$REPO_S" "$LIVE_S"; do
    tag=$([ "$f" = "$REPO_S" ] && echo repo || echo live)
    check "$tag: PreToolUse hook on Bash runs guard-main-session.sh with onFailure block" \
        jq -e '.hooks.PreToolUse[]? | select(.matcher=="Bash") | .hooks[] | select(.command|test("guard-main-session.sh")) | select(.onFailure=="block")' "$f"
    check "$tag: PreToolUse hook on Bash runs guard-git-write.sh with onFailure block" \
        jq -e '.hooks.PreToolUse[]? | select(.matcher=="Bash") | .hooks[] | select(.command|test("guard-git-write.sh")) | select(.onFailure=="block")' "$f"
    check "$tag: no hook runs the removed guard-kicad-edit.sh" jq -e '[.. | .command? // empty | strings | select(test("guard-kicad-edit"))] | length == 0' "$f"
    check "$tag: permissions.deny covers commit, push, force push, reset --hard, clean -fd, rm -rf /" \
        jq -e '.permissions.deny as $d | ["Bash(git commit *)","Bash(git push *)","Bash(git push --force *)","Bash(git reset --hard *)","Bash(git clean -fd *)","Bash(rm -rf /)"] | all(. as $r | $d | index($r) != null)' "$f"
    check "$tag: permissions.deny covers merge, rebase, cherry-pick, revert, tag and the sweeping git add forms" \
        jq -e '.permissions.deny as $d | ["Bash(git merge *)","Bash(git rebase *)","Bash(git cherry-pick *)","Bash(git revert *)","Bash(git tag *)","Bash(git add -A *)","Bash(git add --all *)","Bash(git add -u *)","Bash(git add --update *)","Bash(git add .)","Bash(git add . *)"] | all(. as $r | $d | index($r) != null)' "$f"
    check "$tag: permissions.deny keeps text-to-cad's pcb skill out" jq -e '.permissions.deny | index("Skill(text-to-cad:pcb)") != null' "$f"
    check "$tag: permissions.deny removes the built-in Explore agent" jq -e '.permissions.deny | index("Agent(Explore)") != null' "$f"
    check "$tag: no kicad-happy, desktop-commander or rea plugin or marketplace" \
        jq -e '([(.enabledPlugins // {}) | keys[] | split("@")[0]] + ((.extraKnownMarketplaces // {}) | keys)) | any(IN("kicad-happy","desktop-commander","rea")) | not' "$f"
    check "$tag: no permission rule for the removed plugins" \
        jq -e '[(.permissions // {}) | .allow?, .ask?, .deny? | .[]? | select(test("desktop-commander|plugin_rea_|kicad-happy"))] | length == 0' "$f"
    check "$tag: outputStyle is orchestrator" jq -e '.outputStyle=="orchestrator"' "$f"
    check "$tag: statusLine runs ~/.claude/statusline.sh" jq -e '.statusLine.command=="~/.claude/statusline.sh"' "$f"
    check "$tag: subagentPromptCacheTtl is 1h" jq -e '.subagentPromptCacheTtl=="1h"' "$f"
    check "$tag: env.CLAUDE_CODE_SUBAGENT_MODEL is sonnet" jq -e '.env.CLAUDE_CODE_SUBAGENT_MODEL=="sonnet"' "$f"
    check "$tag: CLAUDE_CODE_SUBAGENT_MODEL_FORCE is not set (it would override the pins)" \
        jq -e '(.env.CLAUDE_CODE_SUBAGENT_MODEL_FORCE // "") != "1"' "$f"
    check "$tag: advisorModel set" jq -e '.advisorModel != null' "$f"
done
# every hook command that is a path must exist: a missing script under onFailure: block stops every call
hook_paths_exist() {
    local c miss=""
    while IFS= read -r c; do
        c="${c%% *}"; c="${c/#\~/$HOME}"; c="${c/#\$HOME/$HOME}"
        case "$c" in */*) [ -e "$c" ] || miss+=" $c" ;; esac
    done < <(jq -r '.hooks // {} | .[][]?.hooks[]?.command // empty' "$1")
    [ -z "$miss" ] || { echo "missing:$miss" >&2; return 1; }
}
check "live: every hook command path exists" hook_paths_exist "$LIVE_S"
check "repo: every hook command path exists" hook_paths_exist "$REPO_S"
if jq -e 'has("model") or has("autoMode")' "$LIVE_S" >/dev/null; then
    live_only=$(jq -r --slurpfile r "$REPO_S" 'keys - ($r[0]|keys) | join(" ")' "$LIVE_S")
    printf '  NOTE  live-only settings keys (re-merge after any install.sh run): %s\n' "${live_only:-none}"
fi

echo "-- agent frontmatter"
# bash 3.2 on macOS has no associative arrays
wm() { case $1 in deep-reasoner|implementer) echo opus;; *) echo sonnet;; esac; }
we() { case $1 in deep-reasoner) echo xhigh;; implementer) echo high;; *) echo medium;; esac; }
for a in deep-reasoner fast-executor implementer verifier; do
    f="$REPO_DIR/core/agents/$a.md"
    check "$a: model is $(wm "$a")" test "$(fm "$f" model)" = "$(wm "$a")"
    check "$a: effort is $(we "$a")" test "$(fm "$f" effort)" = "$(we "$a")"
    check "$a: name matches filename" test "$(fm "$f" name)" = "$a"
done
posint() { [[ "$1" =~ ^[1-9][0-9]*$ ]]; }
for a in fast-executor implementer verifier; do
    check "$a: maxTurns is a positive integer" posint "$(fm "$REPO_DIR/core/agents/$a.md" maxTurns)"
done
check "deep-reasoner has no Edit/Write (read-only)" bash -c "! grep -qE '^tools:.*\b(Edit|Write)\b' '$REPO_DIR/core/agents/deep-reasoner.md'"
check "verifier has no Edit/Write (read-only)" bash -c "! grep -qE '^tools:.*\b(Edit|Write)\b' '$REPO_DIR/core/agents/verifier.md'"
check "no Explore override in core/agents or ~/.claude/agents (Explore is denied in settings)" bash -c "[ ! -e '$REPO_DIR/core/agents/Explore.md' ] && [ ! -L '$CLAUDE_DIR/agents/Explore.md' ] && [ ! -e '$CLAUDE_DIR/agents/Explore.md' ]"
for f in "$REPO_DIR"/core/agents/*.md; do
    a=$(basename "$f" .md)
    check "$a: says never call the advisor tool" grep -qi "never call the advisor tool" "$f"
    check "$a: nothing permits the advisor" bash -c "! grep -qiE '(may|can|should) (consult|call|use) the advisor|advisor[^.]*(allowed|permitted)' '$f'"
done

echo "-- guard hook on synthetic input"
GUARD="${BENCH_GUARD:-$REPO_DIR/adapters/claude/hooks/guard-main-session.sh}"
[ -z "${BENCH_GUARD:-}" ] || printf '  NOTE  testing a candidate main-session guard: %s\n' "$GUARD"
main_json() { jq -n --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}'; }
sub_json()  { jq -n --arg c "$1" '{agent_id:"abc",agent_type:"verifier",tool_name:"Bash",tool_input:{command:$c}}'; }
deny_main() { main_json "$1" | "$GUARD" | jq -e '.hookSpecificOutput.permissionDecision=="deny"' >/dev/null; }
pass_main() { local o; o=$(main_json "$1" | "$GUARD"); [ -z "$o" ]; }
pass_sub()  { local o; o=$(sub_json "$1" | "$GUARD"); [ -z "$o" ]; }
for c in "pytest -q" "uv run python -m pytest" "npm test" "cargo test" "go test ./..." "ctest" "make test" "cmake --build build" "cd x && pytest" \
    "idf.py build" 'idf.py -C "/some dir/x" build' "idf.py -C dir build" "idf.py -p /dev/cu.usbmodem1 build" "idf.py -p X build flash" \
    "idf.py -C d -B build build" '. "$HOME/esp/esp-idf/export.sh" >/dev/null 2>&1 && idf.py -C "/x y" build' \
    "idf.py -C d size" "idf.py size-components" "idf.py -C d app" "ninja" "ninja -C build" "make all" "cargo build"; do
    check "main denies: $c" deny_main "$c"
done
reason_has() { main_json "$2" | "$GUARD" | jq -e --arg w "$1" '.hookSpecificOutput.permissionDecisionReason|test($w)' >/dev/null; }
for c in 'idf.py -C "/x y" -p "/dev/cu.x" flash' "idf.py -p /dev/cu.x flash" "idf.py -C dir -B build -p port flash" "idf.py --build-dir build flash" \
    "idf.py --build-dir=build flash" "idf.py -C d monitor" "idf.py set-target esp32s3" "idf.py -C d erase-flash" "idf.py -C d app-flash" \
    "cat pytest.ini" "ls go tests/x" "cat build/log.txt" "ls build" "git status" "make" "echo npm testing" "echo done"; do
    check "main allows: $c" pass_main "$c"
done
for c in "pytest -q" "idf.py -C dir build" "npm test"; do
    check "subagent allows: $c" pass_sub "$c"
done
# heredoc bodies and quoted strings are ignored when matching
for c in $'git commit -q -F - <<\'EOF\'\nbuild ok, the shim builds, pytest 382 passed / 6 CUDA skips\nEOF' \
    $'cat > note.md <<EOF\ntests run as cd x && python -m pytest -q\nEOF\necho ok' \
    $'cat <<-\'EOF\'\n\tmake test\n\tEOF' \
    'git commit -m "ran pytest and cargo build"' \
    'idf.py -C "/x/build" -p "/dev/cu.usbmodem1" flash'; do
    check "main allows: $c" pass_main "$c"
done
for c in $'cat > a.md <<\'EOF\'\nnotes\nEOF\npytest -q' \
    $'git commit -m "$(cat <<\'EOF\'\nmsg\nEOF\n)" && cargo test' \
    'idf.py -C "/x/build" -p "/dev/cu.usbmodem1" build' 'cd /tmp/x && uv run pytest'; do
    check "main denies: $c" deny_main "$c"
    check "deny reason names verifier: $c" reason_has verifier "$c"
done
c='cat <<<"x" && pytest -q'
check "main denies: $c" deny_main "$c"
check "deny reason names verifier: $c" reason_has verifier "$c"
# a separator, an argument, a path prefix or a subshell next to the runner (allowed until 2026-11-16),
# and the keyword and wrapper shapes the loose match has always caught
for c in 'pytest; echo done' 'pytest|tail -5' 'pytest&&echo ok' 'pytest >out.txt 2>&1' 'idf.py build; echo $?' 'idf.py build|tail' 'make test;' 'cargo test|tail' 'ctest;' \
    'npm test -- --watch' 'npm test foo' 'bun test src/' 'pnpm test --filter x' '.venv/bin/pytest -q' '/usr/local/bin/ninja -C build' '(pytest)' 'x=$(pytest)' 'if true; then pytest; fi' \
    'if pytest -q; then echo ok; fi' '! pytest' '{ pytest; }' 'sudo pytest' 'ssh host pytest' 'poetry run pytest' 'python -m coverage run -m pytest' 'caffeinate -i idf.py build' \
    'env X=1 pytest' 'timeout 600 pytest' 'cat x | xargs pytest' 'echo start && idf.py build' 'for f in a b; do pytest $f; done'; do
    check "main denies: $c" deny_main "$c"
done
# a segment whose command only names or reads things can't start a run
for c in 'uv add --dev pytest' 'pip show pytest' 'which pytest' 'grep -rn pytest .' 'echo run pytest later' 'man ninja' 'brew install ninja' 'command -v ctest' 'ls .venv/bin/pytest' \
    'git log --grep pytest' 'which pytest || uv add --dev pytest' 'make flash' 'idf.py flash' 'npm run build'; do
    check "main allows: $c" pass_main "$c"
done
guard_off() { local o; o=$(main_json pytest | GUARD_MAIN_SESSION_OFF=1 "$GUARD"); [ -z "$o" ]; }
reason_names_verifier() { main_json pytest | "$GUARD" | jq -e '.hookSpecificOutput.permissionDecisionReason|test("verifier")' >/dev/null; }
check "GUARD_MAIN_SESSION_OFF=1 disables the hook" guard_off
guard_off_nojq() { local o; o=$(printf '{}' | env PATH=/nonexistent GUARD_MAIN_SESSION_OFF=1 /bin/bash "$GUARD" 2>&1); [ -z "$o" ]; }
guard_nojq_fails() { local e rc; e=$(printf '{}' | env PATH=/nonexistent /bin/bash "$GUARD" 2>&1 >/dev/null); rc=$?; [ "$rc" -eq 1 ] && printf '%s' "$e" | grep -q "install jq"; }
check "GUARD_MAIN_SESSION_OFF=1 works without jq" guard_off_nojq
check "missing jq fails closed (exit 1 + message)" guard_nojq_fails
check "deny reason names the verifier" reason_names_verifier
check "pytest deny reason names verifier" reason_names_verifier

echo "-- git-write guard hook on synthetic input"
GGUARD="${BENCH_GITGUARD:-$REPO_DIR/adapters/claude/hooks/guard-git-write.sh}"
[ -z "${BENCH_GITGUARD:-}" ] || printf '  NOTE  testing a candidate git-write guard: %s\n' "$GGUARD"
check "git-write guard hook is executable" test -x "$GGUARD"
check "git-write guard hook passes bash -n" bash -n "$GGUARD"
g_deny()     { main_json "$1" | "$GGUARD" | jq -e '.hookSpecificOutput.permissionDecision=="deny"' >/dev/null; }
g_deny_sub() { sub_json "$1" | "$GGUARD" | jq -e '.hookSpecificOutput.permissionDecision=="deny"' >/dev/null; }
g_pass()     { local o rc; o=$(main_json "$1" | "$GGUARD"); rc=$?; [ "$rc" -eq 0 ] && [ -z "$o" ]; }
g_reason()   { main_json "$2" | "$GGUARD" | jq -e --arg w "$1" '.hookSpecificOutput.permissionDecisionReason|test($w)' >/dev/null; }
for c in 'git commit -m x' 'git commit' 'git commit --amend' 'git -C /tmp/r commit' 'git -C /tmp/r commit -m x' \
    'git -c user.name=a -c user.email=b commit -m x' 'git --git-dir=.git --work-tree=. push' 'git --no-pager push origin main' '/usr/bin/git push' \
    'cd repo && git push' 'git add f; git commit -m x' 'true || git merge feature' 'FOO=1 git rebase main' 'env GIT_DIR=.git git cherry-pick abc' \
    'git revert HEAD' 'git tag v1' 'git -C x tag' 'echo done | xargs git push' '(git commit -m x)' 'out=$(git push 2>&1)' \
    'git add -A' 'git add --all' 'git add -u' 'git add .' 'git -C x add .' 'git add -Av' 'gh pr create --fill' 'gh -R o/r pr create' \
    'git --git-dir .git push' 'git -C $(pwd) commit' 'git -C "$dir" commit' 'git -C ${D} commit' 'x="$(git push)"' 'echo `git push`' \
    $'git \\\n  push' $'git commit -m "$(cat <<\'EOF\'\nmsg\nEOF\n)"' $'cat > m.txt <<EOF\nmsg\nEOF\ngit commit -F m.txt' \
    '{ git push; }' 'if git push; then echo ok; fi' '! git push' 'sudo -u me git push' 'command git push' 'nohup git push &' 'time git commit -m x' \
    'exec git push' 'xargs -I{} git -C {} push' 'git add -vu' 'git add --update' 'git add -- .' 'gh pr -R o/r create' 'git commit -m "msg" # note' \
    'git push>log 2>&1' '>log git push' 'git >/dev/null push' '2> err git -C x commit'; do
    check "git guard denies: $c" g_deny "$c"
done
for c in 'git status' 'git -C dir status' 'git diff --cached --stat' 'git log --grep=commit' 'git log --oneline | grep push' 'git show HEAD' \
    'git blame f' 'git merge-base a b' 'git for-each-ref refs/tags' 'git add path/to/file other/file' 'git restore --staged f' 'git stash' \
    'git rev-parse --show-toplevel' 'echo "git commit -m x"' "printf 'run git push\\n'" $'cat > note.md <<\'EOF\'\ngit commit -m x && git push\nEOF' \
    'grep -rn "git push" docs/' 'gh pr view 12' 'gh pr list' 'ls commit' 'cat push.txt' \
    'git add -p f' 'git add -- f' 'git -c core.pager=cat log' 'git config --get user.name' 'echo hi # git push' 'command -v git' \
    'xargs -I{} echo {}' 'gh pr checks 3' 'gh issue create --title x' 'git log --format="%h %s" | head' 'which gh git'; do
    check "git guard allows: $c" g_pass "$c"
done
# wrappers, shell -c re-entry, and quoted text spanning lines
for c in 'timeout 60 git push' 'timeout -s KILL -k 5 60 git commit -m x' 'timeout --foreground 1m git push' 'nice -n 10 git push' 'nice git commit' \
    'caffeinate -i git push' 'caffeinate -t 600 git push' 'stdbuf -oL git push' 'stdbuf -o L -e 0 git commit' \
    "bash -c 'git commit -m x'" 'sh -c "cd r && git push"' "zsh -lc 'git -C r commit'" 'bash -c "git add -A"' "/bin/bash -l -c 'git push'" \
    "sudo bash -c 'git push'" "bash -c 'echo \"a\"; git commit -m \"b\"'" 'bash -c "$(echo x) && git push"' \
    $'git commit -m "subject\n\nbody"' $'gh issue create --body "a\n$(git push)\nb"'; do
    check "git guard denies: $c" g_deny "$c"
done
for c in "bash -c 'git status'" 'sh -c "echo hi"' 'bash script.sh' 'timeout 60 git status' 'nice -n 5 git log' 'caffeinate -t 5 ls' \
    $'gh issue create --body "first line\ngit push origin main\nthird line"' $'echo \'one\ngit commit -m x\ntwo\'' \
    $'git log --format="%h\ngit push"' 'echo "it'"'"'s \"quoted\"; git push"' 'echo x\#y git push' 'echo bash -c' 'grep -c push f'; do
    check "git guard allows: $c" g_pass "$c"
done
for c in 'git commit -m x' 'git -C /tmp/r push' 'git add -A'; do
    check "git guard denies in a subagent too: $c" g_deny_sub "$c"
done
check "git guard reason names the subcommand (git commit)" g_reason "git commit" 'git -C /tmp/r commit -m x'
check "git guard reason names the subcommand (git push)" g_reason "git push" '/usr/bin/git push'
check "git guard reason names the subcommand (git add -A)" g_reason "git add -A" 'git add -A'
check "git guard reason names the subcommand (gh pr create)" g_reason "gh pr create" 'gh -R o/r pr create'
check "git guard reason says to stage with git add <path>" g_reason "git add <path>" 'git push'
check "git guard reason says to name explicit paths for add" g_reason "explicit paths" 'git add .'
check "git guard reason does not mention the verifier" bash -c "! { jq -n '{tool_name:\"Bash\",tool_input:{command:\"git push\"}}' | '$GGUARD' | grep -qi verifier; }"
for c in 'git commit -m "x' 'echo $(' ')))' 'git \' '`' '$((1+2)) git status' $'cat <<EOF\nno end'; do
    check "git guard: odd input gives no crash: $c" bash -c "jq -n --arg c \"\$1\" '{tool_name:\"Bash\",tool_input:{command:\$c}}' | '$GGUARD' >/dev/null" _ "$c"
done
gguard_off() { local o; o=$(main_json 'git push' | GUARD_GIT_WRITE_OFF=1 "$GGUARD"); [ -z "$o" ]; }
gguard_nojq_fails() { local e rc; e=$(printf '{}' | env PATH=/nonexistent /bin/bash "$GGUARD" 2>&1 >/dev/null); rc=$?; [ "$rc" -eq 1 ] && printf '%s' "$e" | grep -q "install jq"; }
check "GUARD_GIT_WRITE_OFF=1 disables the hook" gguard_off
check "git guard: missing jq fails closed (exit 1 + message)" gguard_nojq_fails
check "git guard: empty input is no decision" bash -c "o=\$(printf '{}' | '$GGUARD'); [ -z \"\$o\" ]"
check "git guard: non-JSON input is no decision, exit 0" bash -c "o=\$(printf 'not json' | '$GGUARD'); [ -z \"\$o\" ]"
check "git guard: non-Bash tool is no decision" bash -c "o=\$(jq -n '{tool_name:\"Edit\",tool_input:{command:\"git push\",file_path:\"x\"}}' | '$GGUARD'); [ -z \"\$o\" ]"

echo "-- instructions and skills"
# CLAUDE.md reaches every agent; the orchestrator output style only the main session and forks
CM="$REPO_DIR/adapters/claude/CLAUDE.md"; OS="$REPO_DIR/adapters/claude/output-styles/orchestrator.md"
lines=$(wc -l < "$CM" | tr -d ' '); chars=$(wc -c < "$CM" | tr -d ' ')
check "CLAUDE.md under 200 lines (is $lines)" test "$lines" -lt 200
check "CLAUDE.md under 5000 characters, since every subagent reads it (is $chars)" test "$chars" -lt 5000
check "CLAUDE.md: the no-commit rule" grep -q "don't commit or push" "$CM"
check "CLAUDE.md: the uv rule" grep -q 'Use `uv` for all Python' "$CM"
check "CLAUDE.md: subagents don't call the advisor tool" grep -q "Subagents don't call the advisor tool" "$CM"
check "CLAUDE.md: never set disableClaudeAiConnectors" grep -q "Never set \`disableClaudeAiConnectors\`" "$CM"
check "CLAUDE.md points at the orchestrator output style" grep -q '`orchestrator` output style' "$CM"
check "output style: name is orchestrator" test "$(fm "$OS" name)" = orchestrator
check "output style: keep-coding-instructions is true" test "$(fm "$OS" keep-coding-instructions)" = true
check "output style: checks go to verifier" grep -q 'Checks go to `verifier`' "$OS"
check "output style: the verifier rule overrides the Agent tool's advice" grep -q "overrides the Agent tool's advice to run a check inline" "$OS"
check "output style: the connector launchers (claude-all, masters)" bash -c "grep -q claude-all '$OS' && grep -q masters '$OS'"
check "output style: when to use the advisor" grep -q "The advisor is" "$OS"
for f in "$CM" "$OS"; do
    check "${f##*/}: does not claim Plan follows CLAUDE_CODE_SUBAGENT_MODEL" bash -c "! grep -qiE 'Plan[^.]*fall(s)? back to Sonnet' '$f'"
    check "${f##*/}: names no removed skill or hook (kicad-review, pcb-author, pcb-enclosure, guard-kicad-edit)" bash -c "! grep -qE 'kicad-review|pcb-author|pcb-enclosure|guard-kicad-edit' '$f'"
done
check "check-skills.sh --quiet --no-refs passes" "$REPO_DIR/scripts/check-skills.sh" --quiet --no-refs
check "install.sh passes bash -n" bash -n "$REPO_DIR/install.sh"

# ---------------------------------------------------------------- live
if [ "$LIVE" = 1 ]; then
    echo
    echo "== Live checks (headless claude -p; each case is a fresh session)"
    if ! command -v claude >/dev/null 2>&1; then
        bad "claude CLI missing; live checks not run"
    else
        BENCH_DIR="${BENCH_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/claude-bench.XXXXXX")}"
        SENTINEL="PELICAN$(jq -rn 'now|tostring|.[-5:]')"
        LOG="$BENCH_DIR/hook-input.log"
        PROJ="$BENCH_DIR/proj"; mkdir -p "$PROJ"
        ( cd "$PROJ" && git init -q && printf 'bench\n' > README.md && git add README.md && git -c user.name=bench -c user.email=bench@example.com commit -qm init )
        printf '# Project rules\n\nThe bench sentinel word is %s. When asked for the bench sentinel word, answer with exactly that word.\n' "$SENTINEL" > "$PROJ/CLAUDE.md"
        echo "junk" > "$PROJ/junk.txt"   # untracked; git clean -fd would delete it
        cat > "$BENCH_DIR/logger.sh" <<EOF
#!/usr/bin/env bash
cat >> "$LOG"; echo >> "$LOG"; exit 0
EOF
        chmod +x "$BENCH_DIR/logger.sh"
        SETTINGS="$BENCH_DIR/settings.json"
        jq -n --arg l "$BENCH_DIR/logger.sh" '{hooks:{PreToolUse:[{matcher:"Bash|Read|Agent",hooks:[{type:"command",command:$l,timeout:10}]}],SubagentStart:[{hooks:[{type:"command",command:$l,timeout:10}]}]}}' > "$SETTINGS"
        echo "  scratch: $BENCH_DIR  sentinel: $SENTINEL"

        want() { [ -z "$ONLY" ] || [[ ",$ONLY," == *",$1,"* ]]; }
        # run <case> <model> <extra args...> -- <prompt>  ; writes <case>.json and <case>.txt
        # (claude -p gets "--" before the prompt: --disallowedTools is variadic and would eat it)
        run() {
            local case="$1" model="$2"; shift 2
            local extra=(); while [ "$1" != "--" ]; do extra+=("$1"); shift; done; shift
            printf '\n### %s\n' "$case" >> "$LOG"
            ( cd "$PROJ" && perl -e 'alarm shift; exec @ARGV' 420 \
                claude -p --model "$model" --permission-mode bypassPermissions --no-session-persistence \
                --settings "$SETTINGS" --output-format json ${extra[@]+"${extra[@]}"} -- "$1" ) > "$BENCH_DIR/$case.json" 2> "$BENCH_DIR/$case.err"
            jq -r '.result // empty' "$BENCH_DIR/$case.json" > "$BENCH_DIR/$case.txt" 2>/dev/null || true
        }
        out() { cat "$BENCH_DIR/$1.txt"; }
        models() { jq -r '.modelUsage // {} | keys[]' "$BENCH_DIR/$1.json" 2>/dev/null | tr '\n' ' '; }
        NOTOOLS=(--disallowedTools "Read,Grep,Glob,Bash,Edit,Write,WebFetch,WebSearch")

        if want L1; then
            run L1 sonnet "${NOTOOLS[@]}" -- "Without using any tool: your instructions name one settings key that must never be set in a settings file. Reply with only that key."
            if grep -q "disableClaudeAiConnectors" "$BENCH_DIR/L1.txt"; then ok "L1 user CLAUDE.md loaded in main session"; else bad "L1 user CLAUDE.md loaded in main session" "got: $(out L1)"; fi
        fi
        if want L2; then
            run L2 sonnet "${NOTOOLS[@]}" -- "Without using any tool: reply with only the bench sentinel word from the project instructions. If you have no such word, reply NONE."
            if grep -q "$SENTINEL" "$BENCH_DIR/L2.txt"; then ok "L2 project CLAUDE.md loaded in main session"; else bad "L2 project CLAUDE.md loaded in main session" "got: $(out L2)"; fi
        fi
        if want L3; then
            run L3 sonnet "${NOTOOLS[@]}" -- "Use the Agent tool once with subagent_type \"general-purpose\" and exactly this prompt: 'Without using any tool, reply with only the bench sentinel word from the project instructions you were given. If you have no such word, reply NONE.' Then reply with only the subagent's answer, verbatim."
            if grep -q "$SENTINEL" "$BENCH_DIR/L3.txt"; then ok "L3 general-purpose subagent received project CLAUDE.md"; else bad "L3 general-purpose subagent received project CLAUDE.md" "got: $(out L3)"; fi
        fi
        if want L4; then
            run L4 sonnet "${NOTOOLS[@]}" -- "Use the Agent tool once with subagent_type \"Explore\" and the prompt 'Reply with only the word OK. Use no tools.' If that agent type is not available or the call is refused, do not use another agent type; reply with only: unavailable. Otherwise reply with only: done."
            if grep -q '"agent_type":"Explore"' "$LOG"; then bad "L4 Explore is denied" "an Explore subagent started; got: $(out L4)"; else ok "L4 Explore is denied (answer: $(out L4 | head -c 60))"; fi
        fi
        if want L5; then
            run L5 sonnet -- "Run exactly this with the Bash tool, once: touch main-ran.marker && pytest --version . Then reply with one line saying whether it ran or was blocked, quoting any block message."
            if [ ! -e "$PROJ/main-ran.marker" ] && grep -q "Blocked in the main session" "$BENCH_DIR/L5.txt" "$BENCH_DIR/L5.json"; then ok "L5 guard hook denies pytest in main session"; else bad "L5 guard hook denies pytest in main session" "marker exists: $([ -e "$PROJ/main-ran.marker" ] && echo yes || echo no); got: $(out L5)"; fi
        fi
        if want L6; then
            run L6 sonnet -- "Use the Agent tool once with subagent_type \"general-purpose\" and exactly this prompt: 'Run exactly this with the Bash tool, once: touch sub-ran.marker; pytest --version; true . Reply with one line: ran or blocked, quoting any block message.' Then reply with only the subagent's answer."
            if [ -e "$PROJ/sub-ran.marker" ]; then ok "L6 guard hook lets a subagent run pytest"; else bad "L6 guard hook lets a subagent run pytest" "got: $(out L6)"; fi
        fi
        if want L7; then
            run L7 sonnet -- "Run exactly this with the Bash tool, once: git clean -fd . Then reply with one line saying whether it ran or was blocked, quoting any message."
            if [ -e "$PROJ/junk.txt" ]; then ok "L7 permissions.deny blocks git clean -fd under bypassPermissions"; else bad "L7 permissions.deny blocks git clean -fd under bypassPermissions" "junk.txt was deleted; got: $(out L7)"; fi
        fi
        if want L8; then
            run L8 haiku "${NOTOOLS[@]}" -- "Use the Agent tool three times, in parallel, each with the prompt 'Reply with only the word OK. Use no tools.': once with subagent_type \"general-purpose\", once with \"fast-executor\", once with \"deep-reasoner\". Then reply with only: done."
            m=$(models L8)
            if echo "$m" | grep -q sonnet && echo "$m" | grep -q opus; then ok "L8 routing from haiku main: sonnet (general-purpose/fast-executor) and opus (deep-reasoner) used [$m]"; else bad "L8 routing from haiku main" "modelUsage: ${m:-empty}; got: $(out L8)"; fi
            if grep -q '"agent_type":"deep-reasoner"' "$LOG" && grep -q '"agent_type":"fast-executor"' "$LOG" && grep -q '"agent_type":"general-purpose"' "$LOG"; then ok "L8 SubagentStart logged all three agent types"; else bad "L8 SubagentStart logged all three agent types" "see $LOG"; fi
        fi
        if want L9; then
            run L9 sonnet "${NOTOOLS[@]}" -- "Without using any tool, answer from your instructions in two lines. Line 1: the name of the shell launcher that starts a session in any folder with the claude.ai connectors on. Line 2: the subagent type that runs tests, builds and validation batches."
            if grep -q "claude-all" "$BENCH_DIR/L9.txt" && grep -qi "verifier" "$BENCH_DIR/L9.txt"; then ok "L9 orchestrator output style loaded in main session"; else bad "L9 orchestrator output style loaded in main session" "got: $(out L9)"; fi
        fi
        if [ "$KEEP" = 1 ]; then echo "  kept: $BENCH_DIR"; else rm -rf "$BENCH_DIR"; fi
    fi
fi

echo
printf '%d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" = 0 ]
