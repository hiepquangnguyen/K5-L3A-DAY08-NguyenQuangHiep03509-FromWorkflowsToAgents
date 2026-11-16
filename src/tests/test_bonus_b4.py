"""Tests for Bonus B4: fair baselines, ablations, and standard-library statistical tests."""

from __future__ import annotations

import time

import pytest

from bonus.stats import bootstrap_pass_rate_ci, mcnemar_paired_test, sign_test_paired_metric
from bonus.variants import (
    run_orchestrator_no_investigator,
    run_rules_only,
    run_swarm_pruned,
    run_workflow_no_policy_guard,
)
from lab8.app import register_extra_shapes
from lab8.benchmark import run_benchmark
from lab8.db import connect, init_store
from lab8.durability import InjectedCrash
from lab8.metrics import trial_pass
from lab8.shapes import SHAPES
from tests.conftest import BY_ID, CLAIMS, WORLD


def _fresh_db(tmp_path, name: str):
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return path


def test_bonus_b4_bootstrap_ci_and_mcnemar_exact():
    trials_a = []
    trials_b = []
    # 10 claims x 2 seeds: A passes all 20; B fails both seeds on 3 claims (n10=6, n01=0)
    for i in range(10):
        cid = f"C-{i:03d}"
        for seed in (11, 22):
            trials_a.append({"claim_id": cid, "seed": seed, "passed": True, "cost_estimate": 20.0})
            trials_b.append({"claim_id": cid, "seed": seed, "passed": i >= 3, "cost_estimate": 50.0})

    ci_a = bootstrap_pass_rate_ci(trials_a, n_boot=1000, seed=42)
    ci_b = bootstrap_pass_rate_ci(trials_b, n_boot=1000, seed=42)
    assert ci_a["point"] == 1.0 and ci_a["ci_low"] == 1.0 and ci_a["ci_high"] == 1.0
    assert ci_b["point"] == pytest.approx(0.7)
    assert 0.0 <= ci_b["ci_low"] <= ci_b["point"] <= ci_b["ci_high"] <= 1.0

    mc = mcnemar_paired_test(trials_a, trials_b)
    assert mc["a_only_pass"] == 6
    assert mc["b_only_pass"] == 0
    assert mc["p_value"] == pytest.approx(2.0 * (0.5 ** 6))
    assert mc["significant_0_05"] is True

    mc_same = mcnemar_paired_test(trials_a, trials_a)
    assert mc_same["p_value"] == 1.0
    assert mc_same["significant_0_05"] is False

    sc = sign_test_paired_metric(trials_a, trials_b, metric="cost_estimate")
    assert sc["a_lower"] == 20 and sc["a_higher"] == 0
    assert sc["significant_0_05"] is True


def test_bonus_b4_rules_only_zero_model_calls_and_crash_safe(tmp_path):
    store = _fresh_db(tmp_path, "rules-only.sqlite")
    started = time.time()
    res = run_rules_only("C-001", seed=11, store_path=str(store))
    conn = connect(store)
    try:
        passed, reason = trial_pass(res.as_dict(), BY_ID["C-001"]["expected"], conn, started_at=started)
    finally:
        conn.close()
    assert passed, reason
    assert res.model_calls == 0

    crash_store = _fresh_db(tmp_path, "rules-crash.sqlite")
    with pytest.raises(InjectedCrash):
        run_rules_only("C-012", seed=11, store_path=str(crash_store), crash_at="after_effect_before_checkpoint")
    resumed = run_rules_only("C-012", seed=11, store_path=str(crash_store))
    assert resumed.status == "resolved"
    assert len(resumed.refund_effects) == 1
    assert resumed.committed_audit_count == 1


def test_bonus_b4_swarm_pruned_is_seed_deterministic_and_safe(tmp_path):
    store1 = _fresh_db(tmp_path, "sp1.sqlite")
    store2 = _fresh_db(tmp_path, "sp2.sqlite")
    r1 = run_swarm_pruned("C-001", seed=11, store_path=str(store1))
    r2 = run_swarm_pruned("C-001", seed=11, store_path=str(store2))
    assert r1.status == r2.status == "resolved"
    assert r1.model_calls == r2.model_calls
    assert r1.cost_estimate == r2.cost_estimate

    # Expired approval (C-007) and cross-principal (C-005) remain strictly safe.
    for cid in ("C-005", "C-007"):
        s = _fresh_db(tmp_path, f"sp-{cid}.sqlite")
        started = time.time()
        out = run_swarm_pruned(cid, seed=55, store_path=str(s))
        conn = connect(s)
        try:
            passed, reason = trial_pass(out.as_dict(), BY_ID[cid]["expected"], conn, started_at=started)
        finally:
            conn.close()
        assert passed, f"{cid}: {reason}"


def test_bonus_b4_ablation_variants_via_extra_shape(tmp_path):
    # Verify direct variants and --extra-shape registration behavior cleanly.
    specs = [
        "b4_rules=bonus.variants:run_rules_only",
        "b4_no_inv=bonus.variants:run_orchestrator_no_investigator",
        "b4_no_guard=bonus.variants:run_workflow_no_policy_guard",
    ]
    added = register_extra_shapes(specs)
    try:
        subset = [row for row in CLAIMS if row["claim_id"] in ("C-001", "C-002")]
        report = run_benchmark(
            world=WORLD,
            claims=subset,
            shapes=["workflow", "orchestrator", "b4_rules", "b4_no_inv", "b4_no_guard"],
            seeds=[11, 55],
        )
        assert report["by_shape"]["b4_rules"]["pass_rate"] == 1.0
        assert report["by_shape"]["b4_no_inv"]["pass_rate"] == 1.0
        assert report["by_shape"]["b4_no_inv"]["cost_per_success_vnd"] < report["by_shape"]["orchestrator"]["cost_per_success_vnd"]
        # Dropping the structured-delay guard fails C-002 on both seeds (pass_rate = 0.5).
        assert report["by_shape"]["b4_no_guard"]["pass_rate"] == 0.5
    finally:
        for name in added:
            SHAPES.pop(name, None)

    assert set(SHAPES) == {"workflow", "single", "orchestrator", "swarm"}
