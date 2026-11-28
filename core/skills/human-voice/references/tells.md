# Surface tells

What gives model-written non-fiction away at the level of words, sentences and formatting, grouped from strongest to weakest. Each entry says what to do instead. `scripts/tells.py` flags most of these; the category names in brackets match its output.

Evidence grades: **M** measured in a study, **E** editors' or professional writers' observation. Sources are in `evidence.md`. None of the measured studies covered landing pages, slides or business email, so the transfer to those genres is judgment.

How to use this list: find the flagged spans, then rewrite each span with the advice for its category. Professional writers in Chakrabarty et al. (2025) got the best results that way. Asking a model to "make it sound more human" in one pass didn't work, and swapping a word for its synonym just produces the next tell, because overuse is specific to the word, not its neighbors.

## 1. Content: the root of most tells

The Wikipedia editors' explanation is regression to the mean: a specific, unusual fact turns into a generic, positive, important-sounding statement. "Inventor of the first train-coupling device" becomes "a revolutionary titan of industry". The text gets less specific and more exaggerated at the same time. Fix the content and most of the surface tells go with it.

- **Significance puffery** [puffery] (E). "Stands as a testament to", "marks a pivotal moment", "reflects broader trends", "in an evolving landscape", "plays a key role", "has shaped discussions about X, Y and Z". *Instead:* the specific fact that made it notable, or nothing.
- **Vague attribution** [vague-source] (E). "Studies show", "experts agree", "industry reports", "many teams", "leading companies". *Instead:* name the source, the number and the date, or cut the claim.
- **Vague connection** [vague-source] (E). "Associated with", "in connection with" where a direct verb exists. *Instead:* "taught", "built", "sells".
- **Redundant exposition** [announced-meaning] (E). Explaining what the reader can already infer, restating the previous sentence, saying what a section will say. In the writers' study this stayed constant even in the best-rated model paragraphs. *Instead:* delete it and check that nothing was lost.
- **Low density** (E+M). Sentences that carry no information or don't answer the reader's question; the strongest predictors of "slop" labels in Shaib et al. were relevance, density and tone, ahead of any vocabulary. *Test:* delete the sentence. If the reader loses nothing, it stays deleted.
- **Invented specifics** (E). A batch number, a time of day, a round percentage nobody measured, a customer name, a quote, a founding story. This is what models do when told to "be specific" without facts. *Instead:* a `[placeholder]` and a question to the user.

## 2. Sentence shapes

- **Trailing -ing riders** [ing-rider] (M). ", ensuring a smooth start", ", highlighting the need for", ", making it ideal for". GPT-4o used present participial clauses at 5.3 times the human rate. *Instead:* end the sentence. If the rider says something real, give it its own sentence with a subject.
- **Nominalizations** (M, shown as a rate). "The implementation of", "provides an improvement in", "enables the optimization of". 2.1 times the human rate. *Instead:* the verb, with someone doing it: "we implemented", "it improves".
- **Copula avoidance** [copula-avoidance] (E). "Serves as", "stands as", "boasts", "features" in place of "is" and "has". *Instead:* "is", "has". Plain "is" is a human sign.
- **Contrast frames** [contrast-frame] (E). "Not just X, but Y", "X, not Y", "It's not about X, it's about Y", "No X. No Y. Just Z.", and the reverse "Y rather than X". *Instead:* say Y. Keep at most one per piece, where the contrast is real and the reader actually believes X.
- **Triplets and doublets** [triplet] (E, M for doublets). "Fast, secure and reliable"; "innovative and scalable". Phrasal "A and B" pairs ran at 1.9 times the human rate. Three items make thin analysis look complete. *Instead:* the one item that's true and proven, or the real number of items (two, four).
- **Stacked hedges** [hedge] (E). "May potentially help", "can help you", "seems to improve" when there's no doubt. *Instead:* state it at the strength the facts support, and put the one real caveat where it applies.
- **Uniform rhythm** (weak, uncited). Every sentence 8 to 20 words, or every paragraph the same arc. Newer models tuned away from long sentences drift into this. *Instead:* vary on purpose; a long sentence that carries an argument through, then a short one.

## 3. Words

