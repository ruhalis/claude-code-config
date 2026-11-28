#!/usr/bin/env python3
"""Flag the surface tells of model-written prose in Markdown, plain text or HTML.

Usage:
    python3 tells.py FILE [FILE ...] [--json] [--all]
    python3 tells.py - < draft.md

Each flag names a category from references/tells.md, with the line number and a
snippet. A flag means "rethink this sentence", not "swap this word": a synonym
for a stock word is the next stock word. Some flags are fine in context.

Line numbers refer to the source file. Fenced code, inline code, YAML front
matter, <script> and <style> are skipped. Stdlib only; exit code 0 unless a
file can't be read (2).
"""

import html
import json
import re
import statistics
import sys

I = re.IGNORECASE


def rx(*patterns, flags=I):
    return [re.compile(p, flags) for p in patterns]


STOCK_WORDS = r"\b(" + "|".join([
    r"delv(?:e|es|ed|ing)", r"tapestr(?:y|ies)", r"testament", r"realms?", r"embark(?:s|ed|ing)?",
    r"beacons?", r"multifaceted", r"intricat(?:e|ely|cies|cy)", r"underscor(?:e|es|ed|ing)",
    r"showcas(?:e|es|ed|ing)", r"foster(?:s|ed|ing)?", r"bolster(?:s|ed|ing)?", r"garner(?:s|ed|ing)?",
    r"leverag(?:e|es|ed|ing)", r"harness(?:es|ed|ing)?", r"seamless(?:ly)?", r"elevat(?:e|es|ed|ing)",
    r"unlock(?:s|ed|ing)?", r"unleash(?:es|ed|ing)?", r"empower(?:s|ed|ing|ment)?",
    r"streamlin(?:e|es|ed|ing)", r"robust(?:ly|ness)?", r"pivotal", r"crucial(?:ly)?", r"paramount",
    r"transformative", r"groundbreaking", r"cutting-edge", r"state-of-the-art", r"game-?chang(?:er|ers|ing)",
    r"revolutioni[sz](?:e|es|ed|ing)", r"innovative", r"unparalleled", r"vibrant", r"bustling", r"nestled",
    r"meticulous(?:ly)?", r"commendable", r"noteworthy", r"nuanced?", r"myriad", r"plethora", r"interplay",
    r"enduring", r"burgeoning", r"poised", r"landscapes?", r"ecosystems?", r"holistic(?:ally)?",
    r"synerg(?:y|ies|istic)", r"paradigms?", r"ever-(?:evolving|changing)", r"fast-paced", r"palpable",
    r"unspoken", r"amidst", r"solace", r"camaraderie", r"resonat(?:e|es|ed|ing)", r"elucidat(?:e|es|ed|ing)",
    r"illuminat(?:e|es|ing)", r"facilitat(?:e|es|ed|ing)", r"utiliz(?:e|es|ed|ing|ation)",
    r"endeavou?rs?", r"invaluable", r"imperative", r"world-class", r"best-in-class", r"next-generation",
    r"spearhead(?:s|ed|ing)?", r"reimagin(?:e|es|ed|ing)", r"redefin(?:e|es|ed|ing)", r"curated", r"bespoke",
    r"navigat(?:e|es|ing) (?:the )?(?:complexities|challenges|landscape|world)",
]) + r")\b"

