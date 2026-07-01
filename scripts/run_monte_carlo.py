"""Standalone Monte-Carlo experiment runner (Part C.13).

Prints each experiment's observed value against its reference target. Unlike
``report.py`` this does not write a file — it is the quick "did the mechanics
reproduce the reference numbers?" console check.
"""

from __future__ import annotations

from _experiments import run_all


def main():
    rows = run_all()
    width = max(len(r["id"]) for r in rows)
    print(f"{'ID'.ljust(width)}  {'TYPE':<11}  {'OBSERVED':>10}  {'TARGET':>8}  {'TOL':>7}  STATUS")
    print("-" * (width + 48))
    for r in rows:
        obs = f"{r['observed']:.4f}" if isinstance(r["observed"], float) else str(r["observed"])
        tgt = f"{r['target']:.4f}" if isinstance(r["target"], float) else str(r["target"])
        print(
            f"{r['id'].ljust(width)}  {r['type']:<11}  {obs:>10}  {tgt:>8}  "
            f"±{r['tolerance']:<6.4f} {r['status']}"
        )
    if any(r["status"] != "PASS" for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
