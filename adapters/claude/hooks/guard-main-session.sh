#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash). Denies test, build and validation commands
# in the MAIN session only; the orchestration rule in CLAUDE.md sends those to
# the verifier subagent. Subagent calls carry agent_id in the hook input and
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

# One regex per guarded shape; word-bounded so "pytest.ini" or "go tests/" don't match.
pattern='(^|[;&|[:space:]])(pytest|py\.test|(python3?|uv run|uvx)[[:space:]]+(-m[[:space:]]+)?pytest|(npm|pnpm|yarn|bun)[[:space:]]+(run[[:space:]]+)?test([[:space:]]|$)|cargo[[:space:]]+(test|build)|go[[:space:]]+test|ctest|ninja|make[[:space:]]+(test|check|all)|cmake[[:space:]]+--build)([[:space:]]|$)'
# idf.py: drop value-taking options first so "-B build" is not read as the build action.
opts='-C|-B|-G|-p|-b|-D|--project-dir|--build-dir|--port|--baud|--generator|--define-cache-entry'
stripped=$(printf '%s' "$cmd" | sed -E "s/(^|[[:space:]])($opts)([[:space:]]+|=)(\"[^\"]*\"|'[^']*'|[^[:space:];&|]+)/\1/g")
idf='idf\.py([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+(build|app|bootloader|size|size-components|size-files)([[:space:]]|$)'
if printf '%s' "$cmd" | grep -qE "$pattern" || printf '%s' "$stripped" | grep -qE "$idf"; then
  jq -n --arg reason "Blocked in the main session: tests, builds and validation runs go to the verifier subagent (Agent tool, subagent_type \"verifier\"), per CLAUDE.md. Subagents may run this command." \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
fi
exit 0
