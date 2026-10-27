# Deep RL and robot learning after the book

What Sutton & Barto stop short of: the algorithms, the empirical findings and the failure modes that
decide a modern run. Each entry: the idea in one or two lines, the equation when it carries the point,
the primary citation (author year venue), and what breaks it. Facts newer than this file's last revision
(2026-10) must be web-checked; mark anything not opened "(unverified)" as robotics-research-brief does.

Contents: 1 Value-based · 2 On-policy policy gradient · 3 Off-policy actor–critic (DDPG/TD3/SAC) ·
4 Distributional · 5 Model-based · 6 Exploration · 7 Offline · 8 Imitation, distillation, teacher–student ·
9 Memory and partial observability · 10 Sim-to-real and robot learning · 11 Evaluation methodology ·
12 Reward design · 13 Training pathologies · 14 Choosing

## 1. Value-based (discrete actions)

- **DQN** (Mnih et al. 2015 Nature): Q-learning (S&B 6.5) + a conv net + two deadly-triad guards —
  experience replay (decorrelates, makes data near-i.i.d.) and a target network updated every C steps
  (slows the bootstrap). Huber loss, reward clipping to ±1 (a scale fix that changes the objective).
- **Double DQN** (van Hasselt, Guez, Silver 2016 AAAI): select with the online net, evaluate with the
  target net — S&B 6.7 at scale; fixes most overestimation. **Dueling** (Wang et al. 2016 ICML):
  Q = V + (A − mean A). **PER** (Schaul et al. 2016 ICLR): sample ∝ |δ|^α with IS weights β → 1;
  S&B 8.4. **n-step** returns (S&B 7.1) uncorrected. **NoisyNets** (Fortunato et al. 2018 ICLR).
  **Rainbow** (Hessel et al. 2018 AAAI) combines them; its ablation ranks PER, n-step and distributional
  as the load-bearing parts.
- **Distributed**: Ape-X (Horgan et al. 2018 ICLR), **R2D2** (Kapturowski et al. 2019 ICLR: LSTM
  policy, stored recurrent state + burn-in, n=5, no reward clipping but h(x) value rescaling),
  Agent57 (Badia et al. 2020 ICML).
- **Overestimation** is structural (Thrun & Schwartz 1993; van Hasselt 2010 NeurIPS Double Q-learning):
  max over noisy estimates. Continuous-action analogue: TD3's clipped double-Q (§3).
- Breaks on: long horizons with sparse reward (no exploration), large action spaces (max is intractable
  → policy methods), non-stationary data without a target net.

## 2. On-policy policy gradient (PPO family)

- **A3C/A2C** (Mnih et al. 2016 ICML): S&B 13.5 actor–critic with n-step returns, entropy bonus,
  parallel actors. **GAE** (Schulman et al. 2016 ICLR): Â_t = Σ (γλ)^l δ_{t+l}, the λ-return (S&B 12.1)
  applied to advantages; λ ≈ 0.95 trades bias for variance; the paper explicitly derives it from TD(λ).
