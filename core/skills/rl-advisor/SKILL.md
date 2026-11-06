---
name: rl-advisor
description: "RL and imitation-learning advisor and lab notebook, grounded in Sutton and Barto (2nd ed.) and the deep-RL / robot-learning literature, with aquila's SAC-teachers → DAgger-GRU-student pipeline as the worked reference. Use whenever the user asks why a run behaves as it does (plateau, collapse, action chatter, Q overestimation, works-in-sim-only), what a term or algorithm means or which to pick (TD, GAE, deadly triad, SAC, PPO, DAgger, BPTT), how to set gamma, replay, a reward, observation, DR or curriculum, or whether a result is real (seeds, CIs, best-of-N picks); and whenever they start, stop, sweep, compare or finish a training run, ask what was tried before or which run was best, are about to change a lever, reward term or hyperparameter, or mention a run log, decision ledger or ledger row, run manifest, gate file, TensorBoard/W&B run or sim-to-real test - even when they don't say 'RL'. Not for writing env code (isaac) or comparing papers (robotics-research-brief)."
---

# RL advisor

Arlan does physical-AI R&D and trains RL/IL policies in several repos: aquila (`verro/`: 1000
population-batched SAC teachers → DAgger into a GRU(16) student → ESP32-S3), Isaac Lab PPO (cooper, berkley),
Isaac-L2F. This skill does two jobs that meet in one conversation. **Advise**: why a run behaves as it does,
which algorithm, term or hyperparameter is right, whether a result is real, what the book or the field says.
**Record**: the pre-registration before a run and the verdict after it. Advice usually ends in the smallest
confirming experiment, and that experiment is what the record step writes down. Advice stands on three legs, in
this order of authority for this hardware: what aquila measured (`references/aquila-map.md`), the literature
since the book (`references/deep-rl.md`), and Sutton & Barto itself (`references/sutton-barto.md`). The env code
goes to isaac.

## First: find the record

Project facts come from the repo, not from memory, and the run record is where they live. Once per project:

1. The repo's `CLAUDE.md` has an `## Experiments` section: its `log:` path is the record, and `run-id:`,
   `runs:` (host:path of the run dirs), `metric:`, `eval:` and `framework:` fill the matching fields.
2. Otherwise the repo keeps a ledger: `grep -rl 'Decision ledger' --include='*.md' .`, and you write in that
   ledger's own format. aquila has no `## Experiments` section; its ledger is `verro/STATUS.md`
   `## Decision ledger` (one `Lnn` row per lever or campaign) with the same-ID full row in `verro/EVIDENCE.md`
   §9. Its record step is `references/aquila-map.md` §13.
