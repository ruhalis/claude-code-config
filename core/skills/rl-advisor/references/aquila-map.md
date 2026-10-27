# aquila as the worked reference: where each RL idea lives and what it measured

aquila (`~/projects/aquila`, package `verro/`) reproduces the rl-tools RAPTOR recipe in PyTorch: 1000 SAC
teachers, one per sampled quadrotor dynamics, population-batched on one GPU → DAgger into a
`dense(22→16, ReLU) → GRU(16) → dense(16→4)` student → exported unchanged to the rl-tools executor on an
ESP32-S3. It is a faithful *transcription* of `third_party/rl-tools/src/foundation_policy/` (golden-tested),
and everything it added is a flag-gated lever with an A/B behind it, so it is a good place to point at when
a question is "what does this look like in a real pipeline, and did it help".

Paths are relative to the aquila repo root; `v/` = `verro/verro/`, `t/` = `verro/tools/`. Line numbers are
as of 2026-10-27 and drift: re-grep the symbol before citing one (`grep -n "def _critic_target" v/rl/sac.py`).
The authoritative state is `verro/STATUS.md` (milestones, "What is verified", the decision ledger) and the
numbers are in `verro/EVIDENCE.md` (sections cited as EVIDENCE §n); `CLAUDE.md` at the root has the doc map.
"PLAN item n" in STATUS/EVIDENCE refers to the pre-registration list of the root `PLAN.md`, which was removed with
`BACKLOG.md` in commit f0d12c7 ("remove outdated docs", 2026-10); read it with `git show f0d12c7^:PLAN.md` when a
ledger row cites it. The plan now lives in `verro-tracking.md` / `verro-lookahead.md` at the root.

Contents: 1 Hyperparameters · 2 SAC · 3 Replay and Adam · 4 Reward, termination, observation · 5 Domain
randomisation · 6 DAgger distillation · 7 Selection and gates · 8 Levers and the lever discipline ·
9 Experimental method · 10 What was measured (the lessons, with numbers) · 11 Open threads · 12 Book ↔ aquila

## 1. Hyperparameters (`v/config.py`, transcribed from `pre_training/config.h`, `post_training/config.h`)

| SAC (`SACConfig`) | value | | Distill (`DistillConfig`) | value |
|---|---|---|---|---|
| γ | 0.99 (horizon ≈ 100 steps = 1 s at 100 Hz) | | episodes per teacher per epoch | 10 |
| polyak | 0.995 per step (`sac.h: 1 − 0.005`) | | epochs | 1000 (10 teacher-forcing + 990 DAgger) |
| target entropy | **−2.0** (not −dim(A) = −4) | | BPTT sequence × batch | 500 × 64 |
| α init | log α = log 0.5; lr_α 1e-4 | | GRU width | 16 (`--hidden-dim` 24/32 supported) |
| batch | 128 (actor = critic, SHARED_BATCH) | | teacher gate | mean return ≥ 300 over 100 episodes |
| steps / replay cap | 1 M / 1 M (never wraps) | | labels | deterministic teacher, tanh(mean) |
| warm-up | **no random-action phase**; updates start once the buffer holds > 10k | | offset window | steps [250, 500) of POSITION episodes |
| critic / actor interval | every step / every 2nd step | | lr | 1e-4, RLToolsAdam |
| actor / critic | 3×64 / 2 critics 3×256, ReLU | | loss | MSE on actions |
| lr actor / critic | 3e-4 / 3e-4 | | dataset | rebuilt every epoch (`on_policy = True`) |
| log-std clamp | [−20, 2]; tanh ε 1e-6 | | | |
| episode | 500 steps at 100 Hz (5 s) | | | |

Standing distill defaults that are project-local: `--obs-noise` ON (`ObsNoiseConfig`: position 0.02 m,
rotation elements 0.01, velocity 0.10 m/s, gyro 0.04 rad/s), `--oversample-hard 1.0`, SWA of the every-50
snapshots from epoch 500, top-5 + every-50 snapshots. Teachers are always trained on clean observations.

## 2. SAC (`v/rl/sac.py` `PopulationSAC`, `v/rl/networks.py`; upstream `rl/algorithms/sac/operations_generic.h`)

