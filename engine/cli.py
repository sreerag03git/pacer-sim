"""Command-line entry point for the PACER engine.

Runs the three controller modes on identical scenarios and prints the headline
comparison table. No Streamlit, no UI -- this is the engine proving itself.

    python -m engine.cli                 # defaults (seed 7, 200 runs)
    python -m engine.cli --runs 50        # fewer Monte Carlo runs
    python -m engine.cli --heatwave heatwave --outage 180
"""

from __future__ import annotations

import argparse
import sys
import time

from engine.config import Config, ControllerMode, HeatwavePreset
from engine.montecarlo import MonteCarloResult, run_monte_carlo


def _build_config(args: argparse.Namespace) -> Config:
    return Config(
        homes=args.homes,
        ac_penetration=args.ac / 100.0,
        nameplate_kva=args.nameplate,
        outage_minutes=args.outage,
        heatwave=HeatwavePreset(args.heatwave),
        mc_runs=args.runs,
        seed=args.seed,
    )


def format_headline(result: MonteCarloResult) -> str:
    """Render the headline comparison table as fixed-width monospace text."""
    cfg = result.config
    lines: list[str] = []
    lines.append("")
    lines.append("PACER engine -- headline comparison")
    lines.append(
        f"seed={result.seed}  runs={result.n_runs}  homes={cfg.homes}  "
        f"nameplate={cfg.nameplate_kva:.0f} kVA  fuse={cfg.fuse_current_a:.0f} A/phase  "
        f"outage={cfg.outage_minutes} min  weather={cfg.heatwave.value} ({cfg.heatwave.peak_c:.0f} C)"
    )
    lines.append("")

    header = (
        f"{'Mode':<16}{'Blow-outs':>12}{'Rate':>9}{'95% CI':>18}"
        f"{'Homes dark':>12}{'Peak x rat':>12}{'Min>32C':>10}{'Ageing h':>11}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for mode in result.modes:
        s = result.stats[mode]
        ci = f"[{s.blowout_ci.low*100:4.1f},{s.blowout_ci.high*100:5.1f}]%"
        lines.append(
            f"{mode.label:<16}"
            f"{s.blowout_runs:>8}/{s.n_runs:<3}"
            f"{s.blowout_runs / s.n_runs * 100:>8.1f}%"
            f"{ci:>18}"
            f"{s.mean_homes_dark:>12.1f}"
            f"{s.mean_peak_pu:>12.2f}"
            f"{s.mean_minutes_above_32:>10.1f}"
            f"{s.mean_ageing_hours:>11.3f}"
        )
    lines.append("")
    lines.append("Pairwise two-proportion tests on the blow-out rate:")
    for tt in result.pairwise_tests:
        lines.append(
            f"  {tt.label_a:<16} vs {tt.label_b:<16}  "
            f"{tt.prop_a*100:5.1f}% vs {tt.prop_b*100:5.1f}%   "
            f"z={tt.z:+.3f}  p={tt.p_value:.3g}"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the PACER engine headline comparison.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--homes", type=int, default=200)
    parser.add_argument("--ac", type=float, default=60.0, help="AC penetration (percent)")
    parser.add_argument("--nameplate", type=float, default=160.0, help="transformer nameplate (kVA)")
    parser.add_argument("--outage", type=int, default=120, help="outage duration (minutes)")
    parser.add_argument(
        "--heatwave",
        choices=[p.value for p in HeatwavePreset],
        default=HeatwavePreset.HOT.value,
    )
    args = parser.parse_args(argv)

    config = _build_config(args)
    problems = config.validate()
    if problems:
        for p in problems:
            print(f"config error: {p}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    last = {"pct": -1}

    def progress(frac: float, msg: str) -> None:
        pct = int(frac * 100)
        if pct != last["pct"]:
            last["pct"] = pct
            print(f"\rrunning... {pct:3d}%  {msg:<32}", end="", flush=True)

    result = run_monte_carlo(config, progress=progress)
    elapsed = time.perf_counter() - t0
    print("\r" + " " * 60 + "\r", end="")
    print(format_headline(result))
    print(f"elapsed: {elapsed:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
