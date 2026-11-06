---
name: teach
description: "Personal tutor that teaches a topic for understanding, not memorized facts: probes what Arlan already knows with quizzes, plans the route as a dependency map of core truths, then teaches node by node with a quiz check after each, and builds the lesson as a private Artifact page with the right visual for each idea (inline SVG diagram, anatomy figure, three.js 3D model from a GLB, or a short video/GIF made by the video-maker agent). Use whenever the user says teach me, explain from scratch or from first principles, I don't get / don't understand X, help me learn X, walk me through how X works, or wants to really understand a concept, algorithm, mechanism, math or tool - in English or Russian. Not for a one-off factual answer (just answer it), for a figure or video wanted as the deliverable itself (anatomy, hyperframes via video-maker), or for diagnosing an RL run (rl-advisor; teach still loads rl-advisor for RL subject matter)."
---

# Teach

Goal: understanding. A few core truths that many facts can be derived from, connected into a dependency graph, so the learner can rebuild a fact instead of recalling it. The felt goal is the click.

The method (probe, plan, teach; truths first; make every step discoverable) is adapted from the `teach` skill in github.com/amosblomqvist/learn. This version runs in Claude Code, keeps the lesson on an Artifact page, and hands heavy visuals to subagents.

This skill runs in the **main session**: quizzes need `AskUserQuestion` with the learner, and the dialogue is the lesson. Everything heavy goes out with a self-contained brief (see Delegation).

## Two principles

1. **Unconditional truths first.** Open with facts the learner can hold without caveats: real definitions, universal statements ("every X is Y"), conservation laws, invariants. Confirm each one before building on it. If a fact needs "usually" or "except when", it is not a root; push it down the graph.
2. **"How could I have discovered this?"** Every step answers a question the previous step raised. Show the problem that forces the idea before the idea. Socratic (ask, let the learner take the step) for derivable topics like math and algorithms; expository (narrate the discovery) for tools, conventions and history, or when answers get short and the learner is tired. Switch when asked.

## Learner profile

`~/.claude/teach/learner.md` holds what Arlan has already learned with this skill: topics with date and lesson URL, misconceptions found, preferred mode (Socratic or expository), language. Read it before the probe so known ground is skipped. Update it at the end of every lesson. If it doesn't exist, create it at the end of the first lesson.

## Process

### 1. Probe

Find the edge of what the learner knows before teaching anything.

- First `AskUserQuestion` call: the goal (why this topic, and the depth: intuition, working knowledge, or able to derive and implement it) plus 1-3 graded questions.
- For each strand of the topic, find a **floor** (something they get right) and a **ceiling** (something they get wrong). All right means escalate; don't start teaching until every strand has a miss or the top level is reached.
- When a wrong answer shows up, find out which misconception produced it before moving on; it decides where teaching starts.
- Two or three probe rounds are usually enough. Don't turn the probe into the lesson.

### 2. Plan

