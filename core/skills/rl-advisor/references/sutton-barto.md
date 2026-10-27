# Sutton & Barto, *Reinforcement Learning: An Introduction*, 2nd ed. (MIT Press, 2018)

A working digest, not a replacement for the book: what each chapter establishes, the equations that carry
the point, the insight a practitioner should take, and the misreadings that cost runs. Section numbers are
the 2nd edition's. Equations are in the book's notation (table below). Starred sections (*) are the
book's own "optional on first reading" marks. The PDF is free at incompleteideas.net/book/the-book-2nd.html.

Contents: Notation · Part I (Ch 1–8, tabular) · Part II (Ch 9–13, approximation) · Part III (Ch 14–17)
· Reading paths · Chapter → deep-RL practice map

## Notation (Ch 3, summary of notation in the front matter)

| symbol | meaning |
|---|---|
| S_t, A_t, R_{t+1} | state, action at t; reward received after A_t (the +1 is deliberate: R_{t+1} and S_{t+1} are produced together) |
| p(s', r \| s, a) | the dynamics: a joint distribution over next state and reward; the MDP is fully specified by it |
| π(a \| s) | policy; π_* an optimal one |
| G_t = Σ_{k=0}^{∞} γ^k R_{t+k+1} | return; episodic tasks end at T with a zero-reward absorbing state (3.4 unifies the two) |
| v_π(s) = E_π[G_t \| S_t = s] ; q_π(s, a) | state and action value functions; v_*, q_* the optimal ones |
| δ_t = R_{t+1} + γ V(S_{t+1}) − V(S_t) | TD error (6.1); the one quantity every bootstrapping method is built from |
| α | step size; constant α = exponential recency weighting (2.5) |
| ε, ε-greedy, ε-soft | exploration (2.2, 5.4) |
| ρ_{t:T−1} = Π π(A_k \| S_k)/b(A_k \| S_k) | importance-sampling ratio of target π over behaviour b (5.5) |
| λ | trace-decay / λ-return mixing (12.1) |
| w, x(s), v̂(s, w) | weight vector, feature vector, approximate value (9.1) |
| θ, π(a \| s, θ), J(θ) | policy parameters and the performance objective (13.1) |
| μ(s) | on-policy state distribution: the weighting in the prediction objective (9.2) and in the policy gradient theorem (13.2) |

Capital letters are random variables, lower case their values or deterministic functions; the book is
strict about this and it pays off when reading importance-sampling and policy-gradient derivations.

---

## Part I — Tabular solution methods

### Ch 1 Introduction

- **Four elements** (1.3): policy, reward signal, value function, optionally a model. RL is defined by the
  problem (closed-loop, no supervisor, delayed consequences, trade-off between exploration and
  exploitation), not by a method.
- **Insight**: the reward signal defines *what* is wanted; the value function is what decisions are made
  from; "the most important component of almost all RL algorithms is a method for efficiently estimating
  values." Tic-tac-toe (1.5) already shows TD: V(S_t) ← V(S_t) + α[V(S_{t+1}) − V(S_t)].
- 1.7 history: the three threads that merged (trial-and-error learning from psychology, optimal control /
  DP from Bellman 1957, temporal-difference methods from Samuel, Klopf, Sutton & Barto).

### Ch 2 Multi-armed bandits — the exploration problem in isolation

- Sample-average estimate and the **general incremental form** (2.4):
  NewEstimate ← OldEstimate + StepSize · [Target − OldEstimate]. Every learning rule in the book is an
  instance of this.
- **Step sizes** (2.5): sample averages (α_n = 1/n) are right for stationary problems; a constant α tracks a
  nonstationary one with exponential recency weighting. Convergence (stochastic approximation) needs
  Σ α_n = ∞ and Σ α_n² < ∞; constant α violates the second on purpose. Deep RL always uses constant steps,
  i.e. it is always tracking.
- **Optimistic initial values** (2.6): a one-shot exploration trick for stationary problems; bias of the
  initial estimate with constant α never fully disappears ("the initial estimate is a parameter").
- **UCB** (2.7): A_t = argmax_a [ Q_t(a) + c √(ln t / N_t(a)) ] — uncertainty as a bonus; hard to extend
  beyond bandits but the ancestor of count-based exploration and MCTS's UCT.
- **Gradient bandit** (2.8): action preferences H_t(a), softmax policy, update
  H_{t+1}(a) = H_t(a) + α (R_t − R̄_t)(1{a=A_t} − π_t(a)). The baseline R̄_t does not change the expected
  update, only its variance — the first appearance of the REINFORCE baseline argument (13.4).
- **Associative search / contextual bandits** (2.9) is the bridge to the full problem: actions now also
  change the situation.
- **Pitfall**: the parameter study (Fig 2.6) is the model for honest comparisons — each method at its best
  parameter, on a log axis, with the same budget. Compare methods, not one method's tuned run against
  another's default.

### Ch 3 Finite Markov decision processes — the problem

- The **dynamics** p(s', r | s, a) (3.1) and what follows from it: state-transition probabilities, expected
  rewards. The Markov property is a property of the *state signal*, and the state is whatever the agent
  is given; a bad state representation makes a problem non-Markov without changing the world (17.3).
- **The reward hypothesis** (3.2): all goals can be expressed as maximisation of expected cumulative scalar
  reward. The design rule that follows: "the reward signal is your way of communicating to the agent
  *what* you want achieved, not *how* you want it achieved" — put the how in the initial policy or value
  function, not in the reward. Sub-goal rewards get exploited (the chess example: reward taking pieces
  and it will take pieces and lose).
- **Returns and discounting** (3.3): G_t = R_{t+1} + γ G_{t+1}, bounded by r_max/(1−γ). 1/(1−γ) is the
  effective horizon (γ = 0.99 → 100 steps; `compare_arms.py horizon`). Discounting is a problem
  formulation choice in episodic tasks and a mathematical convenience in continuing ones (see 10.4).
- **Bellman expectation equation** (3.5): v_π(s) = Σ_a π(a|s) Σ_{s',r} p(s',r|s,a)[r + γ v_π(s')] —
  a consistency condition that the true value function uniquely satisfies; backup diagrams are the
  visual language for every algorithm (how deep, how wide, sample or expected).
- **Bellman optimality** (3.6): v_*(s) = max_a Σ_{s',r} p(s',r|s,a)[r + γ v_*(s')],
  q_*(s,a) = Σ p(s',r|s,a)[r + γ max_{a'} q_*(s',a')]. Any policy greedy w.r.t. v_* is optimal;
  with q_* no model is needed for the greedy step — this is why model-free control learns q, not v.
- **Optimality and approximation** (3.7): optimal policies are never computed in practice; the point of RL
  is spending approximation effort on the states that matter (the on-policy distribution), which is the
  argument behind on-policy objectives in Part II.

### Ch 4 Dynamic programming — what you would do with the model

- **Iterative policy evaluation** (4.1): the Bellman equation as an update rule; the operator is a
  γ-contraction in the max norm, hence convergence from any start (the theory that Q-learning and TD
  inherit).
- **Policy improvement theorem** (4.2): if q_π(s, π'(s)) ≥ v_π(s) for all s then v_π' ≥ v_π; greedy
  w.r.t. v_π is a strict improvement unless already optimal. Policy iteration (4.3), value iteration (4.4,
  one sweep of evaluation then improvement, which is the Bellman optimality backup), asynchronous DP (4.5).
- **Generalized policy iteration** (4.6): nearly every RL method is evaluation and improvement processes
  interacting, each moving the other's target. Keep this picture: it explains why actor-critic needs the
  critic to track a moving policy and why too-fast improvement on a stale critic diverges.
- **Efficiency** (4.7): DP is polynomial in |S| and |A|; "the curse of dimensionality" is a property of the
  problem, not of DP. Bootstrapping is DP's gift to RL; the cost is bias when the estimates are wrong.

### Ch 5 Monte Carlo methods — learning from complete returns

- **First-visit vs every-visit MC** (5.1): unbiased, variance ∝ return variance, needs episodes to end,
  no bootstrapping, so no bias from other estimates and *no Markov requirement* — MC is the fallback when
  the state is badly non-Markov.
- **Exploring starts** (5.3) and **ε-soft on-policy control** (5.4): the first time the book has to
  solve exploration for control; ε-greedy improvement is still an improvement in the ε-soft class.
- **Off-policy prediction via importance sampling** (5.5): ordinary IS (unbiased, unbounded variance)
  vs weighted IS (biased, consistent, far lower variance; what everyone uses). The variance of
  ρ_{t:T−1} grows multiplicatively with the horizon: long off-policy trajectories are the root of the
  variance problems in Retrace/V-trace, and the reason deep off-policy methods bootstrap after one step
  instead of correcting whole trajectories.
- **Off-policy MC control** (5.7), discounting-aware (5.8*) and **per-decision IS** (5.9*): only the
  ratio up to the reward's own time step matters for that reward, which lowers variance and is the idea
  behind per-decision corrections.

### Ch 6 Temporal-difference learning — the core idea

- **TD(0)** (6.1): V(S_t) ← V(S_t) + α δ_t with δ_t = R_{t+1} + γ V(S_{t+1}) − V(S_t). A sample backup of
  one step, bootstrapped: MC's sampling plus DP's bootstrapping. The MC error is a sum of TD errors
  (eq. 6.6 in 6.1: G_t − V(S_t) = Σ γ^{k−t} δ_k when V is held fixed), which is what makes traces (Ch 12) work.
- **Why TD** (6.2–6.3): online, incremental, works in continuing tasks, usually faster in practice; under
  batch training TD(0) converges to the *certainty-equivalence* estimate (the value of the maximum-
  likelihood MDP), MC to the least-squares fit of the returns — TD exploits the Markov structure, MC does
  not. Example 6.4 (You are the predictor) is the cleanest intuition for the whole bias/variance debate.
- **Sarsa** (6.4, on-policy): Q(S,A) ← Q(S,A) + α[R + γ Q(S',A') − Q(S,A)], A' from the policy being
  improved.
- **Q-learning** (6.5, off-policy): Q(S,A) ← Q(S,A) + α[R + γ max_a Q(S',a) − Q(S,A)], learns q_*
  regardless of the behaviour policy (if it keeps visiting). Cliff walking (Example 6.6): Q-learning
  learns the optimal path and falls off the cliff while exploring; Sarsa learns the safe path because it
  accounts for its own exploration — on-policy methods learn the value of *the policy actually run*,
  including its noise, which matters whenever the deployed policy keeps the noise.
- **Expected Sarsa** (6.6): target R + γ Σ_a π(a|S') Q(S',a); lower variance than Sarsa, generalises
  Q-learning (π greedy); the expected-target idea reappears in SAC's soft target and in tree backup.
- **Maximization bias and Double learning** (6.7): max over noisy estimates is biased upward; keep two
  estimates, select with one, evaluate with the other. Double Q-learning → Double DQN, clipped double-Q in
  TD3/SAC. If a critic overestimates, this section is the first place to look.
- **Afterstates** (6.8): when the deterministic effect of an action is known (board games), value the
  position after the move; many board/game problems are exactly this.

### Ch 7 n-step bootstrapping — the dial between TD and MC

- **n-step return** (7.1): G_{t:t+n} = R_{t+1} + … + γ^{n−1} R_{t+n} + γ^n V_{t+n−1}(S_{t+n}). The
  error-reduction property: the expected n-step return is a better estimate of v_π than V in the worst
  case by a factor γ^n. Intermediate n is usually best (Fig 7.2): neither 1 nor ∞. In deep RL n-step
  targets (Rainbow n=3, R2D2 n=5) and GAE's λ are this dial.
- **n-step Sarsa** (7.2); **n-step off-policy** with IS ρ_{t+1:t+n} (7.3): the ratio excludes A_t for
  action values (the first action is the one being evaluated). Control variates (7.4*) reduce the
  variance; **tree backup** (7.5) does off-policy n-step with no IS at all by taking expectations over
  the untaken branches (the basis of Retrace's safe behaviour); Q(σ) (7.6*) unifies them.
- **Pitfall**: an n-step target computed from an off-policy replay without correction is a biased
  estimate of the current policy's value; it works in practice (Rainbow, R2D2) because n is small and
  the policy changes slowly, not because it is correct. Say so when asked.

### Ch 8 Planning and learning with tabular methods — models

- **Dyna-Q** (8.2): real experience updates both the value function and a model; simulated experience
  from the model updates the value function more. Planning = updating values from the model; learning
  and planning share the same update. The modern descendants: MBPO (short model rollouts into a
  replay), Dreamer (imagination), MuZero (search).
- **When the model is wrong** (8.3): Dyna-Q+ adds an exploration bonus κ√τ for long-unvisited
  transitions; model errors that make the model optimistic are self-correcting, pessimistic ones are
  not (the agent never checks). Same asymmetry in learned world models.
- **Prioritized sweeping** (8.4): work backwards from large changes — prioritised replay is the deep
  cousin (with the caveat that priorities measured by TD error are noisy and bias the sampling).
- **Expected vs sample updates** (8.5): with branching factor b, a sample update costs 1/b of an expected
  one and is nearly as good after b samples; sample updates win when b is large or compute-limited.
- **Trajectory sampling** (8.6): on-policy distribution of updates focuses work on reachable states; wins
  early, loses late (the states it ignores stay wrong).
- **Real-time DP** (8.7); **decision-time planning** (8.8): heuristic search (8.9), rollout algorithms
  (8.10: Monte Carlo value estimates of each action under a rollout policy, then act greedily — a form of
  policy improvement), **MCTS** (8.11: selection by a tree policy such as UCT, expansion, rollout,
  backup; the search tree is a decision-time, focused value function).
- **8.13 Summary of Part I**: the dimensions of methods — depth of the update (one-step → full return),
  width (sample → expected), on/off-policy, with/without a model. Place any new algorithm in this cube
  before judging it.

---

## Part II — Approximate solution methods

### Ch 9 On-policy prediction with approximation

- **The prediction objective** (9.2): mean squared value error VE(w) = Σ_s μ(s)[v_π(s) − v̂(s,w)]², with
  μ the on-policy distribution. There is no way to be accurate everywhere; μ says where to be accurate.
  Minimising VE is not even guaranteed to give the best policy; it is the tractable surrogate.
- **Semi-gradient TD(0)** (9.3): w ← w + α [R + γ v̂(S',w) − v̂(S,w)] ∇v̂(S,w). "Semi" because the
  target's dependence on w is ignored. Not a true gradient of any objective; converges for linear FA
  on-policy to the TD fixed point w_TD, whose error is bounded by 1/(1−γ) times the best possible
  (9.4) — the bound is loose and the factor is the price of bootstrapping.
- **Features** (9.5): polynomial, Fourier, coarse coding, tile coding (the book's workhorse; generalisation
  is set by tile shape and number of tilings), RBFs. **Step size for linear FA** (9.6): α = (τ E[xᵀx])⁻¹
  to learn in about τ presentations — the one principled step-size heuristic in the book.
- **ANNs** (9.7): backprop as the gradient; the book flags the deadly-triad risk and that deep nets with
  TD are an empirical matter. LSTD (9.8, O(d²), no step size, no bootstrapping bias in the limit),
  memory-based (9.9) and kernel methods (9.10), **interest and emphasis** (9.11: weight updates by how
  much you care about each state; the seed of emphatic TD).

### Ch 10 On-policy control with approximation

- **Episodic semi-gradient Sarsa** (10.1) with q̂(s,a,w); Mountain Car with tile coding (Example 10.1),
  and the n-step version (10.2) — n > 1 helps here too.
- **Average reward** (10.3): for continuing tasks with FA, replace discounting by the differential return
  G_t = Σ (R_{t+k+1} − r(π)); the differential TD error δ_t = R_{t+1} − R̄_t + v̂(S_{t+1}) − v̂(S_t).
- **Deprecating the discounted setting** (10.4): with function approximation and an on-policy
  distribution, the discounted objective is equivalent to the average-reward one up to a constant factor
  for *ranking policies* in the on-policy case, so γ is not really a free parameter of the problem; and the
  policy improvement theorem is lost under FA anyway. The field ignores this (every deep baseline uses
  γ ∈ [0.97, 0.995]) because discounting is a variance/horizon knob that works; when asked, give both:
  the theory says average reward, the practice says γ as a horizon hyperparameter and treat it as one.

### Ch 11 Off-policy methods with approximation — where things break

- **Semi-gradient off-policy TD** with ρ_t (11.1); works often, diverges sometimes.
- **Baird's counterexample** (11.2): linear FA, off-policy updates, a perfectly representable value
  function, and the weights diverge to infinity. Not a step-size problem.
- **The deadly triad** (11.3): instability arises when all three are present — (1) function
  approximation, (2) bootstrapping, (3) off-policy training. Remove any one and stability returns:
  MC targets (no bootstrapping), tabular/on-policy… Deep off-policy RL (DQN, SAC) lives inside the triad
  and is stabilised empirically: target networks (slow the bootstrap), replay with near-on-policy data
  (bounded off-policy-ness), small learning rates, double/clipped critics, gradient clipping, low
  replay ratios. Every "why did my Q explode" starts here.
- **Linear value-function geometry** (11.4): the four errors and their relations — VE (true value
  error), BE (Bellman error), PBE (projected Bellman error; TD's fixed point zeros it), TDE. **Residual
  gradient** on the BE needs double sampling (11.5) and **the BE is not learnable** from data (11.6):
  two MDPs with identical observable data can have different BE minimisers. So "just minimise the
  Bellman residual" is not the fix it sounds like.
- **Gradient-TD** (11.7: GTD2, TDC — true SGD on the PBE, provably convergent off-policy, slower) and
  **emphatic TD** (11.8: reweight by the followed-interest emphasis M_t, convergent in expectation).
  Neither is common in deep RL; cite them when someone needs provable off-policy stability.
- **Reducing variance** (11.9): weighted IS, tree backup, per-decision ratios; the book's honest close:
  off-policy learning with FA is unsolved in general.

### Ch 12 Eligibility traces — the λ dial done efficiently

- **λ-return** (12.1): G_t^λ = (1−λ) Σ_{n≥1} λ^{n−1} G_{t:t+n}, a geometric mix of all n-step returns;
  λ = 0 is TD(0), λ = 1 is MC. The *forward view*: what you would compute offline. GAE is exactly a
  λ-return on advantages (Schulman 2016 cites this chapter).
- **TD(λ)** (12.2): the *backward view*: an eligibility trace z_t = γλ z_{t−1} + ∇v̂(S_t, w) and
  w ← w + α δ_t z_t. Each state's credit for the current TD error decays with recency and frequency;
  equivalent to the forward view offline. Figs 12.3 and 12.6: intermediate λ wins, as with n.
- **Truncated λ-return** (12.3), **online λ-return** (12.4), **true online TD(λ)** (12.5, dutch
  traces): exactly equal to the online forward view, better than the accumulating-trace TD(λ);
  replacing traces are a historical approximation. (12.6*) dutch traces in MC.
- **Sarsa(λ)** (12.7), **variable λ and γ** (12.8: termination and bootstrapping as per-state
  functions — the general form GVFs use), **off-policy traces with control variates** (12.9),
  **Watkins's Q(λ) → tree-backup(λ)** (12.10: cut the trace at exploratory actions, or weight by the
  target policy), **stable off-policy traces** (12.11: GTD(λ), GQ(λ), HTD(λ), emphatic TD(λ)).
- **Implementation** (12.12): traces cost little with sparse features; with dense deep features they are
  rarely used, so deep RL gets its λ from the forward view (GAE, Retrace, V-trace on stored
  trajectories) rather than from traces.

### Ch 13 Policy gradient methods

- **Why parameterise the policy** (13.1): stochastic optimal policies under FA, continuous actions,
  smoother improvement than ε-greedy over a changing argmax (policy churn), easier to inject priors.
- **The policy gradient theorem** (13.2): ∇J(θ) ∝ Σ_s μ(s) Σ_a q_π(s,a) ∇π(a|s,θ). The gradient does
  not involve the derivative of the state distribution — that is the whole trick, and it holds for the
  on-policy μ (off-policy policy gradients need separate justification, as in DPG/Off-PAC).
- **REINFORCE** (13.3): θ ← θ + α γ^t G_t ∇ln π(A_t|S_t,θ). Unbiased, high variance, episodic.
  (The γ^t factor is in the book and dropped in nearly every implementation; it is one of the known
  "the implementations are not the theory" gaps — Nota & Thomas 2020.)
- **Baseline** (13.4): subtracting b(S_t) leaves the expectation unchanged and cuts variance; v̂(S_t,w)
  is the natural baseline. Fig 13.2: the baseline makes the difference between learning and not.
- **Actor–critic** (13.5): one-step: δ_t = R_{t+1} + γ v̂(S_{t+1},w) − v̂(S_t,w); w ← w + α^w δ_t ∇v̂;
  θ ← θ + α^θ γ^t δ_t ∇ln π. Bootstrapping enters the actor through the critic: bias for variance,
  and online learning in continuing tasks. With traces: actor–critic with eligibility traces (both
  ends). A2C/A3C, PPO (with GAE), SAC (with a soft Q critic) are all this box.
- **Continuing problems** (13.6): the average-reward actor–critic; **continuous actions** (13.7):
  Gaussian policy π(a|s,θ) = N(μ(s,θ_μ), σ(s,θ_σ)), ∇ln π in closed form — the direct ancestor of every
  Gaussian policy head (PPO's state-independent log-std, SAC's state-dependent one).
- **Insight**: policy gradient methods are GPI with a soft improvement step; they are *on-policy* by
  derivation, so reusing old data (PPO's several epochs, SAC's replay) is a departure that needs its own
  argument (trust regions / importance ratios, or the deterministic/soft policy gradient theorems).

---

## Part III — Looking deeper (what to take from it)

- **Ch 14 Psychology**: classical conditioning as prediction (the Rescorla–Wagner rule is the delta rule;
  TD models blocking and higher-order conditioning), instrumental conditioning as control, habitual vs
  goal-directed behaviour as model-free vs model-based. Useful vocabulary when a reward design or a
  shaping scheme is argued by analogy.
- **Ch 15 Neuroscience**: the reward-prediction-error hypothesis of dopamine (Schultz, Dayan, Montague
  1997): phasic dopamine behaves like δ_t. Actor–critic maps onto striatal circuits. Context, not
  method.
- **Ch 16 Case studies**: TD-Gammon (self-play, afterstates, nonlinear TD(λ)), Samuel's checkers,
  Watson's wagering, memory control, DQN on Atari (16.5: experience replay and target networks as the
  deadly-triad guards), AlphaGo and AlphaGo Zero (16.6: policy and value nets guiding MCTS; Zero's
  pure self-play), personalised web services (off-policy evaluation, the importance of unbiased
  evaluation), thermal soaring. Read 16.5–16.6 for how the tabular ideas scale.
- **Ch 17 Frontiers**: **GVFs and auxiliary tasks** (17.1: predictions of arbitrary cumulants as
  knowledge; auxiliary losses as representation shaping), **options** (17.2: temporally extended actions
  with their own termination; the formal hierarchy), **observations and state** (17.3: POMDPs, belief
  states, PSRs, and the pragmatic answer: recurrent state updates u(s_{t−1}, a_{t−1}, o_t) learned
  end to end — the justification for a GRU policy on a partially observable robot), **designing reward
  signals** (17.4: sparse vs shaped, the Ng–Harada–Russell potential-based result, intrinsic reward,
  reward hacking; the book's advice is to keep rewards about goals and move "how" into initial policies,
  options or shaping functions that provably preserve optimality), **remaining issues** (17.5:
  representation learning, model learning and planning, curiosity, safety).

---

## Reading paths

- **The 12-hour practitioner path** (enough to reason about any model-free deep-RL method): 3 → 4.1–4.6 →
  5.1, 5.4, 5.5 → 6 (all) → 7.1 → 8.1–8.2 → 9.1–9.4, 9.7 → 10.1 → 11.1–11.3 → 12.1–12.2 → 13 (all).
- **Debugging an off-policy actor–critic**: 6.5–6.7 → 11.2–11.3 → 13.5 → 16.5; then `deep-rl.md`
  (TD3/SAC, target networks, overestimation).
- **Designing a reward or a curriculum**: 3.2 → 17.4 → 14 (shaping by analogy) → Ng et al. 1999.
- **n-step / λ / GAE choices**: 7.1 → 12.1–12.2 → 12.3 → Schulman et al. 2016.
- **Exploration**: 2 (all) → 8.3 → 17.5; then count-based / RND / bootstrapped DQN in `deep-rl.md`.
- **Partial observability and memory policies**: 17.3 → 13.1 → R2D2, Ni et al. 2022 in `deep-rl.md`.
- **Worth doing by hand**: Exercise 3.14/3.17 (Bellman equations), 4.7 (Jack's car rental), Example 6.2
  (random walk: TD vs MC), Exercise 6.12 (does Sarsa = Q-learning when greedy? no: the update order),
  Example 6.6 (cliff walking), Example 7.1 (n-step random walk), Example 8.1 (Dyna maze), Exercise 11.3
  (reproduce Baird), Example 13.1 (REINFORCE on the short corridor).

## Chapter → deep-RL practice map

| book | the modern instance | note |
|---|---|---|
| 2.4 incremental update, 2.5 constant α | every SGD/Adam step on a TD target | deep RL always tracks; Adam's second-moment estimate adds its own recency (rl-tools' Adam floors it, see `aquila-map.md`) |
| 2.7 UCB | UCT in MCTS (8.11, AlphaZero), count bonuses | |
| 2.8 gradient bandit with baseline | REINFORCE baseline, advantage | |
| 3.2 reward hypothesis / what-not-how | reward hacking, potential-based shaping (Ng 1999) | |
| 3.3 γ as horizon | γ = 0.99 ≈ 100 steps; aquila SAC γ (`config.py`) | |
| 4.6 GPI | actor–critic, DAgger (evaluate the student's own states, improve toward teacher labels) | |
| 5.5 importance sampling | PPO ratio, V-trace/Retrace truncated ratios, off-policy evaluation | variance grows with horizon |
| 6.1 TD(0) | the critic loss in DDPG/TD3/SAC, DQN | |
| 6.5 Q-learning, 6.7 double learning | DQN, Double DQN, clipped double-Q in TD3/SAC | |
| 6.6 Expected Sarsa | SAC's soft target (expectation under π of Q − α log π) | |
| 7.1 n-step | Rainbow n=3, R2D2 n=5, GAE λ | uncorrected off-policy n-step is biased |
| 8.2 Dyna | MBPO, Dreamer, MuZero reanalyse | |
| 8.4 prioritized sweeping | PER | |
| 8.11 MCTS | AlphaZero, MuZero | |
| 9.2 μ-weighted objective | on-policy state distribution in PPO/PG; DAgger's mixture of state distributions | |
| 9.3 semi-gradient | stop-gradient on the target, target networks | |
| 10.3–10.4 average reward | rarely used in deep RL (Wan, Naik, Sutton 2021 differential Q-learning) | |
| 11.3 deadly triad | target nets, replay ratio, clipped critics, layer norm in critics | |
| 12.1 λ-return | GAE(λ), Retrace(λ), V-trace | |
| 13.2 PG theorem | REINFORCE, A2C, PPO, DPG (deterministic variant), soft PG (SAC) | |
| 13.4 baseline | value baseline, advantage normalisation | |
| 13.7 Gaussian policy | PPO/SAC heads; tanh squashing is post-book (SAC appendix) | |
| 17.3 state from observations | GRU/LSTM policies (R2D2, aquila's student), asymmetric critics | |
| 17.4 reward design | Isaac Lab reward terms × weights; aquila's d_action term tax | |
