#!/usr/bin/env bash
# PreToolUse hook (matcher: Edit|Write|Bash). KiCad design files and Zener
# board sources are changed by a Claude Fable model only; every other model,
# in the main session or in a subagent, is denied and reviews instead (the
# kicad-review skill). The write path is the pcb-author skill.
#
# Guarded: Edit/Write on *.kicad_sch|pcb|pro|sym|mod|wks|dru and *.zen; Bash
# that redirects, tees or edits in place into one of those; the writing
# subcommands of Diode's `pcb` CLI (layout, import, apply, new, fmt, fix,
# migrate, route, embed-step; a segment with --check only validates and passes);
# `pcb-component-gen`; `kicad-cli <sch|pcb|sym|fp> upgrade`. Best effort on
# Bash: a script that writes the files itself is not seen.
#
# The hook input carries no model, so it is read from the transcript: the last
# assistant message of the session file, or of the subagent's own file
# (<session>/subagents/agent-<agent_id>.jsonl) when agent_id is set. The
# message that issues the call is not on disk yet, so the check sees the
# previous one: a subagent's very first tool call has no model on record and
# is denied (fail closed), and the first call after /model sees the old model.
# Set GUARD_KICAD_OFF=1 in settings `env` to disable without removing the hook.
# Exit 0 with no output = no decision.
set -u
[ "${GUARD_KICAD_OFF:-0}" = "1" ] && exit 0
# Fail closed without jq: exit 1 is a hook failure, so onFailure "block" stops the call.
command -v jq >/dev/null 2>&1 || { echo "guard-kicad-edit: jq missing; install jq (brew install jq) or set GUARD_KICAD_OFF=1" >&2; exit 1; }

input=$(cat)
tool=$(printf '%s' "$input" | jq -r '.tool_name // empty')
ext='\.(kicad_(sch|pcb|pro|sym|mod|wks|dru)|zen)'
what=""

case "$tool" in
  Edit|Write)
    path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
    if printf '%s' "$path" | grep -qE "${ext}\$"; then what="$tool on $(basename "$path")"; fi
    ;;
  Bash)
    cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
    [ -n "$cmd" ] || exit 0
    # A design file as one shell word, up to a quote, space, separator or the end.
    file="[^[:space:];&|<>]*${ext}([\"'[:space:];&|)]|\$)"
    redirect=">[[:space:]]*${file}"
    inplace="(^|[;&|[:space:]])(g?sed|perl)([[:space:]][^;&|]*)?[[:space:]](-[A-Za-z]*i|--in-place)[^;&|]*${ext}"
    tee="(^|[;&|[:space:]])tee[[:space:]][^;&|]*${ext}"
    upgrade='kicad-cli[[:space:]]+(sch|pcb|sym|fp)[[:space:]]+upgrade([[:space:]]|$)'
    # Command position only, one segment per line: optional VAR=value prefixes, optional path, optional +toolchain.
    lead='^[[:space:]$(]*([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*([^[:space:]]*/)?'
    pcbcli="${lead}pcb([[:space:]]+\\+[A-Za-z0-9._-]+)?[[:space:]]+(layout|import|apply|new|fmt|fix|migrate|route|embed-step)([[:space:]]|\$)"
    gen="${lead}pcb-component-gen([[:space:]]|\$)"
    segments=$(printf '%s\n' "$cmd" | tr ';&|' '\n\n\n')
    if printf '%s' "$cmd" | grep -qE "$redirect|$inplace|$tee"; then
      what="a shell write into a KiCad or Zener design file"
    elif printf '%s' "$cmd" | grep -qE "$upgrade"; then
      what="kicad-cli upgrade (rewrites the design file in place)"
    elif printf '%s\n' "$segments" | grep -E "$pcbcli" | grep -qv -- '--check'; then
      what="a pcb command that writes the board (layout, import, apply, new, fmt, fix, migrate, route, embed-step)"
    elif printf '%s\n' "$segments" | grep -qE "$gen"; then
      what="pcb-component-gen (writes a symbol and a footprint)"
    fi
    ;;
esac
[ -n "$what" ] || exit 0

transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
agent_id=$(printf '%s' "$input" | jq -r '.agent_id // empty')
if [ -n "$agent_id" ]; then
  tf="${transcript%.jsonl}/subagents/agent-${agent_id}.jsonl"; who="this subagent"
else
  tf="$transcript"; who="the main session"
fi
model=""
if [ -n "$transcript" ] && [ -f "$tf" ]; then
  # -R + fromjson? so one unparsable line doesn't hide the lines after it.
  model=$(tail -n 500 "$tf" | jq -rR 'fromjson? | select(.type=="assistant") | .message.model // empty' 2>/dev/null | grep -E '^claude-' | tail -n 1)
fi
case "$model" in claude-fable-*) exit 0 ;; esac

if [ -n "$model" ]; then
  seen="$who is on $model"
else
  seen="no model is on record yet for $who (a subagent's first tool call has none: make a read call first, then retry)"
fi
jq -n --arg reason "Blocked: $what. KiCad design files and Zener board sources are changed by a Claude Fable model only, per CLAUDE.md; $seen. Hand the edit to Fable: a main session on Fable, a fork of it, or the Agent tool with subagent_type \"general-purpose\" and model \"fable\", following the pcb-author skill. Other models review through kicad-review and report findings as text." \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
exit 0
