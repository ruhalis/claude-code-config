#!/usr/bin/env bash
set -euo pipefail

# Install this repo's agent config into Claude Code, and its extension list
# and settings into VS Code.
#
#   ./install.sh                    install into every tool detected on this machine
#   ./install.sh claude             install into one tool
#   ./install.sh claude vscode      install into several
#   ./install.sh vscode             merge the VS Code settings, install missing extensions
#   ./install.sh skills             link only the skills (global and per-project)
#   ./install.sh all                install into all tools, detected or not
#   ./install.sh --dry-run all      print the plan, change nothing
#
# Layout:
#   core/          source of truth: agents, skills (linked into ~/.claude/skills) and
#                  optional-skills (linked into the projects named in its projects.txt)
#   adapters/claude/  CLAUDE.md + output-styles/ + statusline.sh + settings.json and
#                  keybindings.json (both merged) + hooks/ + mods/ + bin/clangd
#   adapters/vscode/  extensions.txt + settings.json (merged)
#   scripts/       skill lint, bench, cleanup

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_ROOT="$HOME/.agent-config-backups/$(date +%Y%m%d-%H%M%S)"

DRY_RUN=0
TOOLS=()

# ---------------------------------------------------------------- output ----

if [ -t 1 ]; then
    B=$'\033[1m'; DIM=$'\033[2m'; YEL=$'\033[33m'; RED=$'\033[31m'; RST=$'\033[0m'
else
    B=""; DIM=""; YEL=""; RED=""; RST=""
fi

step() { printf '\n%s==> %s%s\n' "$B" "$1" "$RST"; }
say()  { printf '    %s\n' "$1"; }
note() { printf '    %s%s%s\n' "$DIM" "$1" "$RST"; }
warn() { printf '    %s! %s%s\n' "$YEL" "$1" "$RST" >&2; }
die()  { printf '%serror: %s%s\n' "$RED" "$1" "$RST" >&2; exit 1; }

usage() { awk 'NR == 1 { next } /^#/ { seen = 1; sub(/^# ?/, ""); print; next } seen { exit }' "${BASH_SOURCE[0]}"; exit 0; }

# ------------------------------------------------------------ primitives ----

# Every filesystem mutation goes through these so --dry-run is airtight.

mk() {  # mk <dir>
    [ "$DRY_RUN" = 1 ] || mkdir -p "$1"
}

# Bookkeeping for link(). GONE: paths backup() and drop() cleared this run, one
# "<path><TAB><old link target>" per line, so link() can still say what was
# there; under --dry-run nothing is cleared, and this is how link() knows a real
# file would have been backed up. LINKED: every dst link() made, or under
# --dry-run would make, one per line.
GONE=""
LINKED=""
gone() { GONE+="$1"$'\t'"$2"$'\n'; }  # gone <path> <old target, empty if not a link>
was_gone() {  # was_gone <path> — print its old target; fail if it was not cleared
    printf '%s' "$GONE" | awk -F'\t' -v p="$1" '$1 == p { t = $2; hit = 1 } END { if (!hit) exit 1; print t }'
}

# link <src> <dst> — says new, exists (already this link) or replace. Refuses a
# real file or directory at dst: ln -sfn would overwrite the file, or nest the
# link inside the directory while the directory stays in use.
link() {
    local src="$1" dst="$2" old state
    if [ -L "$dst" ]; then
        old=$(readlink "$dst")
        if [ "$old" = "$src" ]; then state=exists; else state=replace; fi
    elif old=$(was_gone "$dst"); then
        if [ "$old" = "$src" ]; then state=exists; else state=replace; fi
    elif [ -e "$dst" ]; then
        if [ -d "$dst" ]; then old="directory"; else old="file"; fi
        warn "$dst is a real $old, not a link; left alone. Move it away and re-run to link ${src#"$REPO_DIR"/}."
        return 0
    else
        state=new
    fi
    say "link $(printf '%-7s' "$state") $dst -> ${src#"$REPO_DIR"/}"
    LINKED+="$dst"$'\n'
    [ "$DRY_RUN" = 1 ] || { mkdir -p "$(dirname "$dst")"; ln -sfn "$src" "$dst"; }
}

copy() {  # copy <src> <dst>
    say "copy $2"
    [ "$DRY_RUN" = 1 ] || { mkdir -p "$(dirname "$2")"; cp "$1" "$2"; }
}