- **TRPO** (Schulman et al. 2015 ICML): maximise the surrogate E[ρ_t Â_t] under a KL trust region,
  justified by the performance-difference lemma (Kakade & Langford 2002 ICML): J(π') − J(π) =
  E_{s∼d^{π'}}[E_{a∼π'} A^π(s,a)]/(1−γ); the surrogate replaces d^{π'} by d^π, valid only while π' is
  close.
- **PPO** (Schulman et al. 2017 arXiv): clipped surrogate L = E[min(ρ_t Â_t, clip(ρ_t, 1−ε, 1+ε) Â_t)],
  several epochs of minibatch SGD on the same batch, value loss, entropy bonus. What actually makes it
  work is implementation: Engstrom et al. 2020 ICLR ("Implementation Matters"), Andrychowicz et al.
  2021 ICLR ("What Matters in On-Policy RL", 250k runs: advantage normalisation, value clipping off,
  observation normalisation, tanh init, learning-rate ~3e-4, Adam ε), Huang et al. 2022 ICLR blog
  ("The 37 Implementation Details"). rsl_rl's PPO (Isaac Lab) adds adaptive LR on a desired KL
  (0.01) and clipped value loss.
- **Known theory gaps**: the γ^t factor dropped from the gradient (Nota & Thomas 2020 AAMAS: the
  resulting update is not the gradient of any objective), PPO's clipping is not a trust region
  (ratios can leave the clip range; Ilyas et al. 2020 ICLR), reusing samples across epochs is off-policy
  reuse with no correction beyond the clip.
- Breaks on: too few environment steps per update (advantage noise), reward scale (normalise returns or
  rewards, not observations alone), learning-rate/clip pairs that let the KL run away (watch
  `approx_kl`; Isaac Lab's adaptive schedule exists for this), value-function lag after a reward
  change (reset or re-warm the critic), action noise kept at deployment (Sarsa vs Q-learning lesson,
  S&B 6.5 cliff).

## 3. Off-policy actor–critic for continuous control (DDPG → TD3 → SAC)

- **DPG** (Silver et al. 2014 ICML): ∇J = E_{s∼ρ^β}[∇_a Q(s,a)|_{a=μ(s)} ∇_θ μ(s)]; the deterministic
  gradient needs no action-space integral and is off-policy by construction. **DDPG** (Lillicrap et al.
  2016 ICLR): DPG + DQN's guards + Polyak-averaged targets θ' ← τθ + (1−τ)θ' + OU exploration noise.
  Brittle: overestimation feeds the actor, which exploits the critic's errors.
- **TD3** (Fujimoto, van Hoof, Meger 2018 ICML): (1) clipped double-Q: y = r + γ min(Q'_1, Q'_2)(s', ã);
  (2) target policy smoothing: ã = μ'(s') + clip(ε, −c, c); (3) delayed actor updates (every d=2 critic
  steps). The three guards most later methods keep.
- **SAC** (Haarnoja et al. 2018 ICML; v2 with automatic temperature: Haarnoja et al. 2018 arXiv
  "Soft Actor-Critic Algorithms and Applications"): maximum-entropy objective J = Σ E[r + α H(π(·|s))].
  Soft Bellman target y = r + γ(1 − d)[min_i Q'_i(s', a') − α log π(a'|s')], a' ∼ π(·|s');
  critic loss ½(Q − y)²; actor loss E[α log π(a|s) − min_i Q_i(s,a)] with the reparameterised
  a = tanh(μ + σ ε); tanh log-prob correction log π(a|s) = log N(u) − Σ log(1 − tanh(u)²);
  temperature loss J(α) = E[−α (log π(a|s) + H̄)] with target entropy H̄ = −dim(A). Lineage: soft
  Q-learning (Haarnoja et al. 2017 ICML), max-ent IRL (Ziebart et al. 2008 AAAI). aquila's teachers
  are exactly this recipe as transcribed from rl-tools (`aquila-map.md` §2: the entropy bonus in the
  target is unconditional, actor every 2nd step, polyak 0.995, log α init log 0.5).
- **Which to use**: SAC for sample-efficient continuous control with modest action dims; TD3 when the
  entropy term hurts (precise control, where the stochastic policy's noise is the problem); PPO when
  the simulator is cheap and massively parallel (Isaac Lab), since wall-clock beats sample efficiency
  there (Rudin et al. 2021 CoRL).
- Breaks on: temperature collapse or runaway (watch α and the policy entropy; a target entropy of −|A|
  is a heuristic, not a law; aquila's `log_alpha` is in every teacher file), critic divergence late in
  training (aquila §6.5: 69 of 1000 teachers finished > 100 below their best; 15 below the gate),
  reward scale (SAC is sensitive: the entropy term is in reward units), action bounds (tanh squashing
  + the Jacobian term is not optional), replay ratio > 1 without resets (§13).

## 4. Distributional RL

- **C51** (Bellemare, Dabney, Munos 2017 ICML): learn the return distribution Z on a fixed support
  (categorical projection of the Bellman target). **QR-DQN** (Dabney et al. 2018 AAAI: quantile
  regression, Huber-quantile loss), **IQN** (Dabney et al. 2018 ICML: implicit quantiles), **D4PG**
  for continuous control (Barth-Maron et al. 2018 ICLR). The distributional Bellman operator is a
  contraction in Wasserstein for evaluation but the control case is subtler (Bellemare et al. book
  2023, *Distributional RL*, MIT Press).
- Why it helps is still debated (representation richness, auxiliary-task effect: Lyle, Bellemare,
  Castro 2019 AAAI); in Rainbow's ablation it matters late in training.

## 5. Model-based RL

- The Dyna picture (S&B 8.2) at scale. **PILCO** (Deisenroth & Rasmussen 2011 ICML, GP dynamics,
  analytic policy gradients), **PETS** (Chua et al. 2018 NeurIPS: probabilistic ensembles + CEM/MPC;
  the ensemble separates aleatoric from epistemic error), **MBPO** (Janner et al. 2019 NeurIPS: short
  k-step model rollouts branched from real states into SAC's replay; the monotone-improvement bound
  degrades with rollout length, hence k small), **PlaNet** (Hafner et al. 2019 ICML) → **Dreamer**
  (Hafner et al. 2020 ICLR; v2 2021 ICLR; **v3** 2023 arXiv / 2025 Nature: symlog, free-bits KL,
  percentile return normalisation, one set of hyperparameters across 150 tasks), **MuZero**
  (Schrittwieser et al. 2020 Nature: value-equivalent latent model + MCTS), **TD-MPC2** (Hansen et al.
  2024 ICLR).
- When the model is wrong (S&B 8.3) is still the issue: exploitation of model errors by the planner;
  ensembles, short horizons and pessimism (MOPO/MOReL for offline) are the standard guards. For a
  robot with a cheap, faithful simulator (aquila's L2F port, Isaac Lab), the simulator *is* the model,
  and model-free on it is the pragmatic choice.

## 6. Exploration

- ε-greedy and Gaussian action noise are the defaults and are usually enough with dense reward.
- **Count-based** and pseudo-counts (Bellemare et al. 2016 NeurIPS), **ICM** (Pathak et al. 2017
  ICML, prediction-error curiosity; the noisy-TV problem), **RND** (Burda et al. 2019 ICLR: predict a
  fixed random net; the robust default for sparse-reward exploration), **bootstrapped DQN** (Osband et
  al. 2016 NeurIPS: deep exploration via an ensemble of heads; the Thompson-sampling view),
  **Go-Explore** (Ecoffet et al. 2021 Nature: archive, return, explore).
- Entropy regularisation (SAC) is exploration by objective, not by bonus; it also smooths the
  landscape (Ahmed et al. 2019 ICML).
- Breaks on: bonuses that outlive their use (anneal them), intrinsic reward swamping the task reward
  (normalise), curiosity on stochastic observations.

## 7. Offline (batch) RL

- The deadly triad plus **extrapolation error**: bootstrapping from actions the dataset never shows.
  **BCQ** (Fujimoto et al. 2019 ICML), **CQL** (Kumar et al. 2020 NeurIPS: push down Q on
  out-of-distribution actions), **IQL** (Kostrikov et al. 2022 ICLR: expectile regression, never
  queries OOD actions), **TD3+BC** (Fujimoto & Gu 2021 NeurIPS: one BC term is most of the benefit),
  **Decision Transformer** (Chen et al. 2021 NeurIPS: return-conditioned sequence modelling).
  Tutorial: Levine et al. 2020 arXiv.
- Off-policy *evaluation* (OPE) is S&B 5.5 with all its variance; doubly-robust estimators (Jiang & Li
  2016 ICML) and fitted Q evaluation are the standard tools. A distillation dataset (DAgger's) is an
  offline dataset with a teacher oracle attached — the extrapolation problem is why DAgger relabels
  the *student's* states instead of training on the teacher's.

## 8. Imitation, distillation and teacher–student

- **Behaviour cloning** compounds error: with per-step error ε the T-step cost is O(T² ε) because the
  student drifts to states the expert never visited (Ross & Bagnell 2010 AISTATS). **DAgger** (Ross,
  Gordon, Bagnell 2011 AISTATS): iterate — roll out the mixture π_i = β_i π* + (1 − β_i) π̂_i, label the
  visited states with the expert, aggregate, retrain; a no-regret reduction with O(T ε) cost. β_1 = 1
  (pure expert, "teacher forcing"), then β_i → 0 fast; the original uses β_i = p^{i−1} or β_i = 1{i=1}.
  aquila: 10 teacher-forcing epochs then 990 student-driven epochs, labels from the per-frame teacher
  (`aquila-map.md` §6). Its instability mode: the on-policy loop oscillates with period 2 (the student
  trained on epoch k's states is different at epoch k+1, so the state distribution flips) — measured
  in aquila EVIDENCE §8.0 (lag-2 autocorrelation > lag-1 on 5 of 7 runs); damping levers are
  dataset windows across epochs, LR decay, EMA of the student.
- **Policy distillation** (Rusu et al. 2016 ICLR: many teachers → one student, KL on action
  distributions), **GAIL** (Ho & Ermon 2016 NeurIPS: adversarial occupancy matching), **privileged
  teacher–student** (Chen et al. 2019 CoRL "Learning by Cheating"; Lee et al. 2020 Science Robotics
  for quadruped locomotion: teacher sees ground truth, student sees sensors + history; **RMA**, Kumar
  et al. 2021 RSS: a latent of the privileged params regressed from history), **asymmetric
  actor–critic** (Pinto et al. 2018 RSS: privileged critic, deployable actor — the cheap version when
  only training needs the privileged info).
- **Foundation policies for control**: RAPTOR (Eschmann et al. 2025 arXiv, rl-tools; the recipe aquila
  reproduces — 1000 SAC teachers on sampled dynamics, DAgger into a GRU(16) student that identifies
  the airframe from history; the student's latent recovers thrust-to-weight at R² ≈ 0.94–0.95).
- **Standing lessons from aquila** (details and numbers in `aquila-map.md` §10):
  - The student is a lossy compressor: ~3 % of airframes are sacrificed by the shared representation,
    on a fixed low-authority tail that the teachers handle; capacity (GRU 16 → 24) moved the mean but
    not the tail; oversampling the hard frames did move the tail.
  - A student cannot be taught past its labels, but can generalise past them: the GRU student beats its
    memoryless teachers under a rotor fault (517.8 vs 371.4 at 0.3) with no fault labels. Exposing it to
    faults on which the clean teachers flail made it *worse* at faults at every level (clean-bank 0.2
    pilot: −38 / −121). Retraining teachers on the harder env fixed the labels there but taxed the style
    everywhere (d_action penalty on inherited busyness), and that cost transferred through distillation
    while the thin benefit did not survive 2× imitation error (A3/A3b: −59…−82).
  - Observation noise during distillation was the one big win (+147 @ trained magnitude, +288 held-out;
    without it 705/1000 frames fail under sensor noise): the GRU "learned to filter, not react".
    Constant per-episode bias was dead weight (position hold absorbs it).
  - Selecting the shipped student by argmax over epochs picked a +2.4 sd draw; plateau averaging
    (SWA/EMA) ranked first on most runs and held-out selection replaced the argmax.

## 9. Memory and partial observability

- S&B 17.3 in practice: a recurrent policy learns a state update. **DRQN** (Hausknecht & Stone 2015
  AAAI fall symp.), **R2D2** (stored hidden state + burn-in beats zero-init), **Ni, Eysenbach,
  Salakhutdinov 2022 ICML** ("Recurrent model-free RL can be a strong baseline for many POMDPs":
  separate actor and critic RNNs, long context, careful tuning beats specialised methods).
- **BPTT truncation** and **teacher forcing** matter: aquila trains the GRU student on sequences of
  500 steps with hidden state restarted at episode boundaries, batch 64, one cuDNN call per
  reset-free interval. Memory is what performs implicit system identification (RMA, RAPTOR): the
  domain-randomised parameter must stay *constant within an episode* for the memory to identify it
  (DR timescale rule, §10).
- Pitfalls: feeding the policy its own previous action makes a delayed observation of it part of the
  state (aquila §6.1: delaying "all 22 dims" overstated the latency problem because it also delayed
  the previous action); a Markov critic on a POMDP is a biased bootstrap target (use a recurrent or
  privileged critic).

## 10. Sim-to-real and robot learning

- **Domain randomisation** (Tobin et al. 2017 IROS, visual; Peng et al. 2018 ICRA, dynamics;
  OpenAI 2019 ADR for the Rubik's cube), **actuator nets / latency modelling** (Hwangbo et al. 2019
  Science Robotics, ANYmal), **massively parallel GPU sim** (Makoviychuk et al. 2021 Isaac Gym;
  Rudin et al. 2021 CoRL: minutes to a walking policy), **quadrotors**: Molchanov et al. 2019 IROS
  (sim-to-multi-real), Kaufmann et al. 2023 Nature (Swift, champion-level racing), Song et al. 2023
  Science Robotics (RL vs optimal control: RL wins by optimising the true objective, not a proxy),
  RAPTOR (above).
- **DR timescale rule** (aquila EVIDENCE §2): per-step for fast exogenous noise (sensor/action noise,
  gusts), per-episode-constant for structural parameters the memory must identify (mass, motor time
  constant, drag, bias, rotor fault). Per-step structural jitter destroys the sysID signal.
- **Latency is the usual sim-only killer**: a memoryless high-gain inner loop has no phase margin. In
  aquila one 10 ms IMU frame of delay on attitude + gyro cost ~25 % of episodes even from rest;
  position/velocity channels tolerated 30 ms; a heavy velocity low-pass filter (IIR 0.9 at 100 Hz) is
  a delay in disguise and halved survival; a 400 Hz re-evaluation executor bought 5 ms for free.
  Train with the delay (aquila's attitude-delay lever, kept) and measure the real gyro → motor budget
  before flight.
- **Taxonomy of levers** (aquila §2): P0 = distill-time only, valid inside the teachers' competence
  envelope (measure that first with a competence sweep); P1/P2 = transition-function changes that need
  a teacher retrain, batched into one campaign. Keep the faithful path byte-identical with the lever
  off (guard the term, never multiply by zero) so every lever has a clean A/B.
- Where DR does not pay: drag for a low-speed hover mission (the return gate was blind to it and the
  drag-trained student overshot more).

## 11. Evaluation methodology

- **Henderson et al. 2018 AAAI** ("Deep RL that Matters"): seeds, code-level choices and reporting
  swamp algorithmic differences; 5 seeds of the same algorithm can look like two different algorithms.
  **Colas, Sigaud, Oudeyer 2018 arXiv**: how many seeds (power analysis; 2 seeds cannot decide).
  **Agarwal et al. 2021 NeurIPS** ("Deep RL at the edge of the statistical precipice"): report the
  **IQM** with stratified bootstrap CIs, performance profiles and probability of improvement, not the
  mean/median of a handful of runs (`compare_arms.py compare` prints IQM, bootstrap CI, P(b > a)).
  **Jordan et al. 2020 ICML**, **Patterson et al. 2024 JMLR** ("Empirical design in RL"): the
  checklist for an honest comparison.
- **Selection bias**: the expected maximum of N normal draws is +0.56σ (N=2), +1.16σ (N=5), +1.54σ
  (N=10), +2.07σ (N=32) above the mean (`compare_arms.py max-of-n`). aquila's "final vs best-of-10
  checkpoint" gap of +34.8 at eval sd ≈ 24 was almost exactly this (+37 expected): the real signal
  was the sub-300 tail, not the mean. Select on one held-out set, report on another (aquila's
  t2i-stratified split), and compare picks only against picks made the same way.
- **One variable per run**; an A-vs-A′ pair (same arm, new seed) gives the noise floor a lever must
  clear; pre-register the gate and the kill rule before the run (aquila's PLAN items and A4 gates);
  a confounded run gets a Confounded line and the verdict judges the bundle (rl-experiment-log).
- **Metric**: a task metric independent of the shaped reward (success rate, tracking error, frames
  below a fixed gate), never the training return when reward weights differ between arms.

## 12. Reward design

- **Potential-based shaping** (Ng, Harada, Russell 1999 ICML): F(s, s') = γΦ(s') − Φ(s) is the only
  shaping that preserves the optimal policy; anything else can change what is optimal. S&B 3.2/17.4.
- **Specification gaming / reward hacking** (Amodei et al. 2016 arXiv; Skalse et al. 2022 NeurIPS
  formal definition): the agent optimises the reward you wrote, not the one you meant. Action-rate and
  energy penalties are the usual regularisers in control and carry their own tax (aquila: ≈ 35 of a
  −60 return gap was the d_action term charging an inherited busy style).
- Practical rules: sparse task term + a few dense terms with physical units; log each term's
  contribution (Isaac Lab multiplies term × weight before logging, so never compare Episode_Reward
  across weight changes); curriculum the *difficulty*, not the reward; normalise returns rather than
  rewrite them; when a term changes, the task metric decides.

## 13. Training pathologies (names to search by)

- **Overestimation** (Thrun & Schwartz 1993) → double/clipped critics, smaller γ, target smoothing.
- **Primacy bias / plasticity loss** (Nikishin et al. 2022 ICML; Lyle et al. 2022 ICLR capacity loss;
  Sokar et al. 2023 ICML dormant neurons; D'Oro et al. 2023 ICLR: high replay ratios need periodic
  resets; Schwarzer et al. 2023 ICML BBF): networks trained long on early data stop learning;
  resets, layer norm, weight decay, smaller replay ratio.
- **Policy churn** (Schaul et al. 2022 arXiv): greedy actions change on many states after each update;
  a reason policy-gradient updates are smoother (S&B 13.1).
- **Entropy collapse** (SAC α → 0, PPO entropy → 0): exploration ends; fix the target entropy or
  entropy coefficient, check reward scale.
- **Late collapse** of an otherwise converged run (aquila §6.5: 69/1000 SAC teachers finished > 100
  below their best): keep snapshots, re-evaluate the top ones on fresh seeds before trusting
  "keep best" (the gain is mostly selection bias otherwise).
- **Value-function lag after a change** (reward, observation or curriculum stage): the critic's
  targets move; expect a dip; re-warm.
- **Time limits treated as terminals** (Pardo et al. 2018 ICML): bootstrapping must continue through a
  truncation and stop only at a true terminal; conflating `done` with `terminated` biases every value.
- **Action chatter** under sensor noise when noise was not in training (aquila: action rate
  0.007 → 0.70 without noise training vs 0.039 with).
- **Non-finite states** in a vectorised sim poisoning masked statistics (NaN·0 = NaN): use `where`,
  not multiplication, for masking (aquila's offset estimator bug).
- **Numerics that change results**: TF32 defaults in cuDNN/cuBLAS, Adam ε placement (rl-tools floors
  the second moment at 1e-7 inside the sqrt: small-gradient steps are much smaller than torch Adam's),
  GEMM grouping differences at the ulp level that break bit-reproducibility across code versions.

## 14. Choosing (defaults, to be overridden by evidence in the repo)

| situation | start with | because |
|---|---|---|
| cheap, massively parallel sim (Isaac Lab), dense reward | PPO + GAE (rsl_rl defaults; Rudin 2021) | wall-clock, robustness to hyperparameters |
| per-step-expensive sim or real data, continuous actions | SAC (auto-α) or TD3 | sample efficiency; replay |
| many dynamics variants → one deployable policy | per-variant teachers (SAC/PPO) → DAgger into a memory student (RAPTOR / RMA) | the student identifies the variant from history |
| partial observability | recurrent actor (+ recurrent or privileged critic) | S&B 17.3; Ni 2022 |
| sparse reward | RND or count bonus, or reshape the task (curriculum, sub-goals as options) | §6 |
| only logged data | IQL / TD3+BC; evaluate with OPE and a small online check | §7 |
| discrete actions, pixels | Rainbow / R2D2 (memory) | §1 |
| need a planner at decision time | MCTS over a learned or given model (MuZero / AlphaZero) | S&B 8.11 |
| a result that must be trusted | ≥ 3 seeds per arm, held-out eval seed, IQM + bootstrap CI, pre-registered gate | §11 |