3. Otherwise propose `experiments/LOG.md` (in a monorepo, next to the training package) in the template of
   `references/isaac-lab-log.md`. Run `git check-ignore -q <path>` first; if the path is ignored use
   `docs/EXPERIMENTS.md` and say so. If the repo has a doc-ownership map (cooper's `CLAUDE.md`), ask before
   creating the file and add it to the map in the same change. Once chosen, offer to record it as an
   `## Experiments` section.

Then check whether the question was already answered: a lever verdict, a probe, a closed track, the last time
this term or flag was touched (the record, `git log -S'<flag>'`, the comments beside the term). Repeat a closed
experiment only when the user says what changed. The repo record is the only home for run history; the
Obsidian vault gets a summary only on request, at `~/obsidian/ruhalis/1. Projects/<Project>/Experiments.md`,
linking back to it.

## Advise

1. **Open the reference the question needs** (table below) rather than quoting an equation, a section number
   or a measured number from memory; the digests exist so that citations are exact.
2. **Classify the question on the book's axes** before reaching for an algorithm name: prediction or
   control; on-policy or off-policy; tabular or function approximation; sample (MC) or bootstrapped (TD)
   target, and how deep (n, λ); model-free or model-based; learning from reward or from demonstrations;
   a question about the estimator or about the experiment (seeds, selection, CIs). Most confusion is a
   mismatch between axes: an off-policy correction on an on-policy loop, a bootstrapped target from a critic
   that cannot see the state, a Monte Carlo verdict on two samples.
3. **Cite so the reader can check**: the repo as `path:symbol` after re-grepping (line numbers drift), the
   book as chapter.section, a paper as author year venue, aquila's record by ledger row ID. A number you did
   not read in the repo or a source is marked "(not measured here)" or "(unverified)", never implied.

| question | read first |
|---|---|
| what a term or algorithm means, why it works, what the book says, a reading plan | `references/sutton-barto.md` (chapter digest, reading paths, book → practice map) |
| which modern algorithm or trick, what the paper found, what breaks it | `references/deep-rl.md` (value, PG, SAC/TD3, model-based, exploration, offline, imitation, sim2real, evaluation, reward, pathologies) |
| how aquila does it, what it measured, how its runs are recorded | `references/aquila-map.md` (hyperparameters, SAC/DAgger transcription, levers, method, closed results, the record step in §13) |
| a run that misbehaves | `references/diagnostics.md` (symptom → hypotheses → separating test), then the two above |
| is this result real; how many seeds; a best-of-N claim | `references/diagnostics.md` §6 + `scripts/compare_arms.py` |
| recording an Isaac Lab run, or a repo without a ledger | `references/isaac-lab-log.md` (entry template, run dirs, config dump, Changed check) + `scripts/rl_log_entry.py` |

Keep the answer to the length the decision needs: a question deserves an answer, not a lecture. Default order:

- **Answer or diagnosis first**, one or two sentences.
- **Theory**: the mechanism, with the book section or paper that establishes it, and the equation when it
  carries the point (plain text, the book's notation: S_t, A_t, R_{t+1}, G_t, v_π, q_*, δ_t, γ, λ, α, ρ_t).
- **What aquila found**: the ledger row or EVIDENCE section when one exists, with its number and date;
  otherwise "not measured here". When the question is about another repo, the aquila result is an analogy
  and is labelled one.
- **Recommendation**: one pick, its cost, its main risk.
- **The experiment**: the smallest run that would confirm it: arms, the one variable, seeds or episodes per
  arm, the task metric, the noise floor it must clear, the kill rule, the GPU-hours. Offer to write it down as
  the pre-registration (Record).

For "explain X" or a reading plan, drop the last two and give the book path instead: sections in order,
what each buys, the exercise or figure worth doing. For a review push-back, give the one-paragraph version
first and the detail below it.

## Record

A run gets two writes: a start note before launch and a verdict after it. Whatever the format, these fields:

- **Before**: Base (the run or row it differs from), Changed (the one variable, as config path old → new, or
  the commit for a code change), Code (repo@sha, `-dirty` if `git status --porcelain` is not empty, branch),
  Command (exact, with every env var the launcher reads; secrets redacted), Inputs (init checkpoint, dataset,
  teacher bank, with a sha or the run that produced it), Seeds, and the gate: task metric, bar, noise floor,
  kill rule, expected effect.
- **After**: Result (the task metric with its protocol: N episodes or frames, which checkpoint and how it was
  picked, eval seed, sd; wall time and GPU), Verdict (keep / discard / inconclusive, one sentence why), Next
  (the single next change).

Where they go:

- **aquila**: the ledger takes results only ("Results land here; plans do not", `CLAUDE.md`), so the
  pre-registration goes in the plan doc that owns the track or in a `prereg_<id>.md` beside the eval outputs,
  which the row then cites. After the run, read the campaign's `manifest.json` and `gate_<tag>.json` (the gate
  file's `provenance` carries git sha, branch, dirty flag, host and argv), then write the next `Lnn` row in
  STATUS (one line, ≤ ~180 characters: what, **verdict**, refs) and the full row under the same ID in
  EVIDENCE §9. Field by field, with old-format manifests and the student weight sha: `aquila-map.md` §13.
- **Isaac Lab or a repo without a ledger**: the entry template, run-id naming, the `params/env.yaml` dump and
  the Changed check are in `references/isaac-lab-log.md`; `scripts/rl_log_entry.py` pre-fills the entry from a
  run dir.

An entry is open until it has a Verdict, then frozen: a correction is a new entry or row (`Base: <id>
(correction)`; in aquila's EVIDENCE a supersession note, never a rewrite of the body). Never invent a number:
`Result: pending (on <host>:<path>)` until it arrives. To summarise, give a table of id | changed | task metric
| verdict from the record, then a short read of the trend.

## Rules

One copy; the references explain them.

- **One variable per run**, unless it is a declared sweep (one entry with a sub-table). Every undeclared
  difference between base and new run goes on a `Confounded:` line, and the verdict then judges the bundle.
  A reward-formula change in code is the one variable and cites its commit; a stack bump (simulator, RL
  library, torch, driver) is a run of its own.
- **Judge by the task metric**, a quantity independent of reward weights (success rate, tracking error, frames
  below a fixed gate, gate return under a fixed eval reward), never by training return when the reward, the
  dataset or the env differs between arms. A run closed without the task metric is inconclusive, and Next is
  the eval.
- **Clear the noise floor before keep or discard**: the A-vs-A′ difference (same recipe, new seed), or ≥ 3
  training seeds per arm with a CI; with 2 the verdict is inconclusive, and a two-seed gate that splits is "not
  met". Compare a pick only with a pick made the same way, because best-of-N inflates by itself. Numbers and
  method: `diagnostics.md` §6; `compare_arms.py` computes them.
- **A speed lever must not change the numbers.** Keep it only when the run is bit-identical to the plain path
  at full length (aquila: `compare_runs.py` IDENTICAL on full waves). A speedup that changes the numbers
  (early stopping, TF32/bf16, compiler fusion) is a quality change and is judged by the task metric like any
  other lever (`aquila-map.md` §8).
- **Sim-to-real is an entry of its own** with `Base: <sim run>`, what was deployed (export path and sha, or
  the weight sha), robot, firmware rev, date and the real outcome, so the sim verdict stays frozen.
- **Keep it terse**: a lab notebook, not a report.

## Standing judgements

The calls that come up most. Each has a reference behind it; cite the reference, not this list. "§n"
below is a section of aquila's `verro/EVIDENCE.md`; "S&B" is Sutton & Barto by chapter.section.

- **Test the mechanism, and say what was fed.** A proxy that changes the input (a reshaped reference) does not test
  the mechanism asked for (a policy that sees the future); a knob fitted on the scored case is a best case on the
  test, not a result. State what the policy was fed, not only what it was scored against (diagnostics §6).
- **A student cannot be taught past its labels, though it can generalise past them.** The recurrent student
  beats its memoryless teachers under a rotor fault (517.8 vs 371.4 at 0.3, §4) through system
  identification and general DR, with no fault labels at all. Relabelling in a regime where the teachers
  flail pulls it back toward them: the clean-bank fixed-0.2 fault distill made the student worse at faults at
  every level (§3), and the retrained-bank exposure arms A3/A3b failed for a second reason, the teachers'
  style tax transferring everywhere while the thin benefit died under 2× imitation error (§4). Ask what the
  teacher does there before training the student there; the competence sweep is the minutes-scale check.
- **DR has a timescale.** Per-step for fast exogenous noise (sensor and action noise, gusts), per-episode-
  constant for structural parameters the memory must system-identify (mass, τ, drag, fault). Per-step
  structural jitter destroys the sysID signal; the GRU latent reads thrust-to-weight at R² 0.94 when it
  is allowed to (§2).
- **Noise in training is what makes a recurrent policy a filter.** Obs-noise during distillation was the one
  big win (+147 at the trained magnitude; without it 705/1000 frames fail under sensor noise, §3, §5);
  constant bias was dead weight. Evaluate under deployment conditions: the clean-sim leaderboard inverts.
- **The sim-only failure is usually latency.** A memoryless high-gain attitude loop has no margin: one 10 ms
  IMU frame cost ~25 % of episodes; a heavy velocity low-pass is a delay in disguise (§6.1, §6.3). Delay the
  channels one at a time before blaming DR, and train with the delay you will have (§6.7, kept).
- **The deadly triad is a design check, not trivia.** Off-policy data + bootstrapping + function
  approximation can diverge (S&B 11.2–11.3); target networks, clipped double-Q, a replay ratio near 1 and a
  tuned γ are what hold it. When someone proposes removing a guard, name which leg it was holding and ask
  for the A/B.
- **Reward says what, not how.** Shaping that is not potential-based (Ng, Harada, Russell 1999; S&B 3.2,
  17.4) changes the optimal policy, and every regulariser taxes something (aquila's `d_action` term charged
  ≈ 35 of a −60 gap). Judge a reward change by the task metric, never by the shaped return.
- **Quirks in a transcription are load-bearing.** Under aquila's fidelity rule an upstream oddity
  (orientation cost 2·acos(1 − |q_z|), the Adam floor inside the sqrt, the dropped exact-multiple batch) is
  reproduced on purpose. "Fix" it only as a flag-gated lever with the faithful path byte-identical when off,
  and an A/B.
- **The book's agenda vs practice.** S&B 10.4 deprecates discounting for continuing control with function
  approximation; every deep-RL baseline discounts anyway because γ works as a horizon knob. When asked,
  give both and treat γ as a hyperparameter with 1/(1 − γ) in seconds (`compare_arms.py horizon`).
- **A kept lever is not a kept combination.** Two levers that each passed their gate failed it together on
  one seed (§8.2); combining them is a new pre-registered experiment.

## Scripts

Both are read-only; `${CLAUDE_SKILL_DIR}/scripts/<name>`.

`scripts/compare_arms.py` (python3, standard library only):

```bash
compare_arms.py compare --a 512 498 530 --b 541 560 538 [--paired]   # per-seed means: mean, sd, IQM, bootstrap CI, Welch t, P(b > a)
compare_arms.py compare --a-file a.csv --b-file b.csv --col return   # or one number per line without --col
compare_arms.py max-of-n 10 20 --sd 24                               # expected inflation of a best-of-N pick
compare_arms.py horizon --gamma 0.99 --dt 0.01                       # effective horizon in steps and seconds
```

Use per-seed means as samples when the arms differ by training seed, per-episode or per-frame returns when
they share one (`--paired` when the rows match); with 2 samples per arm the script prints the numbers and
says the CI is not to be trusted, which is the honest verdict.

`scripts/rl_log_entry.py <run dir> [--base <base run dir>]` pre-fills an Isaac Lab entry from the run's
`params/*.yaml` and prints the Changed line against a base run. It needs PyYAML, so run it with the training
host's Isaac Lab python (`references/isaac-lab-log.md` §3).

## When delegating

`deep-reasoner`, `fast-executor` and `verifier` cannot load skills. When an investigation or a record goes to
one of them, paste this block and the path of the reference it needs:

> Answer as an RL researcher. Ground theory in Sutton & Barto 2nd ed. by chapter.section and the literature
> by author year venue; read `<skill dir>/references/<file>.md` first and quote from it rather than from
> memory. Check the repo's record (aquila: `verro/STATUS.md` ledger → `verro/EVIDENCE.md` §9) for what was
> already measured before proposing an experiment; cite repo code as `path:symbol` after grepping. Give: the
> answer in two sentences, the mechanism with its citation, what the repo measured (or "not measured here"),
> one recommendation with cost and risk, and the smallest confirming experiment with seeds, metric, noise
> floor and kill rule. No keep/discard below 3 seeds per arm or the A-vs-A′ floor; name best-of-N selection
> bias when a pick is compared to a non-pick. When recording, write in the record's own format (aquila: one
> `Lnn` line of ≤ ~180 characters in STATUS plus the same-ID row in EVIDENCE §9, provenance from the gate
> file) and never invent a number. Do not run training; propose commands.

## Degradation

- No repo on this machine (claude.ai, a different box): answer from the references and say which repo
  evidence would settle it; mark repo-dependent numbers "(from the 2026-10 digest, re-check in STATUS.md)";
  give a record entry as a fenced block for the user to paste.
- The repo has no record yet: say so, answer from theory and the literature, and offer to start one (First,
  step 3).
- Run artifacts on a remote training host (aquila: ruhalis-home; `verro/runs/` is gitignored and the Mac and
  the box each hold runs the other may not): read them over ssh or ask for the manifest, the gate file and
  `git -C <repo> rev-parse --short HEAD && git -C <repo> status --porcelain` from the host. Without the host's
  sha write `Code: unknown (local <sha>)`.
- A paper or figure you cannot open: "(unverified)", as in robotics-research-brief; never invent a number.
- A document the record cites is gone from the checkout (aquila's `PLAN.md`, removed in f0d12c7): read it from
  history (`git log --oneline -- <file>`, then `git show <commit>^:<file>`) and say which revision you read.
- The user wants the run started: state the command, the GPU-hours and the gate, and leave the launch to them
  (GPU jobs only on request, as in isaac).