CATEGORIES = [
    # (name, patterns)
    ("puffery", rx(
        r"\b(?:stands?|serves?|served) as (?:a|an|the) (?:testament|reminder|symbol|beacon|example|cornerstone|foundation)",
        r"\ba testament to\b",
        r"\b(?:marks?|marking|marked) a (?:pivotal|significant|major|new|key) (?:moment|milestone|chapter|step|turning point)",
        r"\bplays? (?:a|an) (?:key|crucial|vital|pivotal|significant|central|important|critical) role\b",
        r"\b(?:reflects?|reflecting|underscores?|highlights?) (?:the )?(?:broader|growing|increasing|wider) (?:trend|shift|importance|need)",
        r"\b(?:evolving|changing|shifting) landscape\b",
        r"\b(?:has|have) (?:shaped|sparked|generated|fueled|ignited) (?:discussions?|debates?|conversations?)",
        r"\b(?:indelible|lasting) (?:mark|impact|legacy)\b",
        r"\bdeeply rooted\b",
        r"\bat the (?:forefront|cutting edge) of\b",
    )),
    ("vague-source", rx(
        r"\b(?:studies|research|experts|analysts|reports|surveys|data|science|statistics) (?:show|shows|suggest|suggests|say|says|agree|indicate|indicates|confirm|confirms|prove|proves|reveal|reveals)\b",
        r"\b(?:industry|market) (?:leaders|experts|reports|research|analysts)\b",
        r"\bleading (?:\w+ )?(?:companies|brands|organi[sz]ations|experts|businesses|providers|teams|restaurants|retailers|firms|startups|enterprises|universities)\b",
        r"\bmany (?:experts|companies|businesses|organi[sz]ations|teams|people|users|customers|professionals)\b",
        r"\b(?:it is|it's) (?:widely|generally|commonly|often) (?:known|believed|accepted|recognized|agreed)\b",
        r"\baccording to (?:experts|research|studies|many|some)\b",
        r"\b(?:trusted|used|loved) by (?:thousands|millions|hundreds|countless)\b",
        r"\b(?:associated|in connection) with\b",
        r"\b(?:some|many|several) (?:say|argue|believe|suggest)\b",
    )),
    ("announced-meaning", rx(
        r"\b(?:this|that|which|it|these) (?:shows|means|proves|demonstrates|highlights|underscores|illustrates|reveals|reminds us|tells us) (?:that|how|why|us)\b",
        r"\bthe (?:key |real |main |big )?(?:takeaway|lesson|bottom line)\b",
        r"\bthe real (?:question|story|value|magic|power|win|problem|answer|secret)\b",
        r"\bwhat this means\b",
        r"\bultimately,",
        r"\bat (?:its|the) (?:core|heart)\b",
        r"\bin other words\b",
        r"\bthe point is\b",
        r"\bthat's (?:the|what) (?:power|beauty|magic|point) of\b",
        r"\bmake no mistake\b",
    )),
    ("recap", rx(
        r"\b(?:in (?:summary|conclusion|closing|short)|to (?:sum up|summari[sz]e|conclude|recap)|all in all)\b",
        r"(?:^|[.!?]\s+)overall,",
        r"\bkey takeaways?\b",
        r"\bdespite (?:these|its|the|this|their) (?:challenges|limitations|hurdles|setbacks|obstacles)\b",
        r"\blooking ahead\b", r"\bfuture (?:outlook|prospects)\b", r"\b(?:moving|going) forward\b",
    )),
    ("contrast-frame", rx(
        r"\bnot (?:just|only|merely|simply)\b",
        r"\b(?:more|so much more) than just\b",
        r"\b(?:is|are|was|were)n't (?:just|only|merely|simply)\b",
        r"\b(?:it's|this is|that's) not about\b",
        r",\s+not\s+(?!only\b|just\b|to\b|because\b|that\b|if\b|yet\b|even\b|least\b|always\b|all\b|so\b|necessarily\b|including\b|counting\b|surprisingly\b|once\b|much\b|enough\b)(?:a |an |the )?[a-z][\w-]*",
        r"\bno \w+(?: \w+)?[,.]\s+(?:and\s+)?no \w+",
        r"\brather than\b",
    )),
    ("ing-rider", rx(
        r",\s+(?:thereby\s+)?(?:ensuring|highlighting|underscoring|showcasing|emphasizing|reflecting|fostering|enabling|allowing|making|providing|offering|creating|contributing|demonstrating|paving|leaving|giving|helping|reinforcing|solidifying|cementing|signaling|signalling|marking|positioning|empowering|driving|delivering|unlocking|setting)\b",
    )),
    ("copula-avoidance", rx(
        r"\b(?:serves?|served|stands?|acts?) as\b",
        r"\bboast(?:s|ed|ing)?\b",
    )),
    ("triplet", rx(
        r"\b[A-Za-z][\w'-]*(?: [\w'-]+){0,2}, [\w'-]+(?: [\w'-]+){0,2},? (?:and|or) [\w'-]+\b",
    )),
    ("hedge", rx(
        r"\b(?:may|might|could|can) (?:potentially|possibly|help)\b",
        r"\bpotentially\b",
        r"\bseems? to\b",
        r"\barguably\b",
    )),
    ("stock-word", rx(STOCK_WORDS)),
    ("stock-phrase", rx(
        r"\bin today's (?:fast-paced |digital |modern |ever-changing |competitive |rapidly evolving )?(?:world|landscape|age|era|market|economy)\b",
        r"\bunlock(?:ing)? the (?:full )?(?:power|potential|value)\b",
        r"\b(?:take|takes|taking) (?:it|things|your \w+(?: \w+)?) to the next level\b",
        r"\bwhether you're (?:a|an)\b",
        r"\blook no further\b",
        r"\bimagine (?:a world|if you|having|never)\b",
        r"\bpicture this\b",
        r"\blet's (?:dive|delve|jump) in(?:to)?\b",
        r"\b(?:dive|dives|diving) (?:deep |deeper )?into\b",
        r"\bdeep dive\b",
        r"\bat the end of the day\b",
        r"\bit's (?:important|worth|crucial|essential) (?:to note|noting|to remember|to understand|to mention)\b",
        r"\bit (?:should|must) be noted\b",
        r"\b(?:needless to say|it goes without saying)\b",
        r"\b(?:a|the) (?:sense|weight|mix|blend) of\b",
        r"\bhung in the air\b|\bthe air (?:was|is) thick\b",
        r"\ba flicker of\b",
        r"\b(?:rich|diverse) (?:array|range|tapestry|variety) of\b",
        r"\bworld of possibilities\b",
        r"\b(?:designed|built|crafted) with you in mind\b",
        r"\b(?:one-stop|go-to) (?:shop|solution|destination)\b",
        r"\bpeace of mind\b",
        r"\b(?:perfect|ideal) (?:solution|choice|partner) for\b",
        r"\b(?:we're|we are) (?:passionate|committed|dedicated) (?:about|to)\b",
    )),
    ("virtue-word", rx(
        r"\b(?:honest(?:ly)?|genuine(?:ly)?|truly|quietly|thoughtfully|lovingly|effortless(?:ly)?|authentic(?:ally)?|passionate(?:ly)?)\b",
        r"\bcarefully (?:crafted|designed|chosen|selected|curated)\b",
        r"\bsimply\b",
    )),
    ("signpost", rx(
        r"\bin this (?:section|article|post|guide|deck|presentation|email|piece|document|report)\b",
        r"\b(?:below|here),? (?:you'll|we'll|you will|we will) (?:find|see|explore|learn|discover)\b",
        r"\bhere (?:are|is) (?:\d+|three|four|five|six|seven|ten|some|a few) (?:reasons|ways|things|tips|steps|lessons)\b",
        r"\blet's (?:explore|break (?:it|this|that) down|unpack|take a (?:closer )?look)\b",
        r"\bwithout further ado\b",
        r"\bas (?:we've|we have) (?:seen|discussed|explored)\b",
        r"\b(?:as )?mentioned (?:above|earlier|previously)\b",
    )),
    ("hook", rx(
        r"\bhere's the (?:thing|deal|kicker|catch|truth)\b",
        r"\blet that sink in\b", r"\bunpopular opinion\b", r"\bread that again\b", r"\bhot take\b",
        r"\bthe (?:result|answer|catch|best part|kicker|twist|secret)\?",
        r"\b(?:spoiler|plot twist):",
        r"\bbut here's\b",
    )),
    ("email-filler", rx(
        r"\bI hope (?:this|you|your|all)\b[^.]{0,40}\b(?:well|finds|good|great)\b",
        r"\b(?:wanted|want) to (?:reach out|follow up|touch base|circle back|check in)\b",
        r"\bjust (?:circling|following|checking) (?:back|up|in)\b",
        r"\btouch(?:ing)? base\b",
        r"\b(?:feel free|don't hesitate|do not hesitate) to (?:reach out|contact|get in touch|let me know)\b",
        r"\b(?:I'm|we're|I am|we are) (?:so )?(?:excited|thrilled|delighted|pleased|happy) to (?:announce|share|introduce|let you know|tell you)\b",
        r"\bplease find attached\b",
        r"\blooking forward to (?:hearing from you|your (?:reply|response|thoughts))\b",
    )),
    ("residue", rx(
        r"\bcertainly!", r"\bgreat question\b", r"\babsolutely!", r"\bI hope this helps\b", r"\bas an AI\b",
        r"\[(?:company|your|client|product|brand) name\]", r"\bwould you like me to\b", r"\bI'd be happy to\b",
        r"\bhappy to help\b", r"\bas of my (?:last )?(?:knowledge|training)\b", r"\blorem ipsum\b",
    )),
    ("em-dash", rx(r"—|\s–\s|\s--\s")),
    ("exclamation", rx(r"!(?![\[=])")),
    ("emoji", rx("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]", flags=re.RegexFlag(0))),
]