# jq programs for merge_json; input is `jq -s live repo`.
# Settings: repo wins recursively (arrays are replaced); live-only keys survive;
# the four keys Claude Code writes itself keep their live value when live has them.
# Retired keys are deleted last: the merge alone would keep a key the repo no
# longer declares. subagentStatusLine is deprecated in favour of mods (agent-rows);
# the plugins and marketplaces listed were removed from the setup on 2026-11-27.
JQ_SETTINGS='((.[0] * .[1]) + (.[0] | with_entries(select(.key | IN("model","modelSettings","effortLevel","autoMode"))))) | del(.subagentStatusLine, .enabledPlugins["kicad-happy@kicad-happy"], .enabledPlugins["desktop-commander@claude-plugins-official"], .enabledPlugins["rea@rea"], .extraKnownMarketplaces["kicad-happy"], .extraKnownMarketplaces["rea"])'
# Keybindings: per context, live blocks then repo blocks, repo winning per key.
JQ_KEYBINDINGS='(.[0] * .[1]) + {bindings: ((((.[0].bindings // []) + (.[1].bindings // [])) | group_by(.context)) | map({context: .[0].context, bindings: (map(.bindings) | add)}))}'
# VS Code settings: repo wins on the keys it declares; every live-only key survives.
JQ_VSCODE='.[0] * .[1]'

# merge_check <src> <dst> <jq program> — stop unless merge_json can merge src
# into dst. Run for every merged Claude file before anything is changed. A live
# file that cannot be merged is never replaced by the repo copy: that would drop
# the keys only the live file has (model, modelSettings, effortLevel, autoMode).
merge_check() {
    local src="$1" dst="$2" prog="$3"
    [ -f "$dst" ] && [ ! -L "$dst" ] || return 0   # no live file to lose; merge_json copies
    command -v jq >/dev/null 2>&1 ||
        die "jq not found, so $dst cannot be merged. Install jq (brew install jq) and re-run. Nothing was changed."
    jq -e . "$dst" >/dev/null 2>&1 ||
        die "$dst is not valid JSON, so it cannot be merged. Fix it or move it away, then re-run. Nothing was changed."
    jq -s "$prog" "$dst" "$src" 2>/dev/null | jq -e . >/dev/null 2>&1 ||
        die "merging ${src#"$REPO_DIR"/} into $dst failed (is its top level a JSON object?). Fix it or move it away, then re-run. Nothing was changed."
}

# merge_json <src> <dst> <jq program> [backup label, default claude] — back up
# and merge: repo (src) over live (dst). A missing or non-regular dst is backed
# up and replaced by a copy. A live file that cannot be merged (no jq, invalid
# JSON, a failing merge) stops the install and stays as it is; merge_check
# catches those cases earlier, before anything is changed. The merge goes to a
# temp file and is validated before backup() moves dst away.
merge_json() {
    local src="$1" dst="$2" prog="$3" label="${4:-claude}" tmp changed
    if [ ! -f "$dst" ] || [ -L "$dst" ]; then
        backup "$dst" "$label"
        copy "$src" "$dst"
        return 0
    fi
    command -v jq >/dev/null 2>&1 || die "jq not found; $dst left as it is, not merged"
    jq -e . "$dst" >/dev/null 2>&1 || die "$dst is not valid JSON; left as it is, not merged"
    tmp=$(mktemp "${TMPDIR:-/tmp}/merge.XXXXXX")
    if ! jq -s "$prog" "$dst" "$src" > "$tmp" || ! jq -e . "$tmp" >/dev/null 2>&1; then
        rm -f "$tmp"
        die "merge of $dst failed; left as it is, not merged"
    fi
    if [ "$DRY_RUN" = 1 ]; then
        changed=$(jq -rn --slurpfile a "$dst" --slurpfile b "$tmp" \
            '[$b[0] | keys[] as $k | select($a[0][$k] != $b[0][$k]) | $k] | join(", ")')
        say "merge $dst (top-level keys that would change: ${changed:-none})"
        rm -f "$tmp"
        backup "$dst" "$label"
        return 0
    fi
    say "merge $dst"
    backup "$dst" "$label"
    mv "$tmp" "$dst"
}

# drop <path> — remove one of our own symlinks; link() recreates it.
drop() {
    gone "$1" "$(readlink "$1")"
    [ "$DRY_RUN" = 1 ] || rm "$1"
}

