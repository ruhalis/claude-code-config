#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash). Denies the git commands that write history,
# for the main session and subagents alike: Claude never commits or pushes in
# this setup (CLAUDE.md, # Git). Denied: git commit, push, merge, rebase,
# cherry-pick, revert and tag; the sweeping git add forms (-A, --all, -u,
# --update, ., ./, :/ and short-flag groups holding A or u); gh pr create.
# It exists next to the permissions.deny rules because those match the command
# text only, so `git -C dir commit`, `git -c k=v commit` or `git --git-dir=.git
# push` slip past them. This hook finds the real subcommand: it skips VAR=value
# prefixes, the wrappers env, command, exec, time, nohup, sudo, xargs, timeout,
# nice, caffeinate and stdbuf, and git's global options, in every simple command
# of the line, including those inside $(...), backticks, subshells and the
# string after `bash|sh|zsh|dash -c`. Heredoc bodies, other quoted strings and
# comments are ignored, so prose that mentions a command doesn't trip it.
# Best effort: git aliases and scripts that run git themselves are not seen.
# Set GUARD_GIT_WRITE_OFF=1 in settings `env` to disable without removing the
# hook. Exit 0 with no output = no decision.
set -u
[ "${GUARD_GIT_WRITE_OFF:-0}" = "1" ] && exit 0
# Fail closed without jq: exit 1 is a hook failure, so onFailure "block" stops the call.
command -v jq >/dev/null 2>&1 || { echo "guard-git-write: jq missing; install jq (brew install jq) or set GUARD_GIT_WRITE_OFF=1" >&2; exit 1; }

input=$(cat)
tool=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)
[ -z "$tool" ] || [ "$tool" = "Bash" ] || exit 0
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
[ -n "$cmd" ] || exit 0