- **The vocabulary cluster** [stock-word] (M). The most over-used words in measured studies: delve, underscore, showcase, tapestry, intricate, pivotal, crucial, robust, foster, bolster, leverage, harness, seamless, elevate, unlock, transformative, unparalleled, multifaceted, meticulous, vibrant, nuanced, interplay, realm, landscape (abstract), testament, potential, findings, amidst, palpable, unspoken, camaraderie. One or two in a page can be coincidence. A cluster is one of the strongest tells. The list churns with each model generation ("delve" has faded since 2025), so the principle matters more than the list. *Instead:* the plain word you'd say out loud ("use", "shows", "important"), or usually just a more specific claim.
- **Stock phrases** [stock-phrase] (E). "In today's fast-paced world", "Unlock the power of", "Whether you're a startup or an enterprise", "Look no further", "Take it to the next level", "Let's dive in", "At the end of the day", "It's worth noting that". *Instead:* delete; start with the content.
- **Literary clichés that leak into copy** [stock-phrase] (M). "A sense of", "the weight of", "a mix of X and Y", "hung in the air", "a flicker of hope". These templates were shared across GPT-4o, Claude 3.5 and Llama. *Instead:* the plain fact.
- **Virtue words about yourself** [virtue-word] (E). Honest, genuinely, truly, simply, quietly, thoughtfully, carefully crafted, effortless. They assert sincerity instead of showing it, and "quietly" and "steady" are among the newest tells. *Instead:* the fact that would make a reader think it.
- **Corporate verbs** [stock-word]. Empower, streamline, revolutionize, reimagine, redefine, spearhead. *Instead:* what actually changes for whom.

## 4. Frames, openings and endings

- **Announced meaning** [announced-meaning] (StoryScope M, writers E). "This shows that", "What this means for you", "The takeaway:", "Ultimately,", "At its core", "The real value is". *Instead:* cut; the evidence before it already made the point. If it didn't, fix the evidence.
- **Recap endings** [recap] (E). "In summary", "In conclusion", "Overall,", "Key takeaways", a "Conclusion" or "Final thoughts" heading on a short piece. *Instead:* stop after the strongest point, or end on the next step.
- **Outline-formula endings** [recap] (E). "Despite these challenges, ... Looking ahead, ..." *Instead:* name the challenge where it matters, and say the plan concretely.
- **Signposting** [signpost] (E). "In this section", "Below you'll find", "Here are 5 reasons", "Let's explore", "Without further ado". *Instead:* just give the reasons.
- **Hook formulas** [hook] (E). "Here's the thing:", "Let that sink in.", "Unpopular opinion:", "The result?", "The best part?". *Instead:* lead with the actual claim.
- **Email warm-ups** [email-filler] (E). "I hope this email finds you well", "I wanted to reach out", "Just circling back", "Don't hesitate to reach out", "I'm excited to share". *Instead:* the point in the first sentence.

## 5. Punctuation and formatting

- **Em dashes** [em-dash] (E, and specific to Claude). A study cited by the Wikipedia guide (July 2026) found Claude was the only current model using more em dashes than professional writers. *Instead:* periods and commas for most, parentheses for an aside, a colon only where it introduces something. Don't convert every dash into a colon or semicolon; that keeps the same rhythm.
- **Exclamation marks in body copy** [exclamation]. *Instead:* none, or one where someone would actually exclaim.
- **Emoji in headings and bullets** [emoji] (E). *Instead:* remove unless the brand voice really uses them.
- **Title Case Headings** [title-case] (E). *Instead:* sentence case, unless the house style says otherwise.
- **Bold-term bullet lists** [bold-bullets] (E). "**Speed:** ... **Security:** ... **Scale:** ..." on every list. *Instead:* plain bullets, a table, or prose; bold only what a scanning reader must not miss.
- **Two-fragment lines** [two-fragment] (E, from taste-skill's copy tells). "Short menu. Long list of regulars." Once can work; on every heading it's a template.
- **One-line paragraph staircases** [staircase] (E). Four or more one-sentence paragraphs in a row, LinkedIn style. *Instead:* paragraphs that hold an idea.
- **Chatbot residue** [residue] (E). "Certainly!", "Great question", "I hope this helps", "Would you like me to", "[Company Name]". *Instead:* delete.

## Not tells: leave these alone

From the Wikipedia guide's list of indicators that don't work: perfect grammar, a formal register where the context is formal, transition words on their own ("Additionally", "However"), a single em dash, ordinary wordy phrases ("in order to", "the fact that"). Signs of human writing worth keeping: plain "is" and "has", plain verbs ("used", not "utilized"), definite claims ("the first", "the only"), honest qualifiers where there is real doubt ("probably", "tends to").