# backup <path> <label> — move an existing real file/dir out of the way.
# Symlinks into this repo are ours; drop them silently, they get recreated.
backup() {
    local path="$1" label="$2"
    [ -e "$path" ] || [ -L "$path" ] || return 0
    if [ -L "$path" ]; then
        case "$(readlink "$path")" in
            "$REPO_DIR"/*) drop "$path"; return 0 ;;
        esac
    fi
    say "backup $path -> $BACKUP_ROOT/$label/"
    gone "$path" ""
    [ "$DRY_RUN" = 1 ] || {
        mkdir -p "$BACKUP_ROOT/$label"
        mv "$path" "$BACKUP_ROOT/$label/$(basename "$path")"
    }
}

# sweep_dir <dir> <label> [keep] — make dir mirror the repo exactly: everything
# not ours is backed up, except entries named in the space-separated keep list.
# ONLY for directories this repo owns outright.
sweep_dir() {
    local dir="$1" label="$2" keep=" ${3-} " entry
    [ -d "$dir" ] || return 0
    for entry in "$dir"/* "$dir"/.[!.]*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        case "$keep" in *" ${entry##*/} "*) continue ;; esac
        backup "$entry" "$label"
    done
}

# ---------------------------------------------------------------- skills ----

# The skills blocks, shared by install_claude and `./install.sh skills`.

link_skills() {  # link_skills <dir> — link every core/skills/<name> into dir
    local d
    for d in "$REPO_DIR"/core/skills/*/; do
        [ -d "$d" ] || continue
        link "${d%/}" "$1/$(basename "$d")"
    done
}

# ~/.claude/skills is swept. synced/ holds the claude.ai skills and .trash/ is
# where Claude Code parks them when syncing is turned off; both belong to
# Claude Code, not this repo.
skills_claude() {
    mk "$1"
    sweep_dir "$1" claude/skills "synced .trash"
    link_skills "$1"
}

# report_skills <dir>... — name every core skill a dir does not link to this
# repo. A dry run counts the links it planned above as made.
report_skills() {
    local dir d n missing other clean=1
    for dir in "$@"; do
        missing=""; other=""
        for d in "$REPO_DIR"/core/skills/*/; do
            [ -d "$d" ] || continue
            n=$(basename "$d")
            if [ -L "$dir/$n" ] && [ "$(readlink "$dir/$n")" = "${d%/}" ]; then
                continue
            elif [ "$DRY_RUN" = 1 ] && printf '%s' "$LINKED" | grep -Fxq -- "$dir/$n"; then
                continue
            elif [ -e "$dir/$n" ] || [ -L "$dir/$n" ]; then
                other+=" $n"
            else
                missing+=" $n"
            fi
        done
        [ -z "$missing" ] || { warn "missing from $dir:$missing"; clean=0; }
        [ -z "$other" ] || { warn "in $dir but not linked to this repo:$other"; clean=0; }
    done
    [ "$clean" = 0 ] || note "every core skill is linked from $*"
}

