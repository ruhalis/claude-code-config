# RL run diagnostics: symptom → hypotheses → the test that separates them

Read the symptom row, run the cheapest separating test first, and only then reach for a lever. Every row
names the theory behind it (S&B section or paper in `deep-rl.md`) and, where aquila met the symptom, the
precedent (`aquila-map.md` §10 has the numbers). "Task metric" means a quantity independent of the shaped
reward (success rate, tracking error, frames below a fixed gate).

Contents: 1 Learning curve shapes · 2 Value/critic problems · 3 Policy problems · 4 Imitation and
distillation · 5 Sim-to-real · 6 Statistics (is it real?) · 7 Reward changes · 8 Numerics and
infrastructure · 9 Questions to ask before proposing a lever

## 1. Learning curve shapes

| symptom | hypotheses, most likely first | separating test |
|---|---|---|
| Flat from the start | reward never reached (exploration); observation not informative or wrongly scaled; actions saturated; LR/clip so small nothing moves | Log reward components per step and the fraction of episodes with any task reward; check obs/action ranges at the policy input; a random policy's return vs the learner's |
| Flat return *and* flat loss from epoch 0 on a subset distill (small bank, few teachers, short crash episodes) | dataset starvation, not learning: the BPTT batcher (aquila `v/distill/dataset.py`) drops partial 500 × 64 chunks, so teachers · episodes · steps under one chunk gives `num_batches = 0` and no gradient; it is logged, not raised | Read `num_batches` (and the `starved` flag, `v/distill/trainer.py`) in the first epochs of `log_distill.jsonl`; expected batches ≈ (N · episodes · steps − 1) // (500 · 64); match the standing recipe (~155 batches of 64 per epoch) with `--episodes ceil(9984/N) --batch-size 64`. aquila's 2026-06-22 drag A/B on 64 frames sat at −71 in both arms for this reason (memory note; not in STATUS/EVIDENCE) |
| Rises then plateaus below the known-achievable | capacity of the policy/representation; a term in the reward taxing the behaviour needed; state not Markov (missing velocity, delay); critic bias at the horizon | Train a bigger net or a privileged variant as an upper bound; ablate reward terms one at a time; add the suspected missing input to the critic only (asymmetric) and see if the ceiling moves |
| Rises then collapses late | SAC temperature runaway or collapse; critic divergence (deadly triad, S&B 11.3); replay filled with stale, now-off-policy data; LR too high for the sharpened policy | Plot α, policy entropy, Q mean/max and TD error over time; the collapse usually shows in Q before return. aquila: 69/1000 teachers finished > 100 below their best, 15 crossed below the gate — keep snapshots and re-evaluate the top ones on fresh seeds |
| Period-2 oscillation of an iterated loop (DAgger, self-play, curriculum stage flips) | the state distribution flips each iteration because the policy trained on iteration k's states differs at k+1 (on-policy loop gain too high) | Lag-1 vs lag-2 autocorrelation of the per-iteration metric (aquila `tools/loop_stats.py`: lag-2 > lag-1 on 5 of 7 runs); damp with a dataset window over iterations, LR decay, EMA of the policy |
| High variance across seeds, same config | the task has a bimodal outcome (finds the trick or not); early data decides (primacy bias); the metric is noisy, not the learner | Report per-seed curves, not the mean; IQM + CI (diagnostics §6); check if seeds differ at a specific stage |
| Improves in training return, task metric flat | reward hacking / the shaped term is being farmed; the training return includes exploration noise effects | Watch the task metric and each reward term; roll out deterministic policy separately |

## 2. Value / critic problems

