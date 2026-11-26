---
name: rl-advisor
description: "RL and imitation-learning advisor and lab notebook, grounded in Sutton and Barto (2nd ed.) and the deep-RL / robot-learning literature. Use when the user asks why a run behaves as it does (plateau, collapse, action chatter, Q overestimation, works-in-sim-only), what a term or algorithm means or which to pick (TD, GAE, deadly triad, SAC, PPO, DAgger, BPTT), how to set gamma, replay, a reward, observation, DR or curriculum, or whether a result is real (seeds, CIs, best-of-N picks); and when they start, stop, sweep, compare or finish a training run, ask what was tried before or which run was best, are about to change a lever, reward term or hyperparameter, or mention a run log, decision ledger or ledger row, run manifest, gate file, TensorBoard/W&B run or sim-to-real test, even without saying 'RL'. Not for writing env code (isaac)."
---

# RL advisor

Two jobs that meet in one conversation. **Advise**: why a run behaves as it does, which algorithm, term or
hyperparameter is right, whether a result is real, what the book or the field says. **Record**: the
pre-registration before a run and the verdict after it. Advice usually ends in the smallest confirming
experiment, and that experiment is what the record step writes down. The authority order is what the project
itself measured, then the literature since the book (`references/deep-rl.md`), then Sutton & Barto
(`references/sutton-barto.md`). Env code belongs to the `isaac` skill, which is installed only in the projects
that use it.

## First: find the project's record

Project facts come from the project, not from this skill or from memory: a digest copied into a skill goes
stale the first time the training changes. Each project keeps its own record, in up to two parts:

- the **ledger** holds the moving state: one row per run, lever or campaign, with its verdict;
- the **digest** holds the durable facts: structure, locked hyperparameters, method, closed results, and how a
  run is recorded there. A row ID in a digest is a pointer; read the row for the current verdict.

Look for them once per project, in this order:

1. The repo's `CLAUDE.md`: an `## Experiments` section (`log:`, `run-id:`, `runs:` as host:path, `metric:`,
   `eval:`, `framework:`), or a document map naming the status, evidence or digest file.
2. `grep -rl 'Decision ledger' --include='*.md' .` for a ledger, and `ls` the directory it sits in for a digest
   beside it (`*DIGEST*`, `*PRECEDENTS*`, `EVIDENCE.md`). Example: aquila keeps its ledger in `verro/STATUS.md`
   (`## Decision ledger`, one `Lnn` row each) with the full rows in `verro/EVIDENCE.md` §9, its digest in
   `verro/RL_DIGEST.md` (§13 is its record step) and its past precedents in `verro/RL_PRECEDENTS.md`.
3. No record at all: say so, answer from theory and the literature, and offer to start one at
   `experiments/LOG.md` (in a monorepo, next to the training package) in the template of
   `references/isaac-lab-log.md`. Run `git check-ignore -q <path>` first and use `docs/EXPERIMENTS.md` if it is
   ignored; if `CLAUDE.md` keeps a doc-ownership map, ask before creating the file and add it to the map in the
   same change; then offer an `## Experiments` section pointing at it. A project without a digest does not need
   one to start; propose one only when the same durable facts keep being re-derived.

A digest carries the date it was last checked. When it is older than a change the ledger or `git log` shows
(a new recipe, a renamed flag), trust the ledger and the code and say the digest needs a refresh.

Then check whether the question was already answered: a lever verdict, a probe, a closed track, the last time
this term or flag was touched (the record, `git log -S'<flag>'`, the comments beside the term). Repeat a closed
experiment only when the user says what changed.

## Advise

1. **Open the reference the question needs** (table below) rather than quoting an equation, a section number
   or a measured number from memory; the digests exist so that citations are exact.
2. **Classify the question on the book's axes** before reaching for an algorithm name: prediction or control;
   on-policy or off-policy; tabular or function approximation; sample (MC) or bootstrapped (TD) target, and how
   deep (n, λ); model-free or model-based; learning from reward or from demonstrations; a question about the
   estimator or about the experiment (seeds, selection, CIs). Most confusion is a mismatch between axes: an
   off-policy correction on an on-policy loop, a bootstrapped target from a critic that cannot see the state, a
   Monte Carlo verdict on two samples.
3. **Cite so the reader can check**: repo code as `path:symbol` after re-grepping (line numbers drift), the book
   as chapter.section, a paper as author year venue, the project's record by ledger row ID. A number not read in
   the repo or a source is marked "(not measured here)" or "(unverified)", because a plausible invented number is
   worse than none.