# Optional skills live in core/optional-skills and are linked only into the
# projects that use them: <project>/.claude/skills/<name>. projects.txt maps
# each skill to its project directories; one missing on this machine is skipped.
# The link holds an absolute path of this machine, so it is listed in the
# project's .git/info/exclude instead of being committed there.
link_optional_skills() {
    local map="$REPO_DIR/core/optional-skills/projects.txt" name dirs p src excl
    [ -f "$map" ] || return 0
    step "Optional skills -> projects"
    while read -r name dirs; do
        case "$name" in ''|'#'*) continue ;; esac
        src="$REPO_DIR/core/optional-skills/$name"
        [ -d "$src" ] || { warn "projects.txt names $name, which is not in core/optional-skills"; continue; }
        for p in $dirs; do
            p="${p/#\~/$HOME}"
            [ -d "$p" ] || { note "$name: $p is not on this machine; skipped"; continue; }
            backup "$p/.claude/skills/$name" "projects/$(basename "$p")"
            link "$src" "$p/.claude/skills/$name"
            excl=$(git -C "$p" rev-parse --git-path info/exclude 2>/dev/null) || continue
            case "$excl" in /*) ;; *) excl="$p/$excl" ;; esac
            grep -Fxq ".claude/skills/$name" "$excl" 2>/dev/null && continue
            say "exclude .claude/skills/$name in $excl"
            [ "$DRY_RUN" = 1 ] || { mkdir -p "$(dirname "$excl")"; printf '%s\n' ".claude/skills/$name" >> "$excl"; }
        done
    done < "$map"
}

install_skills() {
    local c="$HOME/.claude/skills"
    step "Skills -> $c"
    skills_claude "$c"
    report_skills "$c"
    link_optional_skills
}

# Lint core/skills. It only reports:
# a skill that fails is still linked, because the linked copy is the one to fix.
skill_checks() {
    step "Skill checks"
    "$REPO_DIR/scripts/check-skills.sh" --quiet 2>&1 | sed 's/^/    /' ||
        warn "check-skills failed; run scripts/check-skills.sh for the full report"
}

# ----------------------------------------------------------------- tools ----

# Run before anything is changed. jq is required outright: the settings merge
# needs it, and both guard hooks fail closed without it, so a machine without jq
# would have every Bash call blocked.
preflight_claude() {
    local dir="$HOME/.claude"
    command -v jq >/dev/null 2>&1 ||
        die "jq not found. The settings merge needs it, and the guard hooks block every Bash call without it. Install jq (brew install jq) and re-run. Nothing was changed."
    merge_check "$REPO_DIR/adapters/claude/settings.json" "$dir/settings.json" "$JQ_SETTINGS"
    merge_check "$REPO_DIR/adapters/claude/keybindings.json" "$dir/keybindings.json" "$JQ_KEYBINDINGS"
}

install_claude() {
    local dir="$HOME/.claude"
    step "Claude Code -> $dir"
    mk "$dir"

    # status line: this repo's own script. It reads only the JSON Claude Code
    # pipes to it. The first line clears the link to the third-party submodule it
    # replaced on 2026-11-27 (that one read the login token to fetch usage).
    backup "$dir/statusline" claude
    backup "$dir/statusline.sh" claude
    link "$REPO_DIR/adapters/claude/statusline.sh" "$dir/statusline.sh"
    [ "$DRY_RUN" = 1 ] || chmod +x "$REPO_DIR/adapters/claude/statusline.sh"

    # output styles: orchestrator.md carries the main-session rules (subagents
    # never receive an output style); settings.json selects it with outputStyle.
    # Not swept: the folder may hold styles of the user's own.
    mk "$dir/output-styles"
    local o
    for o in "$REPO_DIR"/adapters/claude/output-styles/*.md; do
        [ -e "$o" ] || continue
        backup "$dir/output-styles/${o##*/}" claude
        link "$o" "$dir/output-styles/${o##*/}"
    done

    # mods (hooks modules), loaded through CLAUDE_CODE_PLUGIN_DIRS in
    # settings.json's env, which names each link below. agent-rows draws the
    # agent-list row body (type, model, effort); it replaced the script behind
    # the deprecated subagentStatusLine setting, whose link is cleared here.
    backup "$dir/subagent-statusline.sh" claude
    mk "$dir/mods"
    local m
    for m in "$REPO_DIR"/adapters/claude/mods/*/; do
        [ -d "$m" ] || continue
        m="${m%/}"
        backup "$dir/mods/${m##*/}" claude
        link "$m" "$dir/mods/${m##*/}"
    done

    # hooks, wired in settings.json: the main-session guard (PreToolUse on Bash)
    # and the git-write guard (PreToolUse on Bash; no commit, push, merge ... for anyone)
    mk "$dir/hooks"
    local h
    for h in guard-main-session.sh guard-git-write.sh; do
        backup "$dir/hooks/$h" claude
        link "$REPO_DIR/adapters/claude/hooks/$h" "$dir/hooks/$h"
        [ "$DRY_RUN" = 1 ] || chmod +x "$REPO_DIR/adapters/claude/hooks/$h"
    done
    # The KiCad guard was removed on 2026-11-27. A session started before the
    # settings merge below still calls its path on every Edit, Write and Bash with
    # onFailure: block, and a missing script would block them all. So a link left
    # from the old install becomes a no-op file; delete it by hand once every
    # session has been restarted.
    h="$dir/hooks/guard-kicad-edit.sh"
    if [ -L "$h" ]; then
        say "retire $h (no-op until sessions restart)"
        [ "$DRY_RUN" = 1 ] || {
            printf '#!/bin/sh\n# Retired 2026-11-27 with the KiCad guard; safe to delete once every session has restarted.\nexit 0\n' > "$h.new"
            chmod +x "$h.new"
            mv -f "$h.new" "$h"
        }
    fi

    # clangd wrapper. The clangd-lsp plugin starts the first `clangd` on PATH with
    # a fixed command line, so this one has to come before the system clangd:
    # ~/.local/bin must sit ahead of /usr/bin on PATH. In a workspace that holds
    # an ESP-IDF project it runs Espressif's clangd with --query-driver; anywhere
    # else, the system clangd unchanged.
    # ~/.local/bin is shared, unlike ~/.claude: a clangd already there that is not
    # this repo's link (a real binary, or a link to one) may be the machine's only
    # clangd, so it is left alone instead of backed up. A dangling link there is
    # nobody's clangd (this repo's old path after a rename) and is replaced.
    local wrapper_dst="$HOME/.local/bin/clangd"
    if [ -e "$wrapper_dst" ] \
        && [[ "$(readlink "$wrapper_dst" 2>/dev/null)" != "$REPO_DIR"/* ]]; then
        warn "$wrapper_dst is another clangd, not this repo's wrapper; left alone. To use the wrapper, move it to a directory later on PATH (the wrapper falls back to /usr/bin/clangd, then the next clangd on PATH) and re-run."
    else
        mk "$HOME/.local/bin"
        backup "$wrapper_dst" claude
        link "$REPO_DIR/adapters/claude/bin/clangd" "$wrapper_dst"
        [ "$DRY_RUN" = 1 ] || chmod +x "$REPO_DIR/adapters/claude/bin/clangd"
    fi

    # instructions
    backup "$dir/CLAUDE.md" claude
    link "$REPO_DIR/adapters/claude/CLAUDE.md" "$dir/CLAUDE.md"

    # agents — core format is Claude format, so these link straight through
    mk "$dir/agents"
    sweep_dir "$dir/agents" claude/agents
    local f
    for f in "$REPO_DIR"/core/agents/*.md; do
        [ -e "$f" ] || continue
        link "$f" "$dir/agents/$(basename "$f")"
    done

    # skills — swept, except Claude Code's own synced/ and .trash/
    skills_claude "$dir/skills"
    link_optional_skills

    # settings and keybindings are merged copies: Claude rewrites settings.json
    # in place (theme, model, effort, plugins), and a symlink would push that
    # into the repo. The repo wins on the keys it declares; the live file keeps
    # the rest (see merge_json).
    say "repo keys win; the live file keeps model, modelSettings, effortLevel and autoMode"
    merge_json "$REPO_DIR/adapters/claude/settings.json" "$dir/settings.json" "$JQ_SETTINGS"
    merge_json "$REPO_DIR/adapters/claude/keybindings.json" "$dir/keybindings.json" "$JQ_KEYBINDINGS"
}

# --------------------------------------------------------------- vscode ----

# VS Code's CLI. `code` is only on PATH after "Shell Command: Install 'code'
# command in PATH" from the Command Palette; fall back to the macOS app bundle.
vscode_cli() {
    local c
    if c=$(command -v code 2>/dev/null); then printf '%s\n' "$c"; return 0; fi
    c="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    if [ -x "$c" ]; then printf '%s\n' "$c"; return 0; fi
    return 1
}

# Normalise an extension list (stdin) to one lowercase ID per line, sorted, so
# the lists can be diffed with comm. Marketplace IDs are case-insensitive and
# `--list-extensions` prints them lowercase. Strips comments and blank lines.
ext_ids() {
    awk '{ sub(/#.*/, ""); gsub(/[[:space:]]/, ""); if ($0 != "") print tolower($0) }' | sort -u
}