| symptom | hypotheses | separating test |
|---|---|---|
| Q grows without bound | deadly triad (off-policy + bootstrapping + FA); reward scale (returns ≫ network init range); γ too close to 1 for the reward magnitude; target network too fast (τ too large) | Compare Q to a Monte Carlo return estimate on the same states; halve τ or LR; scale rewards; S&B 11.2–11.3 |
| Q overestimates (Q ≫ MC return) | maximization bias (S&B 6.7); single critic; policy exploiting critic errors (DDPG) | Add/verify clipped double-Q; target policy smoothing; TD3 §3 |
| Q underestimates | pessimism from clipped min with very different critics; entropy term dominating the target (α too high) | Log α·log π against r; check target entropy |
| TD error rising while return stable | the critic lags a fast-changing policy or a reward change; LR mismatch actor/critic | Critic-only warm-up steps; lower actor LR; S&B 4.6 (GPI needs the evaluation to catch up) |
| Fine with MC targets, unstable with TD | bootstrapping off a bad representation (Baird-like) | Use n-step or λ-returns as a middle (S&B 7, 12); add layer norm to the critic; reduce replay ratio |

## 3. Policy problems

| symptom | hypotheses | separating test |
|---|---|---|
| Entropy / α → 0 early | target entropy too low for the action scale; reward scale large relative to the entropy term; tanh saturation (actions pinned at bounds) | Histogram of pre-tanh means; raise target entropy; rescale rewards |
| Actions chatter at high rate | observation noise not in training; action-rate term too small; the policy reacts to a noisy derivative channel | Roll out with noise on/off; aquila: action rate 0.007 → 0.70 without noise training, 0.039 with (noise-trained GRU "learned to filter"); add the `d_action` term's contribution to the log |
| Policy only works with the exploration noise it trained with | on-policy value of the noisy policy ≠ deterministic policy (Sarsa vs Q-learning, S&B 6.5 cliff) | Evaluate deterministic and stochastic; deploy the one you evaluated |
| Good mean, bad tail (a fixed subset of tasks/frames fails) | shared representation sacrifices the subset (lossy compressor); data imbalance in the distillation set; the subset is genuinely harder (low authority) | Check whether the teachers/experts are competent on the subset (aquila: they were — tail = capacity or data balance, not labels); oversample the hard subset (kept: tail 36 → 23); capacity probe (not kept: moved the mean, not the tail) |
| PPO KL runs away / clip fraction near 1 | LR too high for the batch; advantages unnormalised; too many epochs on the batch | Adaptive LR on desired KL (rsl_rl), fewer epochs, normalise advantages |

## 4. Imitation and distillation

