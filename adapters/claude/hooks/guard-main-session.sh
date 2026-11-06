#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash). Denies test, build and validation commands
# in the MAIN session only; the orchestration rule in CLAUDE.md sends those to
# the verifier subagent. Also denies the HyperFrames CLI there, which goes to
# the video-maker subagent. Subagent calls carry agent_id in the hook input and
# pass through untouched. Set GUARD_MAIN_SESSION_OFF=1 in settings `env` to
# disable without removing the hook. Exit 0 with no output = no decision.
set -u
[ "${GUARD_MAIN_SESSION_OFF:-0}" = "1" ] && exit 0
# Fail closed without jq: exit 1 is a hook failure, so onFailure "block" stops the call.
command -v jq >/dev/null 2>&1 || { echo "guard-main-session: jq missing; install jq (brew install jq) or set GUARD_MAIN_SESSION_OFF=1" >&2; exit 1; }

input=$(cat)
agent_id=$(printf '%s' "$input" | jq -r '.agent_id // empty')
[ -n "$agent_id" ] && exit 0            # inside a subagent: allowed

cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
[ -n "$cmd" ] || exit 0

# Match against the command with heredoc bodies dropped and quoted strings
# emptied, so prose such as a commit message or a memory note saying
# "pytest 382 passed" doesn't trip the guard (two false denials, Oct 2026).
# Heredoc: lines after <<WORD / <<'WORD' / <<-WORD up to the WORD line are
# skipped (<<< here-strings are not heredocs). Quotes: emptied per line.
scan=$(printf '%s\n' "$cmd" | awk -v q="'" '
  delim != "" { line = $0; if (strip) sub(/^\t+/, "", line); if (line == delim) delim = ""; next }
  {
    print
    probe = $0
    gsub(/<<</, "###", probe)
    re = "<<-?[ \t]*[\"" q "]?[A-Za-z_][A-Za-z0-9_]*[\"" q "]?"
    if (match(probe, re)) {
      d = substr(probe, RSTART, RLENGTH)
      strip = (substr(d, 3, 1) == "-")
      sub("^<<-?[ \t]*[\"" q "]?", "", d)
      sub("[\"" q "]$", "", d)
      delim = d
    }
  }' | sed -E "s/'[^']*'/''/g; s/\"[^\"]*\"/\"\"/g")

# One regex per guarded shape; word-bounded so "pytest.ini" or "go tests/" don't match.
pattern='(^|[;&|[:space:]])(pytest|py\.test|(python3?|uv run|uvx)[[:space:]]+(-m[[:space:]]+)?pytest|(npm|pnpm|yarn|bun)[[:space:]]+(run[[:space:]]+)?test([[:space:]]|$)|cargo[[:space:]]+(test|build)|go[[:space:]]+test|ctest|ninja|make[[:space:]]+(test|check|all)|cmake[[:space:]]+--build)([[:space:]]|$)'
# idf.py: drop value-taking options first so "-B build" is not read as the build action.
opts='-C|-B|-G|-p|-b|-D|--project-dir|--build-dir|--port|--baud|--generator|--define-cache-entry'
stripped=$(printf '%s' "$scan" | sed -E "s/(^|[[:space:]])($opts)([[:space:]]+|=)(\"[^\"]*\"|'[^']*'|[^[:space:];&|]+)/\1/g")
idf='idf\.py([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+(build|app|bootloader|size|size-components|size-files)([[:space:]]|$)'
# HyperFrames CLI in command position (start, or after ; & |), bare or through npx/bunx/pnpx/pnpm dlx/npm exec.
# Command position only, so "grep hyperframes" or a path containing the word passes.
hf='(^|[;&|])[[:space:]]*((npx|bunx|pnpx)([[:space:]]+(-y|--yes))*[[:space:]]+|pnpm[[:space:]]+dlx[[:space:]]+|npm[[:space:]]+exec[[:space:]]+(--[[:space:]]+)?)?hyperframes(@[^[:space:]]*)?([[:space:]]|$)'
if printf '%s' "$scan" | grep -qE "$hf"; then
  jq -n --arg reason "Blocked in the main session: HyperFrames video work (check, snapshot, preview, render) goes to the video-maker subagent (Agent tool, subagent_type \"video-maker\"), per CLAUDE.md. Subagents may run this command." \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
fi
if printf '%s' "$scan" | grep -qE "$pattern" || printf '%s' "$stripped" | grep -qE "$idf"; then
  jq -n --arg reason "Blocked in the main session: tests, builds and validation runs go to the verifier subagent (Agent tool, subagent_type \"verifier\"), per CLAUDE.md. Subagents may run this command." \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
fi
exit 0