- **Research in one batch.** List every claim in the plan you are not fully sure of, then check them together: a few WebSearch calls, or one `general-purpose` agent with the list that returns a verdict and source per claim. For a topic about the user's own code, use `Explore` or `deep-reasoner`. For RL subject matter, load `rl-advisor` and follow it. Never fire one agent per sentence mid-lesson.
- **Build the dependency map**: 4-10 nodes, roots are the unconditional truths, each edge means "you need A to see B". Stress-test the roots: could the learner accept each at face value?
- **Pick a visual per node** from the ladder below, cheapest that will make it click.
- **Show the plan in the terminal**: the approach in 3-5 lines, the map as an indented text tree (the terminal doesn't render Mermaid), and which nodes get a heavy visual (anatomy figure, 3D model, video). Ask for approval with `AskUserQuestion` (approve / adjust). Approval of the plan is consent for the heavy visuals it lists.
- After approval, start the lesson page (see Lesson page) with the map and an empty section per node, and launch the heavy visuals in the background right away so they are ready by the time their node comes up.

### 3. Teach

For each node, in map order:

1. **Motivate**: the question or failure that makes this node necessary.
2. **Establish**: state it plainly; derive it if it is derivable. Show the visual here.
3. **Connect**: tie it to the nodes before it and to something the learner already knew from the probe.
4. **Check**: one quiz question (rules below) or an "explain it back in your own words" prompt for deeper nodes. A miss means re-teach from the misconception it shows, with a different angle or the next visual up the ladder, not the same words again.

Then write the node's section into the lesson page and republish. Keep the terminal conversational; the page holds the condensed, polished version.

### 4. Close

- Recap the core truths and how the rest follows from them.
- A final `AskUserQuestion` round of 2-3 questions mixing nodes.
- Finish the page (summary at top, all sections filled), republish, update `learner.md`, end with the link.

## Accuracy

- If you are less than sure of a fact, check it before saying it (fold it into the Plan batch when you can). Never fill a gap from memory.
- When you find you said something wrong, correct it openly in the terminal and on the page.

## Quiz rules

`AskUserQuestion` takes 1-4 questions per call and 2-4 options per question, and adds "Other" by itself so the learner can type a free answer.

- **No "(Recommended)" label** and no "recommended first" ordering; the tool's default convention would leak the answer.
- Vary where the correct option sits.
- Options are bare claims of similar length and form: no justification attached, no hedging only on the wrong ones, no bold or emphasis on one option.
- Distractors are real misconceptions, ideally ones seen in the probe, never filler.
- Don't use `preview` to hint, and keep the header neutral ("Check", "Probe").
- After the answer, say why the right option is right and which misconception each wrong option holds.

## Visual ladder

Pick the cheapest level that will make the idea click; go up only when the idea is spatial or changes over time, or when a lower level didn't land. Details, embedding mechanics and brief templates are in `references/visuals.md`.

| Level | Use for | Who builds it |
|---|---|---|
| 1. Text or ASCII sketch | Most nodes; quick structure in the terminal | Main session |
| 2. Inline SVG diagram on the page | Structure, flows, plots, labeled parts | Main session, following the `artifact-diagramming` skill |
| 3. `anatomy` figure | How a mechanism works, shown as a physical object | `general-purpose` agent that loads the `anatomy` skill |
| 4. 3D model in three.js | Shape, assembly, frames, rotations, spatial relations | Simple geometry: built in the page. A real part: `general-purpose` agent with the text-to-cad `cad` skill exports a GLB, or an existing GLB from the repo |
| 5. Video or GIF | Processes over time, motion, sequences | Always the `video-maker` agent (HyperFrames). Never run HyperFrames in the main session |

## Lesson page

One private Artifact page per lesson, built in the scratchpad directory at `teach/<slug>/index.html` with its media under `teach/<slug>/media/`. If the system prompt lists no scratchpad, build it at `~/.claude/teach/lessons/<slug>/index.html` and embed media as `data:` URIs: the Artifact tool only takes `files` from the working directory or the scratchpad.

- Before writing the first page of a lesson, call the Artifact tool with `action: "quickstart"`, `intent: "other"`, and follow what it returns (it covers the page design guidance).
- Structure: title, the learner's goal, the dependency map (inline SVG), one section per node (motivation, statement, visual, a "check yourself" question with the answer in a `<details>` reveal), and a summary of core truths at the top once the lesson is done.
- Math: MathJax 3 SVG output from cdnjs, pinned (`https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.min.js`). It needs no external stylesheet, which the Artifact contract forbids. MathJax 3 only reads `\(...\)` as inline math by default, so put `<script>window.MathJax = { tex: { inlineMath: [['$','$'], ['\\(','\\)']] } };</script>` before the tex-svg script tag; display math is `$$...$$`.
- Publish the skeleton after the plan is approved, then republish the same `file_path` as nodes are taught (small changes as `edits` on the publish call). Media go out through `files` (see `references/visuals.md`).
- To continue an old lesson in a new session, find it with `action: "list"` or the URL in `learner.md`, read it with `action: "read"`, and build on the saved file it names.

## Delegation

The main session keeps the dialogue, the quizzes, the plan and the page. Everything below goes out with a self-contained brief (templates in `references/visuals.md`), launched in the background as soon as the plan is approved:

- Fact checks: one `general-purpose` agent per batch, or direct WebSearch for two or three claims.
- `anatomy` figures: `general-purpose` agent that loads the `anatomy` skill.
- CAD models to GLB: `general-purpose` agent that loads the text-to-cad `cad` skill.
- Video and GIF: `video-maker` agent.

Review what comes back (look at the snapshot or frames) before it goes on the page.

## Language

Teach in the language the learner asks in (English or Russian); keep technical terms in English where that is how they are used.
