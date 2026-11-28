---
name: human-voice
description: "Writes or rewrites text so it reads as if a person wrote it, not default AI: slide and deck text, website and landing-page copy, emails, posts, docs, reports and READMEs. Works on structure first (the stated moral, the tidy single-track order, vague references, performed feelings, flat intensity, template shapes), then on the surface (stock words, em dashes, triplets, 'not X but Y', invented specifics), and never invents facts to sound specific. Use it only when the user asks: 'make this sound human', 'less AI', 'de-AI this', 'this sounds like ChatGPT', 'humanize', 'write it like a person would', 'make it natural, not robotic', or names the skill. Not for code, commit messages or ordinary chat replies. When a whole website is being built with taste-skill, its copy layer leads and this skill adds to it."
---

# Human voice

Default model writing has a recognizable shape. Readers feel it before they can name it, and they stop trusting the text. The shape sits at two levels:

- **Structure:** what the text says, in what order, and how much it explains. A large fiction study (StoryScope, arXiv 2604.03136) separated human from AI stories at 93% macro-F1 *with every style feature removed*, and light surface editing barely moved that number (95.5 to 93.9). Fixing words alone leaves the giveaway in place.
- **Surface:** stock words, rhythm, punctuation and formatting habits. These are the tells people know, and the ones that come back in new forms when you swap them out.

So work in that order: facts, then structure, then surface. The goal is text a reader finds specific and trustworthy. AI-detector scores are not the target. Detectors measure token statistics, and chasing them produces strange prose.

The evidence behind each rule, with numbers and caveats, is in `references/evidence.md`. The surface list is `references/tells.md`. Read `references/voice.md` first: if it holds the user's own voice notes, they win over the defaults here.

## The work, in order

### 1. Facts before sentences

Collect the concrete material first, as a short fact sheet in your head or scratch file: numbers with units and dates, names of products, customers, people and places, what actually happened, what the thing costs, what it doesn't do. Take it from the user's text, the conversation and the project files.

Specifics are the strongest single difference. Human authors named real works and people twice as often as models did (47% vs 24% of stories), and models leaned on vague allusion (72% vs 50%). In non-fiction the same gap shows up as "leading companies", "studies show" and "a range of solutions".

**Never invent specifics to sound human.** No made-up customers, quotes, metrics, dates, batch numbers, minute-of-the-morning details or personal anecdotes. Invented detail is the newest tell, and it is false. When the text needs a fact you don't have, write a visible placeholder like `[number of pilots signed]` and list it for the user, or ask one batch of questions before drafting if the gaps are central.

### 2. One reader, one point

Decide who reads this and the one thing they should know, believe or do afterwards. Write that point down in a sentence. If you can't, the text isn't ready; ask the user or say what's missing.

### 3. Shape: notice the default, then choose

Models converge. In StoryScope the five models from different vendors landed in one tight cluster, and the human stories were spread wider and rarer. Your first idea for the shape is the shared one: three bullets, problem-solution-benefits, hero plus three feature cards, intro-body-conclusion, a closing summary.

For the opening, the overall order and the ending, name the default to yourself, then ask whether this content wants something else. Usually the answer is a different order:

- **Start where it's interesting.** Human writers open at the funeral and work backwards; models tell it from the first clue to the reveal. Lead with the result, the surprising number, or the problem in the reader's own words. Use chronological order only when time is the point.
- **Let it be uneven.** Some sections short, some long, some cut because they have nothing true to say. Perfect evenness (every card the same length, every paragraph the same arc) reads as generated.
- **Build to a peak.** Put the strongest point where it lands hardest, and let the intensity rise toward it. Claude's specific fingerprint in the study was the flattest escalation of any source, the most uniform voice, a reverence for convention, and quiet epilogue endings. Push against those four on purpose.
- **Stop when it's done.** No recap, no "In summary", no closing paragraph that states the lesson.

### 4. Draft with the structural rules