# Prints the first history-writing command found ("commit", "add -A", "gh pr create"), or nothing.
found=$(printf '%s\n' "$cmd" | awk -v q="'" '
  # Heredoc bodies are dropped, as in guard-main-session.sh (<<< is a here-string, not a heredoc).
  delim != "" { line = $0; if (strip) sub(/^\t+/, "", line); if (line == delim) delim = ""; next }
  {
    line = $0
    probe = line
    gsub(/<<</, "###", probe)
    re = "<<-?[ \t]*[\"" q "]?[A-Za-z_][A-Za-z0-9_]*[\"" q "]?"
    if (match(probe, re)) {
      d = substr(probe, RSTART, RLENGTH)
      strip = (substr(d, 3, 1) == "-")
      sub("^<<-?[ \t]*[\"" q "]?", "", d)
      sub("[\"" q "]$", "", d)
      delim = d
    }
    s = s "\n" line
  }
  # scan(text): quoted strings (which may span lines) become an empty word, as prose, except
  # a double-quoted one holding $( or a backtick, whose command runs, and the string after a
  # shell -c (bash, sh, zsh, dash), which is a command line of its own. Comments and escapes go.
  function scan(s,   t, c, k, body, tail) {
    t = ""
    while (s != "") {
      if (!(k = match(s, "[\\\\\"#" q "]"))) { t = t s; break }
      t = t substr(s, 1, k - 1); c = substr(s, k, 1); s = substr(s, k + 1)
      if (c == "\\") { k = substr(s, 1, 1); t = t (k == "\n" ? " " : (index(q "\"`$\\#", k) ? "_" : k)); s = substr(s, 2); continue }
      if (c == "#") {
        k = substr(t, length(t), 1)
        if (t == "" || index(" \t\n;&|(", k)) { k = index(s, "\n"); s = k ? substr(s, k) : "" } else t = t c
        continue
      }
      if (c == q) { k = index(s, q); body = k ? substr(s, 1, k - 1) : s; s = k ? substr(s, k + 1) : "" }
      else if (match(s, /^([^"\\]|\\.)*"/)) { body = substr(s, 1, RLENGTH - 1); s = substr(s, RLENGTH + 1) }
      else { body = s; s = "" }
      tail = substr(t, length(t) > 200 ? length(t) - 199 : 1)
      if (tail ~ /(^|[ \t\n;&|(])([^ \t\n;&|()]*\/)?(ba|z|da)?sh([ \t]+-[-A-Za-z]+)*[ \t]+-[A-Za-z]*c[A-Za-z]*[ \t]*$/) t = t "\n" scan(body) "\n"
      else if (c == "\"" && body ~ /[$][(]|`/) t = t scan(body)
      else t = t q q
    }
    return t
  }
  # takes(wrapper, flag): does this wrapper option consume the next word?
  function takes(c, f) {
    return (c == "env" && f ~ /^-[uCP]$/) || (c == "sudo" && f ~ /^-[ughpCUDRTrt]$/) ||
      (c == "xargs" && f ~ /^-[nIJLPsdERSa]$/) || (c == "exec" && f == "-a") ||
      (c == "timeout" && f ~ /^-[sk]$/) || (c == "nice" && f == "-n") ||
      (c == "caffeinate" && f ~ /^-[tw]$/) || (c == "stdbuf" && f ~ /^-[ioe]$/)
  }
  function classify(line,   w, n, i, c, base, want) {
    gsub(/[0-9]*[<>]+[ \t]*[^ \t<>]*/, " ", line)    # redirections and their targets, wherever they sit
    sub(/^[ \t]+/, "", line)
    n = split(line, w, /[ \t]+/)
    i = 1
    # Before the command word: assignments, shell keywords and wrappers with their options.
    while (i <= n) {
      c = w[i]
      if (c ~ /^[A-Za-z_][A-Za-z0-9_]*=/ || c ~ /^(!|[{]|if|then|else|elif|do|while|until)$/) { i++; continue }
      if (c ~ /^(env|command|exec|time|nohup|sudo|xargs|timeout|nice|caffeinate|stdbuf)$/) {
        for (i++; i <= n && w[i] ~ /^-/; i++) {
          if (w[i] == "--") { i++; break }
          if (takes(c, w[i])) i++
        }
        if (c == "timeout") i++                # its duration
        continue
      }
      break
    }
    if (i > n) return ""
    base = w[i]; sub(/.*\//, "", base)
    if (base == "git") {
      # Global options before the subcommand; these take their value as the next word.
      for (i++; i <= n && w[i] ~ /^-/; i++)
        if (w[i] ~ /^(-C|-c|--git-dir|--work-tree|--namespace|--config-env|--super-prefix)$/) i++
      if (i > n) return ""
      if (w[i] ~ /^(commit|push|merge|rebase|cherry-pick|revert|tag)$/) return w[i]
      if (w[i] == "add")
        for (i++; i <= n; i++)
          if (w[i] ~ /^(-A|--all|-u|--update|\.|\.\/|:\/)$/ || w[i] ~ /^-[A-Za-z]*[Au][A-Za-z]*$/) return "add " w[i]
      return ""
    }
    if (base == "gh") {
      want = "pr"
      for (i++; i <= n; i++) {
        if (w[i] ~ /^(-R|--repo)$/) { i++; continue }
        if (w[i] ~ /^-/) continue
        if (w[i] != want) return ""
        if (want == "create") return "gh pr create"
        want = "create"
      }
    }
    return ""
  }
  END {
    s = scan(s)
    gsub(/[$][{][^}]*[}]/, "V", s)            # ${...} is one word
    # Command substitutions, innermost first: the inner command becomes its own line, the outer gets a word.
    while (match(s, /[$][(][^()]*[)]/)) { extra = extra "\n" substr(s, RSTART + 2, RLENGTH - 3); s = substr(s, 1, RSTART - 1) "V" substr(s, RSTART + RLENGTH) }
    while (match(s, /`[^`]*`/)) { extra = extra "\n" substr(s, RSTART + 1, RLENGTH - 2); s = substr(s, 1, RSTART - 1) "V" substr(s, RSTART + RLENGTH) }
    s = s extra
    # Simple commands: split on ; & | (so && || too), newlines, and any $( ` ( ) left over.
    gsub(/[$][(]|[`();&|]/, "\n", s)
    n = split(s, lines, "\n")
    for (k = 1; k <= n; k++) { r = classify(lines[k]); if (r != "") { print r; exit } }
  }' 2>/dev/null)
[ -n "$found" ] || exit 0

case "$found" in
  add*) reason="Blocked: git $found stages every change at once, and in this setup Claude stages explicit paths only. Name each file (git add <path> <path>), check with git diff --cached --stat, and give the user the git commit command to run themselves with the ! prefix." ;;
  "gh pr create") reason="Blocked: gh pr create. Claude never commits, pushes or opens pull requests in this setup; stage the files with git add <path> and give the user the git commit, git push and gh pr create commands to run themselves with the ! prefix." ;;
  tag) reason="Blocked: git tag. Claude never commits, pushes or tags in this setup (list tags with git for-each-ref refs/tags); stage the files with git add <path> and give the user the git commit command to run themselves with the ! prefix." ;;
  *) reason="Blocked: git $found. Claude never commits or pushes in this setup (no commit, push, merge, rebase, cherry-pick, revert or tag); stage the files with git add <path> and give the user the git commit command to run themselves with the ! prefix." ;;
esac
jq -n --arg reason "$reason" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
exit 0
