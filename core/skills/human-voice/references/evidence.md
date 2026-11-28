# Evidence

Where the rules in `SKILL.md` and `tells.md` come from, and how far to trust them. Read this when a rule seems wrong for a piece, or when the user asks why.

## StoryScope (the structural rules)

Russell, Rajendhran, Pham, Iyyer and Wieting, "StoryScope: Investigating idiosyncrasies in AI fiction", arXiv 2604.03136 (v6, Aug 2026, not peer reviewed). Code: github.com/jenna-russell/storyscope.

**Setup.** 10,272 short stories from published anthologies (Books3), with a writing prompt reverse-engineered from each one. Five models (Claude Sonnet 4.6, GPT-5.4, Gemini 3 Flash, DeepSeek V3.2, Kimi K2.5) wrote a story from each prompt, giving 61,608 stories of about 4,750 words. An LLM pipeline found 304 multiple-choice narrative features; Gemini 3 Flash scored every story on them; XGBoost and SHAP did the rest.

**Headline results.**
- Narrative features with every style feature removed: 93.2% macro-F1 for human vs AI, 68.4% for naming which of six sources wrote it.
- Surface editing of AI artifacts (cliché, redundant exposition, purple prose) barely changed detection: 95.5 to 93.9 macro-F1.
- The five AI models sit in one tight cluster; human stories are more spread out. Within a prompt, the human story was the most unusual of the six 57.8% of the time.

**The numbers behind the rules** (human vs AI average, % of stories):

| Rule in SKILL.md | Finding |
|---|---|
| Don't announce the meaning | Narrator states the theme: 52% vs 77%. Dialogue as philosophical debate: 34% vs 59%. Thematic explicitness 3.28 vs 3.94 on a 1-5 scale |
| Keep one real complication | No subplots: 57% vs 79%. Protagonist framed as morally ambivalent: 59% vs 38%. Resolution by internal acceptance: 27% vs 47% |
| Start where it's interesting | Humans use more time jumps, flashbacks and nonlinear framing to delay a reveal; AI tells it in order |
| Say feelings plainly | Emotion through bodily sensation: 38% vs 81%. Named emotion: 29% vs 8%. Smell imagery: 57% vs 82%. Setting mirrors mood more in AI |
| Name things | Explicit named references to real works and people: 47% vs 24%. Vague allusion: 50% vs 72% |
| Talk to someone | Direct reader address: 0.28 vs 0.07, fourth-wall permeability: 0.67 vs 0.39 (means on ordinal scales in Table 16; the paper's prose calls them percentages, which they aren't) |
| Build to a peak (Claude) | Claude's fingerprint: the flattest event escalation and most uniform voice of all sources, "reverent" toward convention (62% vs 39-56% for the others), favors epilogues and quiet endings |
| Notice the default | AI stories cluster; human stories are rarer in feature space (mean rarity percentile 0.71 vs 0.49) |

**Limits to keep in mind.**
- It's fiction. Translating "states the theme" into "the sentence that explains the previous sentence" for a landing page is judgment, not a finding.
- The setup isn't perfectly parallel. The models wrote from a summary that kept the story's "thematic direction", under the system prompt "You are a creative writing expert who generates rich, detailed stories." Both plausibly push toward explicit themes and sensory density. The practical lesson holds either way: models do this when nudged even slightly.
- The human side is published, edited fiction across many decades. Some human traits (reader address) are partly period conventions.
- Three models wrote stories of about 3,000 words; Claude and GPT wrote about 6,500. Some per-model fingerprints may reflect length.

## Surface tells

- **Wikipedia: Signs of AI writing** (WikiProject AI Cleanup, read 2026-11-28). Editors' field guide. Source of the regression-to-the-mean explanation, puffery, -ing analysis, vague attribution, copula avoidance, negative parallelism, rule of three, formatting tells, the era-by-era word lists, the Claude em-dash finding it cites (July 2026), and the list of indicators that don't work. It warns that treating the signs as the problem can hide the real one: unsupported or vague content.
- **Reinhart et al. 2025, PNAS 122(8), "Do LLMs write like humans?"** Measured on about 8,300 texts across eight registers with Biber's 66 features. GPT-4o vs human: present participial clauses 5.3x, nominalizations 2.1x, "that" clauses as subject 2.6x, phrasal coordination 1.9x, agentless passive about 0.5x. Words at 95-162x the human rate: camaraderie, tapestry, intricate, underscore, unspoken, amidst, palpable, solace. Instruction tuning, not model size, creates the gap, and the dense noun-heavy style persists even when the model is asked for informal speech.
- **Kobak et al. 2025, Science Advances, "Delving into LLM-assisted writing..."** 15M PubMed abstracts. 379 excess style words in 2024, 66% verbs and 14% adjectives. Highest ratios: delves 28x, underscores 13.8x, showcasing 10.7x. Largest gaps among common words: potential, findings, crucial.
- **Chakrabarty, Laban and Wu, CHI 2025, "Can AI writing be salvaged?"** 18 professional writers, 1,057 model paragraphs, 8,035 edits (fiction and creative non-fiction). Seven problem categories: awkward word choice (28% of edits), poor sentence structure (20%), redundant exposition (18%), cliché (17%), purple prose, lack of specificity, tense inconsistency. Redundant exposition and lack of specificity stayed even in the best paragraphs. Detecting spans by category and then rewriting each with category-specific guidance beat raw model text; one-pass self-editing on long text did not work. Human edits still won.
- **Shaib et al., "Measuring AI Slop in Text"** (arXiv 2509.19163, COLM 2026). Expert taxonomy tested on news and QA answers. The strongest predictors of "slop" were relevance, information density and tone, not vocabulary. Agreement was moderate, so slop is partly subjective.
- **taste-skill's copy layer** (installed plugin, `copy-voice.md` and `copy-tells.md`). Practitioner notes on the second generation of tells, the ones models produce once the old words are suppressed: one warm, wry house voice for every client, invented specifics, two-fragment headings, contrast frames, virtue words, polished testimonials. Not a study, but it matches what Claude produces when asked to sound human without guidance.