**Don't announce the meaning.** AI narrators stated the story's theme in 77% of stories vs 52% for humans, and dialogue turned into philosophical debate in 59% vs 34%. The non-fiction version is the sentence that explains the previous sentence: "This shows that...", "The takeaway:", "Ultimately, it's about...", "What this means for you is...". Let the evidence carry the point and cut the explainer. A claim is fine, and in slide titles it's good: "Inspection cost fell from $410 to $95 per km" is a claim, "Efficiency is the future of inspection" is a moral.

**Keep one real complication.** Models resolve everything: 79% of AI stories had no subplot (humans 57%), and protagonists were framed as morally clear far more often. In non-fiction, say what it doesn't do, who it isn't for, what it costs, what went wrong, what you're unsure of. Use the user's facts for this; don't manufacture a flaw.

**Say feelings and facts plainly.** Models perform emotion through the body (81% of AI stories vs 38%), lean on smell and texture, and make the setting mirror the mood. Humans just say "she was afraid" (29% vs 8%). In copy this is "Imagine the feeling of...", "Picture this:", sensory filler and metaphors where a flat statement works better. Write "it's slow on large files", not "it crawls under heavy loads".

**Name things.** Products, people, places, versions, sources. Replace "many teams" with the number of teams, or cut it. Name the tool you replaced, the city, the month.

**Talk to someone.** Human authors addressed the reader directly about four times as often as the models and broke the fourth wall more. In copy, emails and posts, write to one person: "you", a direct question you actually want answered, a parenthetical aside. Write as if someone is reading.

**Commit where the facts allow.** Stacked hedges ("may help", "can potentially", "in many cases") are their own tell. State what you know at the strength you know it, and put the one real caveat where it applies.

**Use each device once.** A contrast frame ("X, not Y"), a triplet, a two-fragment heading ("Short menu. Long list of regulars."), a rhetorical question, a colon reveal ("The result? ..."), a one-line paragraph for punch: any of these can be good, once, where it lands hardest. Repeated, they are the template showing through.

### 5. Surface pass

Read `references/tells.md` and check the draft against it. Then run the checker on the draft:

```bash
python3 <skill-dir>/scripts/tells.py draft.md          # or several files, or - for stdin
```

It flags stock words and phrases, em dashes, contrast frames, -ing riders, announced meaning, vague attribution, recap endings and similar patterns, with line numbers. **A flag means rethink the sentence, not swap the word.** A synonym for a stock word is the next stock word, and a colon in place of every em dash is the same rhythm. Some flags will be fine in context (a literal "landscape" photo, a quoted customer); leave those.

### 6. Read it as the reader

Before handing it over, read it once as the person it's for:

- Could a competitor paste their name over yours and the text still be true? Then it lacks specifics.
- Is there a sentence nobody would say out loud to a colleague across a table? Rewrite it as said.
- Does the strongest point come first or at the peak, and does the text stop after it?
- Is every number, name and quote from the facts, with gaps shown as placeholders?

## Rewriting someone's text

This is the common case: the user hands over a draft and asks to make it sound human.

1. Read all of it and pull out its fact sheet: every concrete number, name, claim and promise. Notice which parts are filler with no fact under them.
2. Find the point and the reader. Often the point is buried in the last paragraph; move it up.
3. Restructure before rewording: cut the announcements and the recap, merge or drop sections with nothing true in them, put the strongest material at the peak.
4. Rewrite sentences with the rules above. Keep the facts, the meaning, technical terms, product names and any of the user's own phrases that already sound like a person.
5. Keep the format they gave (slide-by-slide markdown, HTML, plain email) unless they asked to change it.
6. Hand back the rewritten text first. Then at most five short bullets on the main changes, and the list of placeholders the user needs to fill. Don't lecture about AI tells.

## Writing from scratch

Same order: gather facts (ask one batch of questions if the central ones are missing, otherwise use placeholders), decide reader and point, choose the shape on purpose, draft, run the surface pass, read as the reader. Then return the text plus the placeholder list.