| question | read first |
|---|---|
| what a term or algorithm means, why it works, a reading plan | `references/sutton-barto.md` (chapter digest, reading paths, book → practice map) |
| which modern algorithm or trick, what the paper found, what breaks it | `references/deep-rl.md` |
| what this project does and measured | the project's digest and ledger (First, above) |
| a run that misbehaves | `references/diagnostics.md` (symptom → hypotheses → separating test) |
| is this result real; how many seeds; a best-of-N claim | `references/diagnostics.md` §6 + `scripts/compare_arms.py` |
| recording an Isaac Lab run, or a repo without a ledger | `references/isaac-lab-log.md` + `scripts/rl_log_entry.py` |

Size the answer to the decision: lead with the answer, give the mechanism with its citation, say what the
project measured (a result from another project is an analogy and is labelled one), and when a change is on
the table end with the smallest experiment that would confirm it and offer to write it down as the
pre-registration.

## Record

A run gets two writes: a start note before launch and a verdict after it. Whatever the format, these fields:

- **Before**: Base (the run or row it differs from), Changed (the one variable, as config path old → new, or the
  commit for a code change), Code (repo@sha, `-dirty` if `git status --porcelain` is not empty, branch), Command
  (exact, with every env var the launcher reads; secrets redacted), Inputs (init checkpoint, dataset, teacher
  bank, with a sha or the run that produced it), Seeds, and the gate: task metric, bar, noise floor, kill rule,
  expected effect.
- **After**: Result (the task metric with its protocol: N episodes or frames, which checkpoint and how it was
  picked, eval seed, sd; wall time and GPU), Verdict (keep / discard / inconclusive, one sentence why), Next (the
  single next change).

Write in the record's own format: a project with a ledger says in its `CLAUDE.md` or digest where plans and
results go and how a row is formed (aquila: `verro/RL_DIGEST.md` §13), and that wins over anything here. For
Isaac Lab or a repo without a ledger, `references/isaac-lab-log.md` has the entry template, run-id naming, the
`params/env.yaml` dump and the Changed check, and `scripts/rl_log_entry.py` pre-fills the entry from a run dir.

