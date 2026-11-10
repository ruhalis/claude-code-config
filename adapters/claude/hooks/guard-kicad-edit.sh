#!/usr/bin/env bash
# PreToolUse hook (matcher: Edit|Write|Bash|mcp__.*[Kk][Ii][Cc][Aa][Dd].*). KiCad design files
# and Zener board sources are changed by Claude Fable 5.2 or later only (Fable
# 5.1 scored below Opus 5.5 on BenchCAD 2.1); every other model, in the main
# session or in a subagent, is denied and reviews instead (the kicad-review
# skill). The write path is the pcb-author skill.
#
# Guarded: Edit/Write on *.kicad_sch|pcb|pro|sym|mod|wks|dru and *.zen; Bash
# that redirects, tees or edits in place into one of those; the writing
# subcommands of Diode's `pcb` CLI (layout, import, apply, new, fmt, fix,
# migrate, route, embed-step; a segment with --check only validates and passes);
# `pcb-component-gen`; `kicad-cli <sch|pcb|sym|fp> upgrade` (also under
# `cad run`); text-to-cad's board edit API (kicad_pcb.edit / kicad_sch.edit),
# inline in the command or in any existing *.py file the command names (as in
# `cad run board.py`); and KiCad MCP tools whose names say they write (create,
# add, edit, update, set, delete, remove, move, place, route, save, import ...).
# Best effort on Bash: a script that writes the files some other way is not seen.
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
    # text-to-cad's board edit API, inline or inside a named script (relative paths against the call's cwd).
    editapi='kicad_(pcb|sch)\.edit[[:space:]]*\('
    pyedit=""
    cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
    for py in $(printf '%s' "$cmd" | grep -oE "[^[:space:]\"';&|<>()]+\.py" | sort -u); do
      case "$py" in /*) p="$py" ;; "~/"*) p="$HOME/${py#\~/}" ;; *) p="${cwd:-.}/$py" ;; esac
      if [ -f "$p" ] && grep -qE "$editapi" "$p" 2>/dev/null; then pyedit="$py"; break; fi
    done
    if printf '%s' "$cmd" | grep -qE "$redirect|$inplace|$tee"; then
      what="a shell write into a KiCad or Zener design file"
    elif printf '%s' "$cmd" | grep -qE "$upgrade"; then
      what="kicad-cli upgrade (rewrites the design file in place)"
    elif printf '%s\n' "$segments" | grep -E "$pcbcli" | grep -qv -- '--check'; then
      what="a pcb command that writes the board (layout, import, apply, new, fmt, fix, migrate, route, embed-step)"
    elif printf '%s\n' "$segments" | grep -qE "$gen"; then
      what="pcb-component-gen (writes a symbol and a footprint)"
    elif printf '%s' "$cmd" | grep -qE "$editapi"; then
      what="text-to-cad's board edit API (kicad_pcb.edit / kicad_sch.edit)"
    elif [ -n "$pyedit" ]; then
      what="a script that edits a board through text-to-cad's API ($pyedit calls kicad_pcb.edit / kicad_sch.edit)"
    fi
    ;;
  mcp__*)
    # Only KiCad MCP servers reach here (matcher); their read tools pass, their write tools are guarded.
    lc=$(printf '%s' "$tool" | tr '[:upper:]' '[:lower:]')
    case "$lc" in *kicad*) ;; *) exit 0 ;; esac
    verb="${lc##*__}"
    if printf '%s' "$verb" | grep -qE '(^|_)(create|add|new|edit|update|set|delete|remove|move|place|route|autoroute|write|save|modify|import|apply|assign|rotate|connect|draw|fill|refill|upgrade|annotate|sync)(_|$)'; then
      what="the KiCad MCP tool $verb (writes the design)"
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
# Fable 5.2 or later: claude-fable-<major>[-<minor>][-<date or suffix>], minor read as 0 when absent.
fable_ok() {
  case "$1" in claude-fable-*) ;; *) return 1 ;; esac
  v=${1#claude-fable-}
  maj=$(printf '%s' "$v" | sed -nE 's/^([0-9]+)([^0-9].*)?$/\1/p')
  min=$(printf '%s' "$v" | sed -nE 's/^[0-9]+-([0-9]{1,2})([^0-9].*)?$/\1/p')
  [ -n "$maj" ] || return 1
  [ $((10#$maj * 100 + 10#${min:-0})) -ge 502 ]
}
fable_ok "$model" && exit 0

if [ -n "$model" ]; then
  seen="$who is on $model"
else
  seen="no model is on record yet for $who (a subagent's first tool call has none: make a read call first, then retry)"
fi
jq -n --arg reason "Blocked: $what. KiCad design files and Zener board sources are changed by Claude Fable 5.2 or later only, per CLAUDE.md; $seen. Hand the edit to Fable: a main session on Fable, a fork of it, or the Agent tool with subagent_type \"general-purpose\" and model \"fable\", following the pcb-author skill. Other models review through kicad-review and report findings as text." \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
exit 0