| symptom | hypotheses | separating test |
|---|---|---|
| Student much worse than teacher everywhere | compounding error (BC without DAgger: O(T²ε)); student architecture cannot represent the teacher (no memory for a history-dependent label); labels from the wrong observation (privileged vs sensor) | Measure the per-step imitation error on student-visited states vs teacher-visited states; add DAgger iterations; aquila student MSE floor 0.038 clean vs 0.075–0.081 on the harder bank |
| Student worse *at the thing it was trained for* (e.g. faults) after adding exposure | label quality: the teacher itself fails there, so the student imitates flailing (a recurrent student may already generalise past memoryless teachers there, and relabelling pulls it back); the teacher's style tax transferred (reward terms penalising its busyness) | Competence sweep of the teachers on that regime *before* the distill (EVIDENCE §4: ≤ 0.3 distill territory, ≥ 0.4 retrain; the DAgger bound is in `deep-rl.md` §8); compare student vs teacher on that regime first; if teachers fail, retrain teachers, not the student |
| Student fine on fixed targets, poor on moving ones | the label depends on information the student does not see (future reference); a memoryless teacher cannot teach anticipation | Give the input to the teacher first (aquila lookahead arms A/A′/B/C); do not expect distillation to add information the labels lack |
| DAgger returns oscillate epoch to epoch | loop gain (see the diagnostics §1 oscillation row); oversampling weights raise it (aquila: highest plateau sd on both oversampling seeds) | Window the dataset across epochs; EMA/SWA the student; pick by held-out selection, never the argmax epoch |
| Best epoch looks great, replication does not | argmax over epochs is a +2.4 sd draw of the plateau (EVIDENCE §6.6) | Re-evaluate the top-k with a fresh seed; prefer the plateau average |
| Student "regressed" against a render or another simulator | a different policy in the recording (aquila's pre-10-21 Isaac renders were upstream RAPTOR, not the student); a different path, speed or airframe; a sim with its own termination box | Read the recording's meta for the policy hash, path and airframe before comparing; compare only on a matched path and airframe (aquila row L56 is the matched comparison); a fast un-ramped default path (0.5 m / 4 s, 1.11 m/s) breaks every hover-trained policy, so it measures the path, not the policy |
| A pick halves the failures but doubles the hover offset | the two metrics weight different frames; the pick is a trade-off on the task-metric set, not a win | Report every task metric side by side with the baseline and leave the call to the user (aquila row L55 is the instance); never select on the one metric that moved |
| Steady-state bias differs between snapshots of one run | a loss-invisible snapshot property (an MSE on actions does not see a 1 cm offset), so it swings epoch to epoch; SWA weight-averaging shifts it while output-averaging the same snapshots does not | Measure the offset per snapshot on held-out frames and across frame halves (aquila: r 0.97 between halves, swing −3.6…+3.2 cm, SWA ≈ −0.85 cm, output-average +0.03 cm; brainstorm probes 2026-10-27, re-check in EVIDENCE); a fine-tune that removes the bias can cost return, so judge it on the full metric set |

## 5. Sim-to-real

| symptom | hypotheses | separating test |
|---|---|---|
| Perfect in sim, oscillates or crashes on hardware | latency in the inner loop (IMU → motor) the sim did not have; estimator filtering (a low-pass is a delay); actuator dynamics (motor time constant) missing | Delay channels one at a time in sim (aquila: attitude+gyro cliff at 10 ms; position/velocity free to 30 ms); add a first-order actuator model; measure the real loop timing |
| Works at hover, fails under disturbance | DR magnitude never covered it; memory cannot identify a per-step-jittered parameter (DR timescale rule) | Competence sweep over the disturbance magnitude; make structural DR per-episode-constant |
| Policy saturates actuators on the real system | thrust-to-weight / authority mismatch; sim motor model optimistic | Compare commanded vs achieved on a bench (motor-bench skill); check sampled dynamics against the measured airframe |
| Sensor noise in the field breaks a sim-clean policy | noise not in training | Train with estimator-scale noise (aquila: 705/1000 frames fail without it); keep clean gate + perturbed rollouts separate |
| Drift / steady-state offset | the policy was trained with a reward on absolute position but sees a biased estimate; trim | Steady-state offset correction on the dataset (aquila), or a relative-obs regime; constant bias DR was dead weight |
| Sags or hovers low on one airframe only, fine on the fleet | hover command at the edge of the trained thrust-to-weight range (saturation); battery voltage (a motor map with no V_bat term makes a low battery look like a low-T/W frame); not motor-lag asymmetry | Check the frame's T/W against the training range (aquila U[1.5, 5]; the Crazyflie's 1.47 is below it and needs rpm 0.806 > the training max 0.794; brainstorm probe 2026-10-27, re-check in EVIDENCE); reproduce in the torch sim by lowering T/W, then V_bat; check the sim's termination box (Isaac-L2F ends an episode when any position component passes 1 m) before reading a crash as a policy failure |

## 6. Statistics: is the result real?

- **Two numbers are not a result.** Ask for the eval sd first (same policy, new eval seed). aquila's
  converged-teacher eval sd is ≈ 24 return on 20 episodes; a DAgger plateau's epoch sd is 6–10.
- **A success rate has a binomial sd.** p over n episodes has sd √(p(1 − p)/n): 0.8 on 32 episodes is ± 0.07, so two
  such rates 0.05 apart are within one draw of each other. aquila's per-frame pass/fail counts (the "binomial sd ≈ 5"
  on 1000 frames) are the same formula.