# VS Code's user settings directory (default profile).
vscode_user_dir() {
    case "$(uname -s)" in
        Darwin) printf '%s\n' "$HOME/Library/Application Support/Code/User" ;;
        *)      printf '%s\n' "${XDG_CONFIG_HOME:-$HOME/.config}/Code/User" ;;
    esac
}

# settings.json is a merged copy, like Claude's: VS Code rewrites it from the
# Settings UI. It is JSONC to VS Code, so a live file with comments or trailing
# commas fails jq; that file, a symlink (someone else's dotfiles), or a live file
# with no jq around is left alone, because merge_json would replace it with the
# repo's few keys. Needs no `code` CLI, so it runs before the extensions.
vscode_settings() {
    local src="$REPO_DIR/adapters/vscode/settings.json" dst
    dst="$(vscode_user_dir)/settings.json"
    step "VS Code settings -> $dst"
    [ -f "$src" ] || die "missing $src"
    if [ -L "$dst" ]; then
        warn "$dst is a symlink; left alone. Copy the keys from ${src#"$REPO_DIR"/} into its target by hand."
        return 0
    fi
    if [ -f "$dst" ]; then
        if ! command -v jq >/dev/null 2>&1; then
            warn "jq not found; $dst left alone. Install jq and re-run."
            return 0
        fi
        if ! jq -e . "$dst" >/dev/null 2>&1; then
            warn "$dst is not plain JSON (comments or trailing commas?); left alone. Copy the keys from ${src#"$REPO_DIR"/} by hand."
            return 0
        fi
    fi
    say "repo keys win; the live file keeps every other key"
    merge_json "$src" "$dst" "$JQ_VSCODE" vscode
}