- **Population batching**: `PopLinear` holds weights `[P, out, in]` and runs `torch.baddbmm`, so one forward
  advances all P teachers; losses are mean over batch, *sum* over population, so each member's gradient equals
  the single-instance gradient and one Adam over the stacked tensors is exactly P independent Adams
  (block-diagonal by construction). P = 64 per wave fits the 10 GB RTX 3080 at 7.7 GiB.
- **Squashed Gaussian** (`PopGaussianActor.sample`): a = tanh(μ + σ ε), log π = log N(u) − Σ log(1 − a² + 1e-6);
  the log-std clamp zeroes its gradient outside the bounds, as in the C++.
- **Critic target** (`_critic_target`): y = r + where(terminated, 0, γ · min(Q′₁, Q′₂)(s′, a′)) − α log π(a′|s′),
  a′ from the *current* actor; the entropy term is added unconditionally (`ENTROPY_BONUS_NEXT_STEP = false`);
  only physics termination masks the bootstrap, the 500-step truncation is bootstrapped through (a time
  limit is not a terminal state: Pardo et al. 2018 ICML; S&B 3.3–3.4 on episodic vs continuing).
- **Losses**: critic ½(Q − y)² for each critic on the same target; actor E[α log π − min(Q₁, Q₂)] with α
  detached and a fresh noise draw; temperature loss α · (−log π − H̄) with H̄ = −2; polyak after the critic step.
- **SHARED_BATCH** (fixed 2026-07-03, EVIDENCE §1): one replay batch and one target-action noise draw per step,
  reused by both critics and the actor. The independent-batches version was statistically unbiased, so the
  clean bank trained before the fix stays valid; it is a fidelity point, not a correctness one.
- **Exploration** is the stochastic policy from step 0 (no uniform-random phase). **Eval** is the deterministic
  policy, E parallel episodes of exactly 500 steps; 20 episodes every 50k steps for the log, 100 for the gate.
- **Gate**: `gate_<tag>.json`, mean return ≥ 300 per teacher. Upstream keeps all 1000 teachers; the 300 bar
  is `DistillConfig.solved_return`, re-asserted on clean physics in `DistillTrainer.setup`. Clean bank: 999/1000
  on the distill gate; the A2 drag+fault bank 720/1000 on its harder training env.
- Guards added (inert on finite values): NaN state → terminal self-loop; a member emitting a non-finite action
  is frozen sticky (`dead`), recorded in teacher and gate files.
- Speed (STATUS M3): `--cuda-graph full` + `--fused-adam` are bit-identical to eager and 2.5× faster
  (4056 s per P=64 wave); the eager profile was launch-bound (1017 kernels/iter, GPU 52 % busy).

## 3. Replay and Adam

- `v/rl/replay.py` `PopReplayBuffer`: uniform sampling per member, no prioritisation, no n-step; format 2
  stores each observation once (ring `[P, cap+1, D]` plus a compact side store for episode-ending rows),
  129.7 B/transition/member. `terminated` is stored separately from `done` so truncations bootstrap.
- `v/rl/optim.py` `RLToolsAdam`: update = lr · m̂ / (√max(v̂, 1e-7) + 1e-7). The second moment is floored
  *inside* the sqrt, so the denominator never drops below ≈ 3.2e-4 and small-gradient coordinates take much
  smaller steps than torch Adam. Used by SAC and the distill trainer; never swap in `torch.optim.Adam`.

## 4. Reward, termination, observation (`v/sim/reward.py`, `v/sim/observation.py`)

- Effective reward (weights identical in all 1000 JSONs): r = 1.5 − ‖p − p_des‖ − 0.1 · 2·acos(1 − |q_z|)
  − ‖a_t − a_{t−1}‖, and −100 on the step that terminates. Max 750 per episode; the gate is 300. The other
  terms (velocity, accelerations, action magnitude) exist with weight 0. The orientation cost reads only q_z
  (an upstream quirk, kept). The `d_action` term is what taxed the busy fault-retrained style (§10).
- Termination: |p| beyond a per-frame threshold (20 × max rotor distance, 0.55–4.8 m), |v| > 2 m/s,
  |ω| > 35 rad/s, or a non-finite state (project-local guard).