- **Seeds**: ≥ 3 per arm to say "better", ≥ 5 to size an effect; with 2 the honest verdict is
  "inconclusive" (rl-experiment-log's rule). `compare_arms.py compare --a … --b …` prints the bootstrap
  CI, Welch t, IQM and P(b > a); `--paired` when arms share seeds/frames.
- **Best-of-N inflation**: `compare_arms.py max-of-n N --sd σ`. Subtract it mentally from any "best
  checkpoint" claim; compare picks against picks made the same way, or re-evaluate the pick on fresh
  seeds.
- **Noise floor**: an A-vs-A′ arm (same config, new seed) measured on the same protocol is the bar a
  lever must clear; without it, use the across-seed sd of the baseline.
- **Held-out selection**: select on one half, report on the other (aquila `--split t2i`); the rank-1 vs
  rank-2 margin was ≈ 1 frame against a binomial sd ≈ 5, i.e. selections at 0.2 sd — treat ties as ties.
- **Two seeds cannot carry a keep.** A pre-registered "both students agree" gate on aquila's lookahead step 1
  split (seed 0 FAIL, seed 1 PASS; ledger row L54): the honest reading is "not met", not "one of two passed".
  `compare_arms.py compare` with two samples per arm prints the numbers and says the CI is not to be trusted.
- **Test the mechanism asked about, and say what the policy was fed.** A proxy that changes the input is a different
  idea: reshaping or pre-compensating the reference does not test "give the policy the future reference", which needs
  a policy that sees it (a retrain). A knob fitted on the case you score is a best case on the test itself; fit it on
  held-out cases or label it so. State what the policy was fed, not only the target it was scored against. (aquila,
  2026-10-22: a reference-shaping sweep tuned on the scored figure-eight was presented as what chunks would carry; the
  user called it cheating.)
- **A trade-off is not a win.** When a candidate improves one task metric and worsens another, report both against
  the baseline and leave the pick to the user (diagnostics §4; aquila row L55).
- **Pre-register** the gate, the metric and the kill rule; afterwards the verdict is keep / discard /
  inconclusive, and a confounded run judges the bundle.

## 7. Reward changes

1. Before changing a term, find the last time it was touched and what happened (rl-experiment-log:
   the log, `git log -L` on the term, the ledger).
2. Is the change potential-based (F = γΦ(s') − Φ(s))? If not, it can change the optimal policy; say so
   and watch the task metric, not the return.
3. Predict the side effect: which behaviour becomes cheaper? (Action-rate terms tax corrections; progress
   terms reward speed over safety; alive bonuses reward stalling.)
4. One term per run; the critic will lag after the change, so judge after it re-converges.

## 8. Numerics and infrastructure

| symptom | check |
|---|---|
| Two runs with the same seed differ | TF32 (cuDNN/cuBLAS defaults), nondeterministic kernels, GEMM grouping after a code change (aquila: cuDNN interval GRU vs the per-step loop differ at ~1 ulp fp32), host-dependent `randn` |
| NaN loss from epoch 0 | a NaN in a masked statistic (NaN·0 = NaN; use `where`); a terminated env still integrating; log-prob of a saturated tanh action |
| Resume differs from the uninterrupted run | RNG state restored on the wrong device, replay not persisted, lever flags not persisted (aquila: all three happened; now recorded in every checkpoint) |
| Adam behaves differently from the reference implementation | ε placement (inside vs outside the sqrt), bias correction, weight decay coupling; rl-tools floors v̂ at 1e-7 inside the sqrt |
| Throughput: GPU busy < 60 % | launch-bound (many small kernels per step); CUDA graphs / fused kernels (aquila: 1017 kernels/iter, 2.5× from graphs + fused Adam, bit-identical) |

## 9. Questions to ask before proposing a lever

1. What is the task metric, and what is its noise (sd across eval seeds)?
2. Has this lever, or this term, been tried in this repo? (ledger, log, `git log -S`)
3. Which axis of the problem does the lever change: data distribution, labels, capacity, objective,
   optimisation, or the environment's transition function? A transition-function change invalidates
   every upstream policy (aquila's P1/P2: teacher retrain).
4. What is the A/B: one variable, same seeds, same eval protocol, a pre-registered gate?
5. What would make you stop (kill rule), and what is the cost in GPU-hours?
6. What is the smallest version (fewer frames, shorter run, CPU smoke) that would show the effect's
   sign before the full campaign?
7. What will the policy be fed in the test, and what will it be scored against? If either differs from the
   deployment case or from the mechanism under question, say so before the run (diagnostics §6).