An entry is open until it has a Verdict, then frozen: a correction is a new entry or row (`Base: <id>
(correction)`, or the project's supersession note), so the history of what was believed stays readable. Until
a number arrives, write `Result: pending (on <host>:<path>)`. To summarise, give a table of id | changed | task
metric | verdict from the record, then a short read of the trend.

## Rules

The methodology the verdicts rest on; `references/diagnostics.md` explains each.

- **One variable per run**, unless it is a declared sweep (one entry with a sub-table). Every undeclared
  difference between base and new run goes on a `Confounded:` line, and the verdict then judges the bundle. A
  reward-formula change in code is the one variable and cites its commit; a stack bump (simulator, RL library,
  torch, driver) is a run of its own.
- **Judge by the task metric**, a quantity independent of reward weights (success rate, tracking error, frames
  below a fixed gate, gate return under a fixed eval reward), not training return when the reward, the dataset or
  the env differs between arms. A run closed without the task metric is inconclusive, and Next is the eval.
- **Clear the noise floor before keep or discard**: the A-vs-A′ difference (same recipe, new seed), or ≥ 3
  training seeds per arm with a CI; with 2 the verdict is inconclusive, and a two-seed gate that splits is "not
  met". Compare a pick only with a pick made the same way, because best-of-N inflates by itself. Numbers and
  method: `references/diagnostics.md` §6; `scripts/compare_arms.py` computes them.
- **A speed lever must not change the numbers.** Keep it only when the run is bit-identical to the plain path at
  full length. A speedup that changes the numbers (early stopping, TF32/bf16, compiler fusion) is a quality
  change and is judged by the task metric like any other lever.
- **Sim-to-real is an entry of its own** with `Base: <sim run>`, what was deployed (export path and sha, or the
  weight sha), robot, firmware rev, date and the real outcome, so the sim verdict stays frozen.
- **Keep it terse**: a lab notebook, not a report.

## Standing judgements

The calls that come up most, each argued with its sources in the reference named.

- Test the mechanism asked about, and say what the policy was fed; a knob fitted on the scored case is a best
  case, not a result (diagnostics §6).
- A student cannot be taught past its labels, though a recurrent one can generalise past memoryless teachers;
  check teacher competence in a regime before distilling there (deep-rl §8, diagnostics §4).
- DR has a timescale: per-step for fast exogenous noise, per-episode-constant for structural parameters the
  memory must identify (deep-rl §10).
- Noise in training is what makes a recurrent policy a filter; evaluate under deployment conditions (deep-rl §10,
  diagnostics §5).
- The sim-only failure is usually inner-loop latency; delay channels one at a time before blaming DR
  (diagnostics §5).
- The deadly triad is a design check: when someone proposes removing a guard, name which leg it holds and ask
  for the A/B (S&B 11.3, deep-rl §3).
- Reward says what, not how: non-potential shaping changes the optimum and every regulariser taxes something
  (deep-rl §12, diagnostics §7).
- Quirks in a faithful transcription are load-bearing: change one only as a flag-gated lever, byte-identical
  when off, with an A/B.
- γ is a hyperparameter even though S&B 10.4 deprecates discounting for continuing control; give its horizon
  in seconds (`compare_arms.py horizon`).
- A kept lever is not a kept combination: two levers that each passed are a new pre-registered experiment
  together.

## Scripts

Both are read-only; `${CLAUDE_SKILL_DIR}/scripts/<name>`.

`scripts/compare_arms.py` (python3, standard library only):

```bash
compare_arms.py compare --a 512 498 530 --b 541 560 538 [--paired]   # per-seed means: mean, sd, IQM, bootstrap CI, Welch t, P(b > a)
compare_arms.py compare --a-file a.csv --b-file b.csv --col return   # or one number per line without --col
compare_arms.py max-of-n 10 20 --sd 24                               # expected inflation of a best-of-N pick
compare_arms.py horizon --gamma 0.99 --dt 0.01                       # effective horizon in steps and seconds
```

Use per-seed means as samples when the arms differ by training seed, per-episode or per-frame returns when they
share one (`--paired` when the rows match); with 2 samples per arm the script prints the numbers and says the CI
is not to be trusted, which is the honest verdict.

`scripts/rl_log_entry.py <run dir> [--base <base run dir>]` pre-fills an Isaac Lab entry from the run's
`params/*.yaml` and prints the Changed line against a base run. It needs PyYAML, so run it with the training
host's Isaac Lab python (`references/isaac-lab-log.md` §3).

## When delegating

`deep-reasoner`, `fast-executor`, `implementer` and `verifier` cannot load skills. When an investigation or a
record goes to one of them, paste this block and the path of the reference it needs:

> Answer as an RL researcher. Ground theory in Sutton & Barto 2nd ed. by chapter.section and the literature by
> author year venue; read `<skill dir>/references/<file>.md` first and quote from it rather than from memory.
> Before proposing an experiment, check the project's own record for what was already measured: its ledger
> (`grep -rl 'Decision ledger' --include='*.md' .`) and any RL digest beside it (aquila: `verro/STATUS.md`,
> `verro/EVIDENCE.md` §9, `verro/RL_DIGEST.md`); cite repo code as `path:symbol` after grepping. Lead with the
> answer and its mechanism; say what the repo measured or "not measured here"; when a change is proposed, give
> the smallest confirming experiment with seeds, task metric, noise floor and kill rule. No keep/discard below 3
> seeds per arm or the A-vs-A′ floor; name best-of-N selection bias when a pick is compared to a non-pick. When
> recording, write in the record's own format with provenance from the run's files, and mark any number you did
> not read as pending. Propose training commands; do not launch them.

## Degradation

- No repo on this machine (claude.ai, a different box): answer from the references, say which project evidence
  would settle it, and give a record entry as a fenced block for the user to paste.
- Run artifacts on a remote training host (run dirs are usually gitignored, so the laptop and the box may each
  hold runs the other lacks): read them over ssh or ask for the manifest or config dump and
  `git -C <repo> rev-parse --short HEAD && git -C <repo> status --porcelain` from the host. Without the host's
  sha write `Code: unknown (local <sha>)`.
- A paper or figure you cannot open: "(unverified)".
- A document the record cites is gone from the checkout: read it from history (`git log --oneline -- <file>`,
  then `git show <commit>^:<file>`) and say which revision you read.
- The user wants the run started: state the command, the GPU-hours and the gate. Training runs, sweeps and
  evaluation batches go through the `verifier` agent or the user, not an inline launch.