RECAP_HEADINGS = {
    "conclusion", "conclusions", "summary", "in summary", "in conclusion", "key takeaways", "takeaways",
    "final thoughts", "wrapping up", "the bottom line", "recap", "closing thoughts",
}
SMALL_WORDS = {"a", "an", "the", "and", "or", "but", "for", "nor", "of", "on", "in", "to", "at", "by", "with",
               "from", "as", "is", "vs", "via", "per", "into", "over"}
NOMINAL = re.compile(r"\b[a-z]{3,}(?:tion|tions|ment|ments|ness|ity|ities|ance|ances|ence|ences)\b", I)
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
PLACEHOLDER = re.compile(r"\[[^\]\n]{3,80}\](?!\()")
SENT_SPLIT = re.compile(r"(?<=[.!?])[\"”')\]]*\s+")
TWO_FRAGMENT = re.compile(r"^[A-Z][^.!?]{1,40}\.\s+[A-Z][^.!?]{1,40}\.$")
BOLD_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\*\*|__)[^*_]{1,50}?(?:\*\*|__)?\s*:")


def classify_lines(text, is_html):
    """Return [(lineno, raw, clean, kind)] with kind in heading/bullet/prose/blank."""
    out = []
    lines = text.split("\n")
    in_fence = in_script = in_front = False
    if lines and lines[0].strip() == "---":
        in_front = True
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if in_front:
            if i > 1 and s in ("---", "..."):
                in_front = False
            out.append((i, raw, "", "blank"))
            continue
        if not is_html and re.match(r"^(```|~~~)", s):
            in_fence = not in_fence
            out.append((i, raw, "", "blank"))
            continue
        if in_fence:
            out.append((i, raw, "", "blank"))
            continue
        kind = "prose"
        clean = raw
        if is_html:
            low = raw.lower()
            if in_script:
                if re.search(r"</(script|style)>", low):
                    in_script = False
                out.append((i, raw, "", "blank"))
                continue
            if re.search(r"<(script|style)\b", low) and not re.search(r"</(script|style)>", low):
                in_script = True
                out.append((i, raw, "", "blank"))
                continue
            clean = re.sub(r"<(script|style)\b.*?</\1>", " ", clean, flags=I)
            if re.search(r"<h[1-6]\b", low):
                kind = "heading"
            elif re.search(r"<li\b", low):
                kind = "bullet"
            clean = html.unescape(re.sub(r"<[^>]+>", " ", clean))
        else:
            if re.match(r"^\s*#{1,6}\s", raw):
                kind = "heading"
                clean = re.sub(r"^\s*#{1,6}\s+", "", raw)
            elif re.match(r"^\s*(?:[-*+]|\d+[.)])\s", raw):
                kind = "bullet"
            clean = re.sub(r"`[^`]*`", " ", clean)
            clean = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", clean)
            clean = re.sub(r"https?://\S+", " ", clean)
        clean = clean.replace("’", "'").replace("‘", "'")
        clean = re.sub(r"(\*\*|__)", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            kind = "blank"
        out.append((i, raw, clean, kind))
    return out


def snippet(line, start, end, width=110):
    a = max(0, start - 40)
    b = min(len(line), end + 50)
    s = line[a:start] + "»" + line[start:end] + "«" + line[end:b]
    if a > 0:
        s = "…" + s
    if b < len(line):
        s = s + "…"
    return s if len(s) <= width + 20 else s[: width + 20] + "…"


def is_title_case(text):
    words = [w for w in re.findall(r"[A-Za-z][\w'-]*", text)]
    if len(words) < 3 or text.isupper():
        return False
    major = [w for w in words[1:] if w.lower() not in SMALL_WORDS]
    if len(major) < 2:
        return False
    return sum(w[0].isupper() for w in major) / len(major) >= 0.8


def analyze(name, text):
    is_html = name.lower().endswith((".html", ".htm")) or bool(re.match(r"\s*<(!doctype|html|body|div|section|main)", text, I))
    rows = classify_lines(text, is_html)
    hits = {c: [] for c, _ in CATEGORIES}
    for extra in ("title-case", "two-fragment", "bold-bullets", "staircase"):
        hits[extra] = []

    words = 0
    nominal = 0
    for lineno, raw, clean, kind in rows:
        if kind == "blank":
            continue
        words += len(WORD.findall(clean))
        nominal += len(NOMINAL.findall(clean))
        for cat, pats in CATEGORIES:
            for p in pats:
                for m in p.finditer(clean):
                    hits[cat].append({"line": lineno, "match": m.group(0).strip(), "text": snippet(clean, m.start(), m.end())})
        if kind == "heading":
            if is_title_case(clean):
                hits["title-case"].append({"line": lineno, "match": clean, "text": clean})
            if clean.lower().strip(" :.") in RECAP_HEADINGS:
                hits["recap"].append({"line": lineno, "match": clean, "text": "heading: " + clean})
        if kind in ("heading", "prose") and len(WORD.findall(clean)) <= 14 and TWO_FRAGMENT.match(clean):
            hits["two-fragment"].append({"line": lineno, "match": clean, "text": clean})

    bold_rows = [(n, c) for n, raw, c, k in rows if k == "bullet" and BOLD_BULLET.match(raw)]
    if len(bold_rows) >= 3:
        for n, c in bold_rows:
            hits["bold-bullets"].append({"line": n, "match": c[:40], "text": c[:110]})

    # Paragraphs of prose for rhythm and staircases.
    paras, cur = [], []
    for lineno, raw, clean, kind in rows:
        if kind == "prose":
            cur.append((lineno, clean))
        else:
            if cur:
                paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    sent_lengths = []
    one_liners = []
    for p in paras:
        body = " ".join(c for _, c in p)
        sents = [s for s in SENT_SPLIT.split(body) if WORD.search(s)]
        for s in sents:
            sent_lengths.append(len(WORD.findall(s)))
        one_liners.append(len(sents) == 1 and len(WORD.findall(body)) <= 25)
    run_start = None
    for idx, flag in enumerate(one_liners + [False]):
        if flag and run_start is None:
            run_start = idx
        elif not flag and run_start is not None:
            if idx - run_start >= 4:
                first = paras[run_start][0]
                hits["staircase"].append({"line": first[0], "match": f"{idx - run_start} one-sentence paragraphs in a row", "text": first[1][:110]})
            run_start = None

    placeholders = []
    for lineno, raw, clean, kind in rows:
        if kind != "blank":
            for m in PLACEHOLDER.finditer(clean):
                if not re.fullmatch(r"\[(?:company|your|client|product|brand) name\]", m.group(0), I):
                    placeholders.append({"line": lineno, "text": m.group(0)})

    per_k = (lambda n: round(n * 1000 / words, 1)) if words else (lambda n: 0.0)
    metrics = {
        "words": words,
        "sentences": len(sent_lengths),
        "em_dashes": len(hits["em-dash"]),
        "em_dashes_per_1k_words": per_k(len(hits["em-dash"])),
        "stock_words_per_1k_words": per_k(len(hits["stock-word"])),
        "contrast_frames": len(hits["contrast-frame"]),
        "triplets": len(hits["triplet"]),
        "sentence_len_mean": round(statistics.mean(sent_lengths), 1) if sent_lengths else 0,
        "sentence_len_sd": round(statistics.pstdev(sent_lengths), 1) if len(sent_lengths) > 1 else 0,
        "share_sentences_8_to_20_words": round(sum(8 <= n <= 20 for n in sent_lengths) / len(sent_lengths), 2) if sent_lengths else 0,
        "nominalizations_per_100_words": round(nominal * 100 / words, 1) if words else 0,
        "placeholders": len(placeholders),
    }
    hits = {k: v for k, v in hits.items() if v}
    return {
        "file": name,
        "metrics": metrics,
        "flags": hits,
        "flag_count": sum(len(v) for v in hits.values()),
        "placeholders": placeholders,
    }


def print_report(rep, show_all):
    m = rep["metrics"]
    print(f"{rep['file']}: {m['words']} words, {m['sentences']} prose sentences")
    print(f"  em dashes {m['em_dashes']} ({m['em_dashes_per_1k_words']}/1k words) | stock words {m['stock_words_per_1k_words']}/1k"
          f" | sentence length {m['sentence_len_mean']} ± {m['sentence_len_sd']}"
          f" ({int(m['share_sentences_8_to_20_words'] * 100)}% in 8-20)"
          f" | nominalizations {m['nominalizations_per_100_words']}/100 words")
    if not rep["flags"]:
        print("  no flags")
    for cat, items in sorted(rep["flags"].items(), key=lambda kv: -len(kv[1])):
        print(f"  {cat} ({len(items)})")
        shown = items if show_all else items[:8]
        for h in shown:
            print(f"    L{h['line']}: {h['text']}")
        if len(items) > len(shown):
            print(f"    … {len(items) - len(shown)} more (--all)")
    if rep["placeholders"]:
        print(f"  placeholders to fill ({len(rep['placeholders'])}): " + ", ".join(f"L{p['line']} {p['text']}" for p in rep["placeholders"][:12]))
    print(f"  total flags: {rep['flag_count']}")


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    show_all = "--all" in argv
    if not args or "--help" in argv or "-h" in args:
        print((__doc__ or "").strip())
        return 0 if ("--help" in argv or "-h" in args) else 2
    reports = []
    for path in args:
        try:
            if path == "-":
                text, name = sys.stdin.read(), "<stdin>"
            else:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text, name = f.read(), path
        except OSError as e:
            print(f"tells.py: {e}", file=sys.stderr)
            return 2
        reports.append(analyze(name, text))
    if as_json:
        print(json.dumps(reports if len(reports) > 1 else reports[0], ensure_ascii=False, indent=1))
    else:
        for r in reports:
            print_report(r, show_all)
        print("A flag means rethink the sentence, not swap the word. See references/tells.md for what to do per category.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