install_vscode() {
    vscode_settings

    local list="$REPO_DIR/adapters/vscode/extensions.txt" code
    step "VS Code extensions"
    [ -f "$list" ] || die "missing $list"
    code=$(vscode_cli) || {
        warn "VS Code CLI not found; skipping. Install VS Code, then run \"Shell Command: Install 'code' command in PATH\" from the Command Palette."
        return 0
    }
    note "using $code"

    local wanted have missing extra
    wanted=$(ext_ids < "$list")
    have=$("$code" --list-extensions 2>/dev/null | ext_ids)
    missing=$(comm -23 <(printf '%s\n' "$wanted") <(printf '%s\n' "$have"))
    extra=$(comm -13 <(printf '%s\n' "$wanted") <(printf '%s\n' "$have"))

    if [ -z "$missing" ]; then
        note "all $(printf '%s\n' "$wanted" | wc -l | tr -d ' ') extensions already installed"
    else
        local args=() id
        while IFS= read -r id; do
            say "install $id"
            args+=(--install-extension "$id")
        done <<< "$missing"
        if [ "$DRY_RUN" = 0 ]; then
            # One invocation: every `code` launch costs a second or two. A
            # marketplace failure must not abort the rest of the install; the
            # re-check below reports what did not land.
            "$code" "${args[@]}" 2>&1 | sed 's/^/      /' || true
            missing=$(comm -23 <(printf '%s\n' "$wanted") <("$code" --list-extensions 2>/dev/null | ext_ids))
            [ -z "$missing" ] || warn "not installed: $(printf '%s' "$missing" | tr '\n' ' ')"
        fi
    fi
    # Report, never remove: the list is what a fresh machine should get, not a
    # ban on installing anything else.
    [ -z "$extra" ] || note "installed here but not in extensions.txt: $(printf '%s' "$extra" | tr '\n' ' ')"
}

# ------------------------------------------------------------------ main ----

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage ;;
        -n|--dry-run) DRY_RUN=1 ;;
        all) TOOLS=(claude vscode) ;;
        claude|vscode|skills) TOOLS+=("$1") ;;
        -*) die "unknown flag: $1 (try --help)" ;;
        *) die "unknown tool: $1 (expected claude, vscode, skills, or all)" ;;
    esac
    shift
done

if [ ${#TOOLS[@]} -eq 0 ]; then
    if command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ]; then TOOLS+=(claude); fi
    if vscode_cli >/dev/null 2>&1 || [ -d "$HOME/.vscode" ]; then TOOLS+=(vscode); fi
    [ ${#TOOLS[@]} -gt 0 ] || die "no supported tool detected; name one explicitly (claude|vscode|skills)"
    note "detected: ${TOOLS[*]}"
fi

# de-duplicate while preserving order
UNIQ=()
for t in "${TOOLS[@]}"; do
    case " ${UNIQ[*]-} " in *" $t "*) continue ;; esac
    UNIQ+=("$t")
done
TOOLS=("${UNIQ[@]}")

# Stop here, before anything is changed, if the Claude merges cannot work.
case " ${TOOLS[*]} " in
    *" claude "*) preflight_claude ;;
esac

printf '%sInstalling from %s%s\n' "$B" "$REPO_DIR" "$RST"
[ "$DRY_RUN" = 1 ] && printf '%s(dry run — nothing will be written)%s\n' "$YEL" "$RST"

# The one submodule is the upstream anatomy skill.
case " ${TOOLS[*]} " in
    *" claude "*)
        if [ -f "$REPO_DIR/.gitmodules" ] && [ "$DRY_RUN" = 0 ]; then
            git -C "$REPO_DIR" submodule update --init --recursive
        fi ;;
esac

for t in "${TOOLS[@]}"; do
    "install_$t"
done

case " ${TOOLS[*]} " in
    *" claude "*|*" skills "*) skill_checks ;;
esac

printf '\n%sDone.%s Restart the tools you installed into.\n' "$B" "$RST"
[ -d "$BACKUP_ROOT" ] && say "backups: $BACKUP_ROOT"
exit 0