- Teacher obs, 26 dims: [p − p_des | R (9) | v − v_des | ω | previous action | normalised rotor speeds]; always
  clean. Student obs, 22 dims: [p | R | v | ω | previous action], absolute by default (`--relative-obs` gives
  the firmware's p − p_ref / v − v_ref regime). Noise, bias and delay (`v/sim/obs_delay.py`, per-episode
  fractional delay on a channel group: `imu` = rotation + gyro, `est` = position + velocity) apply to the
  student's observations only; labels always come from the true state.
- Desired state: half the episodes hover at the origin (POSITION), half track a Langevin target
  (γ=1, ω=2, σ=0.5, α=0.01) that moves slowly (median 0.18 m/s).

## 5. Domain randomisation (`v/sim/params.py`, `v/sim/env.py`)

- **Per airframe** (fixed per teacher, from the 1000 JSONs): thrust-to-weight U[1.5, 5], mass 0.02–5 kg
  uniform in size, rotor τ 0.03–0.10 s rising / 0.03–0.30 s falling, constant random force per episode scaled
  with (T/W − 1)·T/W·m; disturbance torque std 0 in the canonical set. 256 "payload" frames (T/W up to 8,
  off-centre CoM) were added 2026-10-22.
- **Per episode**: position U(±max), velocities U(±1), random attitude with angle ~ U(0, 1) rad (the `limit`
  argument is unused upstream, kept), 10 % guidance resets to rest, trajectory type 50/50.
- `with_default_init` restores the env-default init (max position 0.5 m) for every distillation and eval
  rollout but not for teacher training (`post_training/helper.h:11-13`).
- Project-local levers, all default off and byte-identical when off (§8): drag, single-rotor fault
  (`motor_effectiveness[rotor] = 1 − loss`, uniform or fixed mode), motor tolerance, τ jitter, OU wind scaled
  by thrust surplus, authority-scaled torque DR (`torque_auth_frac`), action noise, obs bias, obs delay.

## 6. DAgger distillation (`v/distill/trainer.py`, `rollout.py`, `dataset.py`, `student.py`, `average.py`)

