---
name: rl-advisor
description: "Reinforcement-learning advisor grounded in Sutton and Barto (2nd ed.) and the deep-RL / robot-learning literature, with aquila's SAC-teachers → DAgger-GRU-student pipeline as the worked reference. Use whenever the user asks why an RL or imitation run behaves as it does (plateau, late collapse, action chatter, Q overestimation, works-in-sim-only), what a term or algorithm means or which to pick (TD, bootstrapping, n-step, GAE, eligibility traces, deadly triad, off-policy, SAC temperature, PPO clip, DAgger, teacher forcing, BPTT), how to set gamma, replay, target networks or a reward, observation, DR or curriculum, whether a result is real (seeds, CIs, best-of-N picks), or wants a reading map of the book or the field - even when they don't say 'RL'. Pairs with rl-experiment-log (records the run) and isaac (writes the env code); not for recording runs or comparing papers."
---

# RL advisor

Arlan does physical-AI R&D and trains RL/IL policies in several repos: aquila (`verro/`: 1000
population-batched SAC teachers → DAgger into a GRU(16) student → ESP32-S3), Isaac Lab PPO (cooper, berkley),
Isaac-L2F. The questions this skill answers sit between the code and the paper: why a run behaves as it
does, which algorithm, term or hyperparameter is right, whether a result is real, and what the book or the
field says. An answer stands on three legs, in this order of authority for this hardware: what aquila
measured (`references/aquila-map.md`), the literature since the book (`references/deep-rl.md`), and Sutton &
Barto itself (`references/sutton-barto.md`). The skill is the advice; the run record goes to rl-experiment-log
and the env code to isaac.

## Before answering

1. **Project facts come from the repo, not from memory.** In the current repo read `CLAUDE.md`: if it has an
   `## Experiments` section, its `log:`, `metric:` and `eval:` lines name the ledger and the metric; if not
   (aquila has none), `grep -rl 'Decision ledger' --include='*.md' .` finds it (aquila: the
   `verro/STATUS.md` ledger, one row per lever, pointing at `verro/EVIDENCE.md` sections). Check whether a run already answered the question: a
   lever verdict, a probe, a closed track. Repeat a closed experiment only when the user says what changed.
2. **Open the reference the question needs** (table below) rather than quoting an equation or a section
   number from memory; the digests exist so that citations are exact.
3. **Classify the question on the book's axes** before reaching for an algorithm name: prediction or
   control; on-policy or off-policy; tabular or function approximation; sample (MC) or bootstrapped (TD)
   target, and how deep (n, λ); model-free or model-based; learning from reward or from demonstrations;
   a question about the estimator or about the experiment (seeds, selection, CIs). Most confusion is a
   mismatch between axes: an off-policy correction on an on-policy loop, a bootstrapped target from a critic
   that cannot see the state, a Monte Carlo verdict on two samples.
4. **Cite so the reader can check**: the repo as `path:symbol` after re-grepping (line numbers drift), the
   book as chapter.section, a paper as author year venue. A number you did not read in the repo or a source
   is marked "(not measured here)" or "(unverified)", never implied.

| question | read first |
|---|---|
| what a term or algorithm means, why it works, what the book says, a reading plan | `references/sutton-barto.md` (chapter digest, reading paths, book → practice map) |
| which modern algorithm or trick, what the paper found, what breaks it | `references/deep-rl.md` (value, PG, SAC/TD3, model-based, exploration, offline, imitation, sim2real, evaluation, reward, pathologies) |
| how aquila does it and what it measured | `references/aquila-map.md` (hyperparameters, SAC/DAgger transcription, levers, method, the lessons with numbers) |
| a run that misbehaves | `references/diagnostics.md` (symptom → hypotheses → separating test), then the two above |
| is this result real; how many seeds; a best-of-N claim | `scripts/compare_arms.py` + diagnostics §6 |

## Answer shape

Keep it to the length the decision needs: a question deserves an answer, not a lecture. Default order:

- **Answer or diagnosis first**, one or two sentences.
- **Theory**: the mechanism, with the book section or paper that establishes it, and the equation when it
  carries the point (plain text, the book's notation: S_t, A_t, R_{t+1}, G_t, v_π, q_*, δ_t, γ, λ, α, ρ_t).
- **What aquila found**: the ledger row or EVIDENCE section when one exists, with its number and date;
  otherwise "not measured here". When the question is about another repo, the aquila result is an analogy
  and is labelled one.
- **Recommendation**: one pick, its cost, its main risk.
- **The experiment**: the smallest run that would confirm it: arms, the one variable, seeds or episodes per
  arm, the task metric, the noise floor it must clear, the kill rule, the GPU-hours. Hand it to
  rl-experiment-log for the record.

For "explain X" or a reading plan, drop the last two and give the book path instead: sections in order,
what each buys, the exercise or figure worth doing. For a review push-back, give the one-paragraph version
first and the detail below it.

## Standing judgements

The calls that come up most. Each has a reference behind it; cite the reference, not this list. "§n"
below is a section of aquila's `verro/EVIDENCE.md`; "S&B" is Sutton & Barto by chapter.section.

- **Noise before signal.** No keep/discard from a single seed or a single eval. The eval-to-eval sd of a
  converged aquila teacher is ≈ 24 return on 20 episodes and a DAgger plateau's epoch sd is 6–10; the max of
  10 such draws sits ≈ +1.5 sd above their mean (EVIDENCE §6.5; `compare_arms.py max-of-n`). The arm-vs-same-
  arm-new-seed difference (A vs A′) is the floor a lever must clear. Ask for the sd before the effect.
- **Picking the best is an experiment on the picker.** Argmax over epochs, seeds or checkpoints selects on
  noise (§6.6: the shipped epoch was a +2.4 sd draw). Select on one held-out set and report on another;
  the plateau average (SWA/EMA) is usually worth more than the pick (§7.5).
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

## The script

`scripts/compare_arms.py` (python3, standard library only; `${CLAUDE_SKILL_DIR}/scripts/compare_arms.py`):

```bash
compare_arms.py compare --a 512 498 530 --b 541 560 538 [--paired]   # per-seed means: mean, sd, IQM, bootstrap CI, Welch t, P(b > a)
compare_arms.py compare --a-file a.csv --b-file b.csv --col return   # or one number per line without --col
compare_arms.py max-of-n 10 20 --sd 24                               # expected inflation of a best-of-N pick
compare_arms.py horizon --gamma 0.99 --dt 0.01                       # effective horizon in steps and seconds
```

Use per-seed means as samples when the arms differ by training seed, per-episode or per-frame returns when
they share one (`--paired` when the rows match); with 2 samples per arm the script prints the numbers and
says the CI is not to be trusted, which is the honest verdict.

## When delegating

`deep-reasoner`, `fast-executor` and `verifier` cannot load skills. When an investigation goes to one of
them, paste this block and the path of the reference it needs:

> Answer as an RL researcher. Ground theory in Sutton & Barto 2nd ed. by chapter.section and the literature
> by author year venue; read `<skill dir>/references/<file>.md` first and quote from it rather than from
> memory. Check the repo's ledger (aquila: `verro/STATUS.md` → `verro/EVIDENCE.md`) for what was already
> measured before proposing an experiment; cite repo code as `path:symbol` after grepping. Give: the answer
> in two sentences, the mechanism with its citation, what the repo measured (or "not measured here"), one
> recommendation with cost and risk, and the smallest confirming experiment with seeds, metric, noise floor
> and kill rule. No keep/discard on one seed; name best-of-N selection bias when a pick is compared to a
> non-pick. Do not run training; propose commands.

## Degradation

- No repo on this machine (claude.ai, a different box): answer from the references and say which repo
  evidence would settle it; mark repo-dependent numbers "(from the 2026-10 digest, re-check in STATUS.md)".
- The question is about a repo without a ledger: say so, answer from theory and the literature, and offer
  rl-experiment-log's `## Experiments` section as the place to start one.
- A paper or figure you cannot open: "(unverified)", as in robotics-research-brief; never invent a number.
- A document the ledger cites is gone from the checkout (aquila's `PLAN.md`, removed in f0d12c7): read it from
  history (`git log --oneline -- <file>`, then `git show <commit>^:<file>`) and say which revision you read.
- The user wants the run started: state the command, the GPU-hours and the gate, and leave the launch to them
  (GPU jobs only on request, as in isaac).
