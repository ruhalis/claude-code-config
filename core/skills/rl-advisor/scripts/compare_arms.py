#!/usr/bin/env python3
"""Statistics for RL run comparisons, standard library only.

usage: compare_arms.py compare  --a 512 498 530 --b 541 560 538 [--paired] [--boot 20000] [--seed 0]
       compare_arms.py compare  --a-file a.txt --b-file b.txt            # one number per line, or a CSV column via --col
       compare_arms.py max-of-n 10 [--sd 24]                             # expected inflation of "best of N" picks
       compare_arms.py horizon  --gamma 0.99 [--dt 0.01]                 # effective horizon of a discount factor
       compare_arms.py horizon  --steps 100                              # the gamma for a 100-step horizon
       compare_arms.py selftest [--trials 4000] [--seed 0]              # false-positive rate and power check

`compare` prints n, mean, sd, IQM, the difference of means with a bootstrap 95 % CI,
Welch's t, the Welch 95 % CI and the probability of improvement P(b > a). The verdict
("clears the noise") comes from the Welch interval (paired t with --paired), i.e. p < 0.05;
the percentile bootstrap CI is printed as secondary only, because on 3-10 values per arm it
is too narrow (it calls a no-effect pair "clear" ~20 % of the time at n=3). `selftest`
simulates no-effect and large-effect arms and exits non-zero if the verdict is miscalibrated.
Use per-seed means as the
samples when the runs differ by seed, per-episode returns when they share a seed
(then the CI is about episode noise only and says nothing about seed-to-seed spread).
`max-of-n` is the expected maximum of N standard normal draws, in sd units: the
inflation a "best epoch / best seed / best checkpoint" pick carries by itself.
"""
import argparse
import csv
import math
import random
import statistics
import sys


# ---- small numerics -------------------------------------------------------