- **Loop** (`post_training/main.cpp`): epochs 0–9 the teachers drive their own episodes (behaviour cloning on
  teacher-visited states); from epoch 10 the stateful GRU student drives on its (perturbed) observations and the
  per-frame teacher labels the visited states with its deterministic action. A hard switch, no β schedule
  (Ross et al. 2011's β_i = 1{i = 1} variant). `--teacher-student-mix M` ports upstream's optional extra
  teacher-driven passes.
- **Dataset**: 1000 teachers × 10 episodes × ≤ 500 steps (≈ 5 M labelled steps), rebuilt every epoch, no
  aggregation across epochs unless `--dagger-window W` (a damping lever, default 1). Hard-frame oversampling
  (`--oversample-hard`, ON since 2026-10-18): episodes are redrawn with replacement with weight
  1 + gap/mean-gap, gap = max(teacher return − this epoch's student return, 0) per frame; dataset size unchanged.
- **Offset correction**: per teacher, the mean position over steps [250, 500) of POSITION episodes is
  subtracted from the *dataset* position dims only; rollouts see raw observations (deployment parity). The
  NaN-safe `where` mask here fixed a full-scale NaN loss (STATUS).
- **BPTT batcher**: the episodes are shuffled, concatenated into one stream with a reset flag at each episode
  start, cut into 500 × 64 chunks; a boundary-spanning episode restarts from h0 at the next chunk and the final
  exact-multiple batch is dropped (upstream cursor quirks, kept). The GRU runs one cuDNN call per reset-free
  interval (exact at fp64 vs the per-step loop, ~1 ulp fp32 differences).
- **Loss / optimiser**: `F.mse_loss` over [500, 64, 4]; `RLToolsAdam` lr 1e-4. Best-of-epoch is tracked on the
  epoch's own 10-episode noise-on rollout return; snapshots are the pre-update weights that produced it.
- **Student**: `Linear(22,16) → ReLU → GRU(16) → Linear(16,4)`, persisted zero h0, no output tanh; GRU
  convention verified against rl-tools at 1e-12; on-device parity 4.8e-7 over 200 closed-loop steps.
- **SWA / EMA**: `student_swa.pt` = float64 mean of the every-50 snapshots from epoch 500; `--ema-from-epoch`
  writes `student_ema.pt` (decay 0.98); both are automatic selection candidates.

## 7. Selection and gates

- `t/select_student.py`: every snapshot + best + SWA/EMA scored on all 1000 frames × 8 episodes at held-out
  seed 1000 under still / noise / noise + 5 ms IMU delay; rank key = (frames below 300 under the last
  condition, −mean, −still mean). `--split t2i` (default): frames stratified by torque-to-inertia into two
  matched 500/500 halves, select on one, report on the other, cross-fit; a seed-stability Spearman check.
  The shipped student is this pick, never the single-epoch argmax (CLAUDE.md).
- A4 fault-switch harness (`t/eval_fault_switch.py`): hover 250 steps, cut one rotor to 1 − fault, watch
  20 s; pass at a level iff ≥ 90 % of 64 airframes keep ≥ 95 % post-injection survival, in both the clean and
  the flight (noise + torque DR) variant. A demo pick must pass it at 0.3.
- Teacher competence sweep (`t/teacher_competence_sweep.py`): an unchanged bank under an eval-time
  perturbation ramp (128 evenly spaced teachers × 8 episodes, fixed-loss semantics); reports the last
  100 %-pass level and the first mean-below-gate level. This is the minutes-scale measurement that decides
  P0 vs retrain (§8):
  `PYTHONPATH= .venv/bin/python tools/teacher_competence_sweep.py --axis fault --teachers runs/teachers_clean --levels 0.1 0.2 0.3 0.4 --device cuda`
  (`--axis drag|torque|fault`, `--episodes`, `--teachers-count`; run from `verro/`).
- Fleet eval (`t/eval_frames.py`): 1000 frames × 32 episodes, env-default init, raw obs; the task metrics are
  mean return and frames below 300.
- `v/eval/stats.py` has Spearman only; no CI is computed anywhere in the repo. Bring `compare_arms.py`.

## 8. Levers and the lever discipline (EVIDENCE §2)

- **Taxonomy**: P0 = distill-time only, valid inside the teachers' competence envelope (measure it with the
  sweep first); P1/P2 = transition-function changes that need a teacher retrain, batched into one campaign.
- **DR timescale rule**: per-step for fast exogenous noise (obs/action noise, gusts), per-episode-constant for
  structural parameters the GRU should system-identify (mass, τ, drag, bias, fault). Per-step structural
  jitter destroys the sysID signal.
- **Faithful path**: with a lever off, the original float path runs byte-for-byte (guard the term, never
  multiply by zero); every divergent path has its own unit test; golden tests stay green.
- **Clean gate, perturbed rollouts only**: the teacher gate and the offset estimation never see a lever.
- Levers and the dynamics hash are recorded in every checkpoint, snapshot, teacher file and gate file; `--resume`
  refuses a mismatch; a bank mixing physics refuses to load.

## 9. Experimental method (how verdicts are reached)

- One variable per run; a lever is compared to the baseline arm on the same frames, seeds and eval protocol;
  seed sd is stated; the verdict is keep / discard / inconclusive and lands as one ledger row (STATUS) pointing at
  an EVIDENCE section. Pre-registered gates (PLAN items) name the metric, the bar and the kill rule before the
  run. An A-vs-A′ arm (same recipe, new teacher seed) is the planned noise floor for the lookahead pilot.
- Task metrics: mean return and frames below 300 on 1000 × 32 (fleet), survival / excursion / settle on the
  A4 harness, tracking error on held-out figure-eights (lookahead). Training return is never the metric when
  the dataset or the env differs between arms.
- The record lives in the repo: rl-experiment-log's entry format maps onto the ledger row + EVIDENCE section.

## 10. What was measured: the lessons, with numbers

| date / section | finding | the RL point |
|---|---|---|
| 06-22, §2 | GRU latent linear probe: thrust-to-weight R² 0.939 (RAPTOR 0.949); log-mass R² ≈ 0 | memory does implicit sysID of the *controllable* ratio only (RMA/RAPTOR); keep structural DR per-episode |
| 06-22, §2 | drag DR: teacher gate flat to ±2 across dxy 0→1 s⁻¹; drag student overshoots more | a lever the metric is blind to cannot be tuned; a low-speed mission does not exercise drag |
| 06-22, §2 | disturbance torque: population authority spans 2500×, a flat std fails small frames | randomise relative to each instance's authority (authority-scaled DR) |
| 07-02, §3 | obs-noise distill: +147 @ trained magnitude, +288 @ 2× held-out; clean cost −7.7; action rate 0.70 → 0.039 under noise | noise in training makes the recurrent policy a filter; the single biggest win |
| 07-02, §3 | obs-bias: −13…−17, no benefit; action-noise σ 0.02 and τ-jitter 0.15: no-ops | position hold absorbs a constant bias; already-robust axes buy nothing |
| 07-02, §3 | distill-only motor fault on the clean bank, a fixed 0.2 loss every episode (the uniform U(0, m) training mode landed 07-03): −38 @ 0.2, −121 @ 0.4, clean tied | **label quality, not exposure**: the clean teachers flail under fault, the student imitates flailing |
| 07-02, §4 | fault competence sweep: pass 98/91/78/35/13 % at loss 0.1…0.5 | sized the campaign: ≤ 0.3 distill territory, ≥ 0.4 retrain |
| 07-07, §4 | A2 fault+drag+torque retrain, 16 × 64: fault-0.4 pass 35 → 58 %, clean mean 580 → 479 | harder env fixes the labels where it matters at a clean-level price |
| 07-09, §4 | A3 (0.2) / A3b (U(0, 0.4)) distills from that retrained bank: −60 flat / −59…−82, worse at high fault; student MSE floor 0.075–0.081 vs 0.038 clean | distillation transfers the teacher's style tax everywhere (≈ 35 of −60 is the `d_action` term) and loses a thin benefit under 2× imitation error; track closed. A clean-bank U(0, 0.4) arm was never run: neighbours on both sides, not the arm itself |
| 07-12, §4 | the standing student beats its own teachers under fault: 517.8 vs 371.4 mean return at loss 0.3 | the recurrent student generalises past memoryless labels (sysID + general DR); fault labels are not where its margin comes from |
| 07-12, §4 | A4 fault switch: standing student passes 0.3 in both variants (100 % / 99.1 %) | pre-registered gate frozen the demo policy |
| 07-27, §5 | WINDTOL: wind DR free in still air, +8.9 @ ×1 / +20.8 @ ×2 tail-concentrated; the WINDTOL bank costs −14.8 still-air | a bank retrain for one lever taxes every other regime; price it |
| 07-28, §5 | still-air gap to upstream decomposes exactly: recipe −11.8, bank −14.8, knobs −11.0, wind −0.3; knobs-off student fails 705/1000 under noise | the clean-sim leaderboard inverts under deployment conditions: evaluate under them |
| 07-28, §5 | upstream release is noise-fragile (329 / 185 failed at the composite vs ours 475 / 72) | |
| 09-02, §6.1 | delay cliff is attitude + gyro only: one 10 ms frame → 72 % settle (est channels free to 30 ms); 400 Hz executor makes 5 ms free, 10 ms −8 % | latency on the inner loop is the sim-to-real killer; delaying the previous action too overstated it |
| 09-02, §6.3 | estimator errors survivable at 98 % except a heavy velocity low-pass (IIR 0.9 → 55 %) | a filter is a delay |
| 09-02, §6.4 | fleet 596.5 / 39 below gate; 38/39 in the bottom torque-authority/inertia decile, shared with upstream; teachers competent there | the student is a lossy compressor; the tail is capacity or data balance, not labels |
| 09-02, §6.5 | teacher final vs best-of-10 snapshots: +34.8 ≈ the expected +37 of max-of-10 at eval sd 24; real signal: 69 teachers finish > 100 below their best, 15 below the gate | selection bias vs late collapse; price keep-best with a held-out re-eval |
| 09-02, §6.6 | shipped epoch 969 at 560.1 was a +2.4 sd draw of a 540.8 ± 8 plateau | argmax over epochs is selection on noise |
| 10-17, §6.7 | attitude-delay distill (`--obs-delay-max-ms 10 --obs-delay-channels imu`): delayed fault-switch settle 97.1 / 92.4 % vs 89.2 / 85.9 %; still-air unchanged; **kept** | train with the latency you will have |
| 10-17, §7.5 | SWA ranks 1st on all 3 runs, +4.8…+11.8 fleet mean; **kept** as a mandatory candidate | plateau averaging beats the pick |
| 10-18, §7.4 | relative-obs re-distill, 3 seeds: −2.0 (seed sd 2.6–4.3); **not kept** | a null result with its sd is a result |
| 10-18, §7.6 | hard-frame oversampling: tail 36.3 → 23 (SWA), fixes 9 of 38 tail frames, introduces 0; **kept**, default 1.0 | data balance moved the tail that capacity did not |
| 10-18, §7.7 | GRU 16 → 24: mean +11.8 but the same 35-frame tail; **not kept** | capacity bought body return, not the tail |
| 10-18, §8.0 | DAgger loop: period-2 oscillation (lag-2 > lag-1 in 5 of 7 runs); oversampling seeds have the highest plateau sd (10.4 / 9.9 vs 6.5–8.2); collect is 72 % of an epoch | the on-policy loop has a gain; weights raise it; damping levers pre-registered |
| 10-18, §8.1 | split protocol: rank-1 vs rank-2 margin ≈ 1 frame against a binomial sd ≈ 5; SWA recommended 4 of 8 | most selections are decided at 0.2 sd: treat as ties |
| 10-18, §8.2 | standing config (delay + oversampling + EMA): best fleet numbers ever (606.7 / 18) but the flight A4 gate misses on the pick, seed 1 kills | combining two kept levers is a new experiment; the gate, not the mean, decides |
| 10-23, STATUS | early stopping at 500k: 980 vs 985 passes, mean −12…−15; returns still rising to ~800k; not adopted | |

## 11. Open threads (2026-10-27)

- `verro-tracking.md` / `verro-lookahead.md`: the student cannot anticipate a moving reference because its
  memoryless teachers' labels depend only on the current error; the adopted plan is a no-GPU step 0, then
  a Langevin pilot of the reference acceleration (arms LA, LA′, LB at P=48) and the CHUNKREF pilot (A, A′, B, C),
  with A-vs-A′ as the noise floor and a fallback rule. Nothing has run on the GPU yet.
- PLAN item 22 (reduced oversampling with the delay lever) pre-registered after §8.2; M7 acceptance eval open.
- Replay side-store growth under a NaN-diverged member can OOM a P=64 wave (cap K is the follow-up).

## 12. Book ↔ aquila concordance

| Sutton & Barto | in aquila |
|---|---|
| 2.5 constant step size, tracking | Adam everywhere; `RLToolsAdam`'s floored second moment |
| 3.2 what-not-how reward | r = 1.5 − ‖p‖ − 0.1·orientation − ‖Δa‖; the `d_action` tax on the retrained style |
| 3.3–3.4 returns, γ, episodes vs continuing | γ 0.99 at 100 Hz; `terminated` vs `done`; truncations bootstrap (Pardo et al. 2018) |
| 4.6 GPI | SAC's actor/critic interleave (actor every 2nd step); DAgger's evaluate-on-student-states / improve-toward-labels |
| 5.5 off-policy, behaviour ≠ target | replay of a stochastic policy, deterministic eval (Sarsa-vs-Q cliff: evaluate what you deploy) |
| 6.1 TD(0) | the critic loss ½(Q − y)² |
| 6.6 Expected Sarsa | the soft target with the entropy term |
| 6.7 double learning | min(Q′₁, Q′₂) in the target |
| 9.2 μ-weighted objective | DAgger relabels the *student's* state distribution; hard-frame oversampling reweights μ toward the tail |
| 9.3 semi-gradient, target networks | polyak 0.995 targets; `no_grad` on y |
| 11.3 deadly triad | the guards: targets, clipped double-Q, replay ratio 1, Adam ε 1e-7 |
| 12.1 λ-return / BPTT horizon | 500-step BPTT sequences with h0 restarts |
| 13.5 actor–critic, 13.7 Gaussian policy | SAC actor with state-dependent log-std, tanh squash |
| 17.3 state from observations | the GRU student identifies the airframe from history (R² 0.94) |
| 17.4 reward design | lever verdicts by task metric (frames below gate, survival), never by return under a changed env |
