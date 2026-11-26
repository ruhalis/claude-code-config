#!/usr/bin/env bash
# Claude Code status line, in the layout and colours of the third-party script it replaced:
#   Model (effort) | dir@branch (+12 -3) | 129k/1m (12%) | 5h 29% @20:00 | 7d 64% @Thu Apr 23, 21:00 | v2.1.332
# It reads only the JSON Claude Code pipes to stdin (code.claude.com/docs/en/statusline): no network
# and no credentials. That is why the old "extra" spend segment is gone: it came from a usage
# request made with the login token. rate_limits arrives on subscription logins after the first
# reply and each window can be missing, so a segment is printed only when its value is there.
input=$(cat)
us=$'\x1f'   # not whitespace, so read keeps empty fields
IFS=$us read -r model effort cwd used size h5 h5r d7 d7r ver < <(jq -r --arg s "$us" '
    def n: if . == null then "" else floor | tostring end;
    [ .model.display_name // "Claude", .effort.level // "", .cwd // "",
      (.context_window.current_usage | if . == null then 0 else
          (.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0) end | n),
      (.context_window.context_window_size | n),
      (.rate_limits.five_hour.used_percentage | n), (.rate_limits.five_hour.resets_at | n),
      (.rate_limits.seven_day.used_percentage | n), (.rate_limits.seven_day.resets_at | n),
      .version // "" ] | join($s)' <<<"$input" 2>/dev/null)

rgb() { printf '\033[38;2;%sm' "$1"; }
blue=$(rgb '0;153;255') orange=$(rgb '255;176;85') green=$(rgb '0;160;0') cyan=$(rgb '46;149;153')
red=$(rgb '255;85;85') yellow=$(rgb '230;200;0') purple=$(rgb '167;139;250') white=$(rgb '220;220;220')
dim=$'\033[2m' R=$'\033[0m' bar=" $dim|$R "

tok()  { awk -v n="$1" 'BEGIN { if (n >= 1e6) { v = sprintf("%.1f", n / 1e6) + 0; printf (v == int(v) ? "%dm" : "%.1fm"), v }
                              else if (n >= 1000) printf "%.0fk", n / 1000; else printf "%d", n }'; }
heat() { if [ "$1" -ge 90 ]; then printf %s "$red"; elif [ "$1" -ge 70 ]; then printf %s "$orange"
         elif [ "$1" -ge 50 ]; then printf %s "$yellow"; else printf %s "$green"; fi; }
when() { date -r "$1" "+$2" 2>/dev/null || date -d "@$1" "+$2" 2>/dev/null; }   # BSD date, then GNU

out="$blue${model:-Claude}$R"
case "$effort" in
    "") ;; low) e="$dim$effort" ;; medium) e="${orange}med" ;; xhigh) e="$purple$effort" ;; max) e="$red$effort" ;; *) e="$green$effort" ;;
esac
[ -z "$effort" ] || out+=" $dim($R$e$R$dim)$R"
if [ -n "$cwd" ]; then
    out+="$bar$cyan${cwd##*/}$R"
    if branch=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null); then
        out+="$dim@$R$green$branch$R"
        stat=$(git -C "$cwd" diff --numstat 2>/dev/null | awk '{ a += $1; d += $2 } END { if (a + d > 0) printf "+%d -%d", a, d }')
        [ -z "$stat" ] || out+=" $dim($R$green${stat% *}$R $red${stat#* }$R$dim)$R"
    fi
fi
[ "${size:-0}" -gt 0 ] 2>/dev/null && out+="$bar$orange$(tok "$used")/$(tok "$size")$R $dim($R$green$(( used * 100 / size ))%$R$dim)$R"
[ -z "$h5" ] || out+="$bar${white}5h$R $(heat "$h5")$h5%$R${h5r:+ $dim@$(when "$h5r" %H:%M)$R}"
[ -z "$d7" ] || out+="$bar${white}7d$R $(heat "$d7")$d7%$R${d7r:+ $dim@$(when "$d7r" '%a %b %-d, %H:%M')$R}"
[ -z "$ver" ] || out+="$bar${orange}v$ver$R"
printf '%s\n' "$out"