## Formats

### Presentations and slide text

- **Titles are claims.** Each slide title is that slide's point as a full sentence with its number: "Utilities spend $410 per km on helicopter inspection". Not a topic label ("Market"), not a moral.
- **The body is evidence,** not a paraphrase of the title: a number, a chart description, a photo, a named quote, a short table. Zero to three bullets; often none.
- **Speaker notes are spoken.** Contractions, short sentences, how you'd say it to one person in the room, including the line that gets you to the next slide.
- **Arc:** open on the problem as a concrete case or number, not an agenda. Build toward the strongest slide. Include one honest risk and what you're doing about it. End on the ask or the decision you need, not a summary slide that repeats the deck.
- **Vary the slides.** A grid of icons with three-word labels on every slide is the template showing.

### Websites and landing pages

- If the whole page is being built with taste-skill, follow its copy layer (`copy.md`, `copy-voice.md`, `copy-tells.md`) and use this skill as a second check. Otherwise this section leads.
- **Headline:** what it is and who it's for, in words a buyer would use. A reader should know in five seconds whether it's for them.
- **Each section answers a question the buyer actually has:** what it does, how it works, what it costs, what it doesn't do, who's behind it, how to start. Drop sections that answer nothing.
- **Proof is real or absent.** Named customers and numbers with dates, from the facts. If there are none yet, leave the section out or leave a placeholder; three polished invented testimonials are worse than none.
- **The call to action says what happens next:** "Book a 20-minute demo", "See pricing", not "Get started today!".

### Emails and messages

- The first sentence is the point or the ask. No warm-up ("I hope this finds you well", "I wanted to reach out", "Just circling back").
- One ask, with the date or decision you need.
- Bad news early and plain, followed by what you're doing about it.
- As short as the content allows. Sign off with a name or "Thanks,".

### Posts and articles

- No hook formulas ("Here's the thing:", "Unpopular opinion:", "Let that sink in."), no staircase of one-line paragraphs, no emoji bullets, few or no hashtags.
- One story or one argument, carried by a detail only the author knows. Get it from the user; don't invent it.
- End when the point is made. Ask a question only if you want answers.

### Docs, reports and READMEs

- Conclusion first, then the evidence for it.
- Numbers carry units, dates and sources.
- Headings name the content ("Why the battery dies at -20 °C"), not the genre ("Overview", "Key Insights").
- Lists and tables are fine where the reader scans. Human doesn't mean unstructured.

## Over-correction

The rules above produce their own failure modes when pushed. Watch for these:

- **Fake casual.** Forced slang, typos, "tbh", lowercase everything, trailing ellipses. Human means specific and direct, not sloppy. Use a casual register only when the voice file or the context calls for it.
- **The house voice.** Warm, wry, modest, a little literary, a dry joke closing each paragraph, the same for every client. Match the register to the subject and the audience instead: a utility procurement deck and a café menu should not sound alike.
- **Twin devices.** "Instead of Y, X" for "X, not Y", "No forms. No calls. No waiting." for a triplet, colons and semicolons for em dashes. The count matters more than the spelling.
- **All punch.** Strings of short fragments are as uniform as strings of long sentences. Vary the length: some long sentences that carry an argument through, some short ones.
- **Invented texture.** A personal story, a customer name, a precise time or a round percentage added because it sounds lived-in. If it isn't in the facts, it's a placeholder.
- **Stripped structure.** Removing every list and heading from a spec or pricing page to look less generated. Keep structure that helps the reader find things.

## Reference files

- `references/voice.md`: the user's own voice notes. Read it first; if filled in, it overrides the generic defaults.
- `references/tells.md`: the surface tells, grouped, with the sources and what to do instead.
- `references/evidence.md`: what StoryScope and the other studies found, the numbers behind the rules, and the limits of that evidence.
- `scripts/tells.py`: the surface checker (stdlib Python, `python3 tells.py FILE... [--json]`).
