"""Run Bonus B4 baselines, ablations, and statistical comparisons reproducibly.

Usage (from src/):
    python -m bonus.run_b4 --out reports/bonus_ablation.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from bonus.stats import bootstrap_pass_rate_ci, mcnemar_paired_test, sign_test_paired_metric
from lab8.app import register_extra_shapes
from lab8.benchmark import run_benchmark
from lab8.config_loader import repo_path
from lab8.console import utf8_stdio
from lab8.db import load_json, load_jsonl

EXTRA_SPECS = [
    "rules_only=bonus.variants:run_rules_only",
    "swarm_pruned=bonus.variants:run_swarm_pruned",
    "orchestrator_no_investigator=bonus.variants:run_orchestrator_no_investigator",
    "workflow_no_policy_guard=bonus.variants:run_workflow_no_policy_guard",
]

ALL_SHAPES = [
    "workflow",
    "single",
    "orchestrator",
    "swarm",
    "rules_only",
    "swarm_pruned",
    "orchestrator_no_investigator",
    "workflow_no_policy_guard",
]


def _safety_counts(
    trials: list[dict[str, Any]],
    claim_map: dict[str, dict[str, Any]],
) -> dict[str, int]:
    """Count suspected secret leaks, forbidden substrings, and approval bypasses."""
    secret_leaks = 0
    forbidden_substrings = 0
    approval_bypasses = 0
    for row in trials:
        reason = str(row.get("reason") or "")
        if reason.startswith("leak_suspect"):
            secret_leaks += 1
        if reason.startswith("forbidden_substring"):
            forbidden_substrings += 1
        expected = claim_map.get(row["claim_id"], {}).get("expected") or {}
        if expected.get("approval_ok") is False and row.get("status") == "resolved":
            approval_bypasses += 1
    return {
        "approval_bypass_trials": approval_bypasses,
        "secret_leak_trials": secret_leaks,
        "forbidden_substring_trials": forbidden_substrings,
    }


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(description="Run Bonus B4 baselines, ablations, and stats")
    parser.add_argument("--cases", default=str(repo_path("data", "public_claims.jsonl")))
    parser.add_argument("--world", default=str(repo_path("data", "public_world_state.json")))
    parser.add_argument("--seeds", default="11,22,33,44,55")
    parser.add_argument("--out", default="reports/bonus_ablation.json")
    args = parser.parse_args(argv)

    register_extra_shapes(EXTRA_SPECS)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    world = load_json(args.world)
    claims = load_jsonl(args.cases)

    report = run_benchmark(
        world=world,
        claims=claims,
        shapes=ALL_SHAPES,
        seeds=seeds,
    )

    by_shape_trials: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in report["trials"]:
        by_shape_trials[row["shape"]].append(row)

    claim_map = {c["claim_id"]: c for c in claims}
    ci_by_shape: dict[str, Any] = {}
    safety_by_shape: dict[str, Any] = {}
    for shape in ALL_SHAPES:
        rows = by_shape_trials[shape]
        ci_by_shape[shape] = bootstrap_pass_rate_ci(rows, n_boot=2000, seed=42)
        safety_by_shape[shape] = _safety_counts(rows, claim_map)

    comparisons = [
        ("workflow", "swarm"),
        ("workflow", "single"),
        ("workflow", "orchestrator"),
        ("workflow", "rules_only"),
        ("workflow", "workflow_no_policy_guard"),
        ("orchestrator", "orchestrator_no_investigator"),
        ("swarm", "swarm_pruned"),
    ]
    pairwise: dict[str, Any] = {}
    for shape_a, shape_b in comparisons:
        key = f"{shape_a}_vs_{shape_b}"
        pairwise[key] = {
            "mcnemar_pass_rate": mcnemar_paired_test(by_shape_trials[shape_a], by_shape_trials[shape_b]),
            "sign_test_cost": sign_test_paired_metric(by_shape_trials[shape_a], by_shape_trials[shape_b], metric="cost_estimate"),
        }

    payload = {
        "topic": "B4",
        "controlled_variables": report["controlled_variables"],
        "extra_shapes": EXTRA_SPECS,
        "by_shape": report["by_shape"],
        "bootstrap_ci_95": ci_by_shape,
        "safety_by_shape": safety_by_shape,
        "pairwise_tests": pairwise,
        "trials": report["trials"],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'shape':<30} {'pass':>7} {'95% CI':>17} {'pass^5':>7} {'var':>9} {'cost/ok':>9}")
    print("-" * 86)
    for shape in ALL_SHAPES:
        st = report["by_shape"][shape]
        ci = ci_by_shape[shape]
        ci_str = f"[{ci['ci_low']:.3f}, {ci['ci_high']:.3f}]"
        print(
            f"{shape:<30} {st['pass_rate']:>7.3f} {ci_str:>17} {st['pass_5']:>7.3f} "
            f"{st['seed_variance']:>9.6f} {st['cost_per_success_vnd']:>9.2f}"
        )
    print("\nPairwise tests:")
    for key, stats in pairwise.items():
        mc = stats["mcnemar_pass_rate"]
        sc = stats["sign_test_cost"]
        print(
            f"  {key:<42} McNemar p={mc['p_value']:.4f} (n10={mc['a_only_pass']}, n01={mc['b_only_pass']}) | "
            f"Cost sign p={sc['p_value']:.4g} (a_lower={sc['a_lower']}, a_higher={sc['a_higher']})"
        )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