def phi(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def Phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def expected_max_normal(n, lo=-9.0, hi=9.0, steps=36000):
    """E[max of n iid N(0,1)] = ∫ x · n · φ(x) · Φ(x)^(n-1) dx, by the trapezoid rule."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if n == 1:
        return 0.0
    h = (hi - lo) / steps
    total = 0.0
    for i in range(steps + 1):
        x = lo + i * h
        f = x * n * phi(x) * Phi(x) ** (n - 1)
        total += f if 0 < i < steps else 0.5 * f
    return total * h


def iqm(xs):
    """Interquartile mean: mean of the middle 50 % (Agarwal et al. 2021)."""
    s = sorted(xs)
    n = len(s)
    if n < 4:
        return statistics.fmean(s)
    lo, hi = n // 4, n - n // 4
    return statistics.fmean(s[lo:hi])


def welch(a, b):
    na, nb = len(a), len(b)
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    va = statistics.variance(a) if na > 1 else 0.0
    vb = statistics.variance(b) if nb > 1 else 0.0
    se2 = va / na + vb / nb
    if se2 == 0:
        return float("nan"), float("nan")
    t = (mb - ma) / math.sqrt(se2)
    num = se2 * se2
    den = 0.0
    if na > 1:
        den += (va / na) ** 2 / (na - 1)
    if nb > 1:
        den += (vb / nb) ** 2 / (nb - 1)
    df = num / den if den > 0 else float("nan")
    return t, df


def t_two_sided_p(t, df):
    """Two-sided p-value of Student's t via the regularized incomplete beta (no scipy)."""
    if math.isnan(t) or math.isnan(df) or df <= 0:
        return float("nan")
    x = df / (df + t * t)
    return _betainc(df / 2.0, 0.5, x)


ALPHA = 0.05  # two-sided; the verdict's 95 % interval


def t_crit(df, alpha=ALPHA):
    """Two-sided critical value c with P(|T_df| > c) = alpha, by bisection on t_two_sided_p."""
    if math.isnan(df) or df <= 0:
        return float("nan")
    lo, hi = 0.0, 2.0
    while t_two_sided_p(hi, df) > alpha:
        lo, hi = hi, hi * 2.0
    while hi - lo > 1e-9 * hi:
        mid = 0.5 * (lo + hi)
        if t_two_sided_p(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def mean_diff_interval(a, b, paired=False, alpha=ALPHA):
    """b - a with its t interval: Welch (unpaired, Welch-Satterthwaite df) or paired t (df = n - 1).

    Returns a dict with diff, se, df, t, p, crit, lo, hi. When se == 0 (no spread in either arm,
    or in the paired differences) there is no noise estimate: t, df, p, crit, lo and hi are nan.
    """
    if paired:
        d = [y - x for x, y in zip(a, b)]
        diff = statistics.fmean(d)
        se = statistics.stdev(d) / math.sqrt(len(d))
        df = len(d) - 1.0
        t = diff / se if se > 0 else float("nan")
    else:
        diff = statistics.fmean(b) - statistics.fmean(a)
        se = math.sqrt(statistics.variance(a) / len(a) + statistics.variance(b) / len(b))
        t, df = welch(a, b)
    nan = float("nan")
    if se == 0:
        return dict(diff=diff, se=0.0, df=nan, t=nan, p=nan, crit=nan, lo=nan, hi=nan)
    crit = t_crit(df, alpha)
    return dict(diff=diff, se=se, df=df, t=t, p=t_two_sided_p(t, df), crit=crit,
                lo=diff - crit * se, hi=diff + crit * se)


def verdict(iv):
    if iv["se"] == 0:
        return "inconclusive"
    return "clears the noise" if iv["lo"] > 0 or iv["hi"] < 0 else "inside the noise"


def _betainc(a, b, x):
    # Regularized incomplete beta I_x(a, b) by Lentz's continued fraction (Numerical Recipes).
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1 - x) / b


def _betacf(a, b, x, maxit=300, eps=3e-14):
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / (c if abs(c) > tiny else tiny)
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / (c if abs(c) > tiny else tiny)
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def bootstrap_diff(a, b, paired, boot, seed):
    rng = random.Random(seed)
    diffs = []
    if paired:
        pairs = list(zip(a, b))
        for _ in range(boot):
            s = [rng.choice(pairs) for _ in pairs]
            diffs.append(statistics.fmean(y - x for x, y in s))
    else:
        for _ in range(boot):
            sa = [rng.choice(a) for _ in a]
            sb = [rng.choice(b) for _ in b]
            diffs.append(statistics.fmean(sb) - statistics.fmean(sa))
    diffs.sort()
    lo = diffs[int(0.025 * (boot - 1))]
    hi = diffs[int(0.975 * (boot - 1))]
    return lo, hi


def prob_improvement(a, b):
    """P(b > a) over all pairs, ties count half (Mann–Whitney effect size)."""
    wins = 0.0
    for x in a:
        for y in b:
            wins += 1.0 if y > x else 0.5 if y == x else 0.0
    return wins / (len(a) * len(b))


# ---- input ----------------------------------------------------------------

def read_numbers(path, col):
    out = []
    with open(path, newline="") as f:
        text = f.read()
    if col is None:
        for tok in text.replace(",", " ").split():
            try:
                out.append(float(tok))
            except ValueError:
                continue
        return out
    rows = list(csv.reader(text.splitlines()))
    header = rows[0] if rows else []
    if col in header:
        idx, body = header.index(col), rows[1:]
    else:
        try:
            idx, body = int(col), rows
        except ValueError:
            sys.exit("compare: --col %r is neither a column of %s (header: %s) nor an integer index"
                     % (col, path, ", ".join(header) or "empty"))
    for r in body:
        if idx < len(r):
            try:
                out.append(float(r[idx]))
            except ValueError:
                continue
    return out


# ---- commands -------------------------------------------------------------

def cmd_compare(args):
    a = list(args.a or []) + (read_numbers(args.a_file, args.col) if args.a_file else [])
    b = list(args.b or []) + (read_numbers(args.b_file, args.col) if args.b_file else [])
    if len(a) < 2 or len(b) < 2:
        sys.exit("compare: need at least 2 samples per arm (got %d and %d)" % (len(a), len(b)))
    if args.paired and len(a) != len(b):
        sys.exit("compare: --paired needs equal-length arms")
    if args.boot < 1:
        sys.exit("compare: --boot must be >= 1 (got %d)" % args.boot)
    for name, xs in (("a", a), ("b", b)):
        print("%s: n=%d mean=%.3f sd=%.3f iqm=%.3f min=%.3f max=%.3f" % (
            name, len(xs), statistics.fmean(xs), statistics.stdev(xs), iqm(xs), min(xs), max(xs)))
    diff = statistics.fmean(b) - statistics.fmean(a)
    lo, hi = bootstrap_diff(a, b, args.paired, args.boot, args.seed)
    t, df = welch(a, b)
    p = t_two_sided_p(t, df)
    pooled = math.sqrt((statistics.variance(a) + statistics.variance(b)) / 2.0)
    print("b - a: %.3f  bootstrap 95%% CI [%.3f, %.3f]  (%s, %d resamples; secondary, does not decide)" % (
        diff, lo, hi, "paired" if args.paired else "unpaired", args.boot))
    print("Welch t=%.3f df=%.1f p=%.4f  Cohen d=%.3f  P(b > a)=%.3f" % (
        t, df, p, diff / pooled if pooled > 0 else float("nan"), prob_improvement(a, b)))
    iv = mean_diff_interval(a, b, args.paired)
    test = "paired t" if args.paired else "Welch"
    if args.paired and iv["se"] > 0:
        print("paired t=%.3f df=%.0f p=%.4f" % (iv["t"], iv["df"], iv["p"]))
    v = verdict(iv)
    if v == "inconclusive":
        print("%s 95%% CI: none (%s have zero spread, so there is no noise estimate)" % (
            test, "the paired differences" if args.paired else "both arms"))
        print("read: no spread to measure the noise against -> inconclusive "
              "(add seeds, or use a finer-grained metric)")
    else:
        print("%s 95%% CI [%.3f, %.3f]  (b - a +/- t_crit %.3f x se %.3f; decides the verdict)" % (
            test, iv["lo"], iv["hi"], iv["crit"], iv["se"]))
        print("read: the %s 95%% CI %s zero (p %s 0.05) -> %s" % (
            test, "excludes" if v.startswith("clears") else "contains",
            "<" if v.startswith("clears") else ">=", v))
        if (lo > 0 or hi < 0) != v.startswith("clears"):
            print("note: the bootstrap CI %s zero but the %s CI does not; on few seeds the percentile "
                  "bootstrap is too narrow, the %s line decides" % (
                      "excludes" if lo > 0 or hi < 0 else "contains",
                      test, test))
    if min(len(a), len(b)) < 3:
        print("note: 2 samples per arm give a CI you should not trust; this is a sanity check, not a verdict")


WELCH_SIZE_N3 = 0.034  # Welch's own false-positive rate at 3 vs 3 (20000 null trials); it is conservative there


def cmd_selftest(args):
    """Simulate the verdict and fail if it is miscalibrated.

    Band for the no-effect rate, from the binomial sd of a rate over N trials, sd(p) = sqrt(p(1-p)/N):
    upper = 5 % + 4 sd(5 %), so an anti-conservative gate (the old bootstrap verdict: ~20 / 13 / 8 %
    at n = 3 / 5 / 10) fails; lower = 3.4 % - 4 sd(3.4 %), Welch's real size at n = 3, so a gate that
    went blind (a wrong df or t_crit) fails too. 4 sd keeps a correct implementation inside the band
    under any re-seed (two-sided chance ~6e-5 per case). At N = 4000 the band is [2.25 %, 6.38 %].
    """
    rng = random.Random(args.seed)
    n_trials = args.trials
    if n_trials < 100:
        sys.exit("selftest: --trials must be >= 100")
    hi_band = ALPHA + 4 * math.sqrt(ALPHA * (1 - ALPHA) / n_trials)
    lo_band = max(0.0, WELCH_SIZE_N3 - 4 * math.sqrt(WELCH_SIZE_N3 * (1 - WELCH_SIZE_N3) / n_trials))
    failures = []
    disagree = 0

    def run(n, delta, trials, paired=False):
        nonlocal disagree
        hits = 0
        for _ in range(trials):
            if paired:  # shared per-seed level, so the arms are correlated
                s = [rng.gauss(0.0, 1.0) for _ in range(n)]
                a = [x + rng.gauss(0.0, 0.5) for x in s]
                b = [x + delta + rng.gauss(0.0, 0.5) for x in s]
            else:
                a = [rng.gauss(0.0, 1.0) for _ in range(n)]
                b = [rng.gauss(delta, 1.0) for _ in range(n)]
            iv = mean_diff_interval(a, b, paired)
            clears = verdict(iv) == "clears the noise"
            hits += clears
            if clears != (iv["p"] < ALPHA) and abs(iv["p"] - ALPHA) > 1e-9:
                disagree += 1
        return hits / trials

    print("selftest: seed %d, %d trials per no-effect case, pass band [%.2f%%, %.2f%%] around the nominal 5%%"
          % (args.seed, n_trials, 100 * lo_band, 100 * hi_band))
    for n, paired in ((3, False), (5, False), (10, False), (5, True)):
        rate = run(n, 0.0, n_trials, paired)
        ok = lo_band <= rate <= hi_band
        label = "%s n=%d" % ("paired  " if paired else "unpaired", n)
        print("  no effect, %s per arm: clears the noise %5.2f%%  %s" % (label, 100 * rate, "ok" if ok else "FAIL"))
        if not ok:
            failures.append("no-effect rate %.2f%% at %s is outside the band" % (100 * rate, label))

    # Power at a 3 sd effect: noncentral t gives ~68 % at n = 3 and ~98 % at n = 5, ~100 % at n = 10.
    power_trials = max(100, n_trials // 4)
    for n, floor in ((3, 0.50), (5, 0.90), (10, 0.90)):
        rate = run(n, 3.0, power_trials)
        ok = rate >= floor
        print("  3 sd effect, unpaired n=%d per arm: clears the noise %5.1f%% (need >= %.0f%%)  %s"
              % (n, 100 * rate, 100 * floor, "ok" if ok else "FAIL"))
        if not ok:
            failures.append("power %.1f%% at n=%d is below %.0f%%" % (100 * rate, n, 100 * floor))

    print("  verdict vs Welch p < 0.05 disagreements: %d" % disagree)
    if disagree:
        failures.append("%d trials where the interval verdict and p < 0.05 disagree" % disagree)

    fixed = []
    for df, ref in ((1, 12.706), (2, 4.303), (4, 2.776), (10, 2.228), (30, 2.042)):
        if abs(t_crit(df) - ref) > 5e-4:
            fixed.append("t_crit(df=%d) = %.4f, table value %.3f" % (df, t_crit(df), ref))
    if verdict(mean_diff_interval([5.0, 5.0, 5.0], [6.0, 6.0, 6.0])) != "inconclusive":
        fixed.append("zero spread in both arms is not reported as inconclusive")
    # The SKILL.md usage example: the bootstrap CI excludes zero, Welch p = 0.0505 does not.
    if verdict(mean_diff_interval([512.0, 498.0, 530.0], [541.0, 560.0, 538.0])) != "inside the noise":
        fixed.append("the 512/498/530 vs 541/560/538 example does not read 'inside the noise'")
    print("  t_crit table, zero-spread and usage-example checks: %s" % ("FAIL" if fixed else "ok"))
    failures += fixed

    if failures:
        for f in failures:
            print("FAIL: " + f)
        sys.exit(1)
    print("selftest: PASS")


def cmd_max_of_n(args):
    for n in args.n:
        z = expected_max_normal(n)
        line = "best of %d: expected max = +%.3f sd above the mean" % (n, z)
        if args.sd is not None:
            line += " = +%.2f in metric units at sd %.2f" % (z * args.sd, args.sd)
        print(line)
    print("read: a best-of-N pick is this far above a typical draw before any real effect; "
          "compare picks only against picks made the same way, or re-evaluate the pick on fresh seeds")


def cmd_horizon(args):
    if args.gamma is not None:
        g = args.gamma
        if not 0 < g < 1:
            sys.exit("horizon: --gamma must be in (0, 1)")
        h = 1.0 / (1.0 - g)
        half = math.log(0.5) / math.log(g)
        print("gamma=%.5f: effective horizon 1/(1-gamma)=%.1f steps, half-life %.1f steps, "
              "weight left after %d steps %.3f" % (g, h, half, int(h), g ** int(h)))
        if args.dt:
            print("at dt=%g s: horizon %.2f s, half-life %.2f s" % (args.dt, h * args.dt, half * args.dt))
    if args.steps is not None:
        g = 1.0 - 1.0 / args.steps
        print("horizon %d steps: gamma=%.5f" % (args.steps, g))
        if args.dt:
            print("that is %.2f s at dt=%g s" % (args.steps * args.dt, args.dt))
    if args.gamma is None and args.steps is None:
        sys.exit("horizon: give --gamma or --steps")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="compare_arms.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compare", help="two arms of returns: CI, Welch t, P(b > a)")
    c.add_argument("--a", type=float, nargs="*", help="arm A samples (baseline)")
    c.add_argument("--b", type=float, nargs="*", help="arm B samples (candidate)")
    c.add_argument("--a-file", help="file with arm A samples")
    c.add_argument("--b-file", help="file with arm B samples")
    c.add_argument("--col", help="CSV column name or index to read from the files")
    c.add_argument("--paired", action="store_true", help="samples are paired (same seed / same frame)")
    c.add_argument("--boot", type=int, default=20000, help="bootstrap resamples (default 20000)")
    c.add_argument("--seed", type=int, default=0, help="bootstrap RNG seed")
    c.set_defaults(func=cmd_compare)

    m = sub.add_parser("max-of-n", help="expected inflation of a best-of-N pick, in sd units")
    m.add_argument("n", type=int, nargs="+", help="number of draws the pick was the best of")
    m.add_argument("--sd", type=float, help="eval sd in metric units, to print the inflation in those units")
    m.set_defaults(func=cmd_max_of_n)

    h = sub.add_parser("horizon", help="discount factor <-> effective horizon")
    h.add_argument("--gamma", type=float)
    h.add_argument("--steps", type=int, help="desired horizon in steps")
    h.add_argument("--dt", type=float, help="control period in seconds, to print horizons in seconds")
    h.set_defaults(func=cmd_horizon)

    s = sub.add_parser("selftest", help="check the verdict's false-positive rate and power by simulation")
    s.add_argument("--trials", type=int, default=4000, help="no-effect trials per case (default 4000)")
    s.add_argument("--seed", type=int, default=0, help="simulation RNG seed")
    s.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
