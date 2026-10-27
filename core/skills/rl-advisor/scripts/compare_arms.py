#!/usr/bin/env python3
"""Statistics for RL run comparisons, standard library only.

usage: compare_arms.py compare  --a 512 498 530 --b 541 560 538 [--paired] [--boot 20000] [--seed 0]
       compare_arms.py compare  --a-file a.txt --b-file b.txt            # one number per line, or a CSV column via --col
       compare_arms.py max-of-n 10 [--sd 24]                             # expected inflation of "best of N" picks
       compare_arms.py horizon  --gamma 0.99 [--dt 0.01]                 # effective horizon of a discount factor
       compare_arms.py horizon  --steps 100                              # the gamma for a 100-step horizon

`compare` prints n, mean, sd, IQM, the difference of means with a bootstrap 95 % CI,
Welch's t and the probability of improvement P(b > a). Use per-seed means as the
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
    idx = header.index(col) if col in header else int(col)
    for r in rows[1:] if col in header else rows:
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
    for name, xs in (("a", a), ("b", b)):
        print("%s: n=%d mean=%.3f sd=%.3f iqm=%.3f min=%.3f max=%.3f" % (
            name, len(xs), statistics.fmean(xs), statistics.stdev(xs), iqm(xs), min(xs), max(xs)))
    diff = statistics.fmean(b) - statistics.fmean(a)
    lo, hi = bootstrap_diff(a, b, args.paired, args.boot, args.seed)
    t, df = welch(a, b)
    p = t_two_sided_p(t, df)
    pooled = math.sqrt((statistics.variance(a) + statistics.variance(b)) / 2.0)
    print("b - a: %.3f  bootstrap 95%% CI [%.3f, %.3f]  (%s, %d resamples)" % (
        diff, lo, hi, "paired" if args.paired else "unpaired", args.boot))
    print("Welch t=%.3f df=%.1f p=%.4f  Cohen d=%.3f  P(b > a)=%.3f" % (
        t, df, p, diff / pooled if pooled > 0 else float("nan"), prob_improvement(a, b)))
    verdict = "clears the noise" if lo > 0 or hi < 0 else "inside the noise"
    print("read: the 95%% CI %s zero -> %s" % ("excludes" if verdict.startswith("clears") else "contains", verdict))
    if min(len(a), len(b)) < 3:
        print("note: 2 samples per arm give a CI you should not trust; this is a sanity check, not a verdict")


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

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
