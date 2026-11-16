"""Bonus B4 shape variants sharing the standard run_claim signature.

Variants:
- rules_only: deterministic workflow with 0 model calls (no draft MockLLM call).
- swarm_pruned: reference swarm that randomly drops peer/parse calls per seed.
- orchestrator_no_investigator: orchestrator keeping plan/draft calls without handoff/investigator.
- workflow_no_policy_guard: workflow ablation without structured-delay guard (trusts ticket delay).
"""

from __future__ import annotations

import random
import sqlite3

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete, parse_delay_days
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import (
    compute_compensation,
    get_claim_view,
    lookup_order,
    lookup_policy,
    lookup_refund_history,
    tool_cost,
)
from lab8.trace import Trace


def _finalize_refund(
    conn: sqlite3.Connection,
    *,
    shape: str,
    claim_id: str,
    seed: int,
    proposal: int,
    quote_reason: str | None,
    budget: Budget,
    trace: Trace,
    crash_at: str | None,
) -> RunResult:
    if proposal <= 0:
        trace.add("decision", {"status": "denied", "proposal_amount": 0, "reason": quote_reason})
        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=quote_reason,
        )

    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    trace.add(
        "issue_refund",
        {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]},
    )
    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=outcome["reason"],
        )

    return finish(
        conn,
        shape=shape,
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )


def run_rules_only(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Baseline 1 & workflow ablation: pure deterministic rules, 0 model calls."""
    conn = connect(store_path)
    try:
        budget = Budget()
        trace = Trace(make_run_id("rules_only", claim_id, seed))
        claim_view = get_claim_view(conn, claim_id)
        budget.add_tool(tool_cost())
        if not claim_view["found"]:
            trace.add("error", {"reason": "unknown_claim"})
            return finish(
                conn,
                shape="rules_only",
                claim_id=claim_id,
                seed=seed,
                status="failed",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="unknown_claim",
            )
        order_id = claim_view.get("order_id")
        trace.add("claim_view", {"claim_id": claim_id, "has_order_id": bool(order_id)})
        if not order_id:
            trace.add("decision", {"status": "needs_info", "reason": "missing_order_id"})
            return finish(
                conn,
                shape="rules_only",
                claim_id=claim_id,
                seed=seed,
                status="needs_info",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="missing_order_id",
            )
        order_view = lookup_order(conn, order_id, claim_view["principal_id"])
        budget.add_tool(tool_cost())
        trace.add("lookup_order", order_view)
        if not order_view.get("visible"):
            reason = order_view.get("reason")
            trace.add("decision", {"status": "escalated", "reason": reason})
            return finish(
                conn,
                shape="rules_only",
                claim_id=claim_id,
                seed=seed,
                status="escalated",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason=reason,
            )
        quote_payload = compute_compensation(conn, order_view["order"])
        budget.add_tool(tool_cost())
        trace.add("quote", quote_payload)
        return _finalize_refund(
            conn,
            shape="rules_only",
            claim_id=claim_id,
            seed=seed,
            proposal=int(quote_payload["amount_vnd"]),
            quote_reason=quote_payload.get("reason"),
            budget=budget,
            trace=trace,
            crash_at=crash_at,
        )
    finally:
        conn.close()


def run_swarm_pruned(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Baseline 2: swarm reference with random pruning of peer/parse calls by seed."""
    from lab8.handoff import make_handoff
    from lab8.runtime import run_readonly_investigators
    from lab8.shapes.common import safe_dump

    conn = connect(store_path)
    try:
        rng = random.Random(seed)
        keep_peer = rng.random() >= 0.5
        keep_parse = rng.random() >= 0.5

        budget = Budget()
        trace = Trace(make_run_id("swarm_pruned", claim_id, seed))
        claim_view = get_claim_view(conn, claim_id)
        budget.add_tool(tool_cost())
        if not claim_view["found"]:
            trace.add("error", {"reason": "unknown_claim"})
            return finish(
                conn,
                shape="swarm_pruned",
                claim_id=claim_id,
                seed=seed,
                status="failed",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="unknown_claim",
            )

        ticket = claim_view["ticket"]
        if keep_peer:
            complete(budget, seed=seed, purpose="peer", prompt=ticket)
        parsed_delay: int | None = None
        if keep_parse:
            parsed_delay = parse_delay_days(ticket)
            complete(budget, seed=seed, purpose="parse", prompt=ticket)
        trace.add("prune", {"keep_peer": keep_peer, "keep_parse": keep_parse})

        order_id = claim_view.get("order_id")
        if not order_id:
            complete(budget, seed=seed, purpose="draft", prompt="needs_info")
            trace.add("decision", {"status": "needs_info"})
            return finish(
                conn,
                shape="swarm_pruned",
                claim_id=claim_id,
                seed=seed,
                status="needs_info",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="missing_order_id",
            )

        handoff = make_handoff(
            request_id=f"REQ-{claim_id}",
            claim_id=claim_id,
            task="check_applicable_policy",
            facts={},
            allowed_tools=["lookup_order", "lookup_policy", "compute_compensation"],
        )
        trace.add("handoff", safe_dump(handoff))
        investigated = run_readonly_investigators(
            conn, budget, handoff, principal_id=claim_view["principal_id"]
        )
        order_view = investigated["tools"].get("lookup_order", {})
        trace.add(
            "investigator",
            {
                "lookup_order": order_view,
                "policy_count": len((investigated["tools"].get("lookup_policy") or {}).get("policies") or []),
            },
        )
        if not order_view.get("visible"):
            complete(budget, seed=seed, purpose="draft", prompt="escalated")
            return finish(
                conn,
                shape="swarm_pruned",
                claim_id=claim_id,
                seed=seed,
                status="escalated",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason=order_view.get("reason"),
            )

        order = dict(order_view["order"])
        quote_payload = investigated["tools"]["compute_compensation"]
        if parsed_delay is not None and parsed_delay != int(order["delay_days"]) and seed % 5 == 0:
            order["delay_days"] = parsed_delay
            trace.add("model_override", {"delay_days": parsed_delay})
            budget.add_tool(tool_cost())
            quote_payload = compute_compensation(conn, order)

        proposal = int(quote_payload["amount_vnd"])
        trace.add("quote", quote_payload)
        complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
        return _finalize_refund(
            conn,
            shape="swarm_pruned",
            claim_id=claim_id,
            seed=seed,
            proposal=proposal,
            quote_reason=quote_payload.get("reason"),
            budget=budget,
            trace=trace,
            crash_at=crash_at,
        )
    finally:
        conn.close()


def run_orchestrator_no_investigator(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Ablation on orchestrator: keep plan + draft calls, drop handoff & investigator layer."""
    conn = connect(store_path)
    try:
        budget = Budget()
        trace = Trace(make_run_id("orchestrator_no_investigator", claim_id, seed))
        claim_view = get_claim_view(conn, claim_id)
        budget.add_tool(tool_cost())
        if not claim_view["found"]:
            trace.add("error", {"reason": "unknown_claim"})
            return finish(
                conn,
                shape="orchestrator_no_investigator",
                claim_id=claim_id,
                seed=seed,
                status="failed",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="unknown_claim",
            )

        order_id = claim_view.get("order_id")
        principal_id = claim_view["principal_id"]
        complete(budget, seed=seed, purpose="plan", prompt=f"claim={claim_id} has_order_id={bool(order_id)}")
        if not order_id:
            complete(budget, seed=seed, purpose="draft", prompt=f"claim={claim_id} status=needs_info")
            trace.add("decision", {"status": "needs_info", "reason": "missing_order_id"})
            return finish(
                conn,
                shape="orchestrator_no_investigator",
                claim_id=claim_id,
                seed=seed,
                status="needs_info",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="missing_order_id",
            )

        order_view = lookup_order(conn, order_id, principal_id)
        budget.add_tool(tool_cost())
        policies = lookup_policy(conn)["policies"]
        budget.add_tool(tool_cost())
        history = lookup_refund_history(conn, order_id, principal_id)
        budget.add_tool(tool_cost())
        trace.add(
            "direct_lookup",
            {"lookup_order": order_view, "policy_count": len(policies), "refund_history": history},
        )
        if not order_view.get("visible"):
            reason = order_view.get("reason")
            complete(budget, seed=seed, purpose="draft", prompt=f"claim={claim_id} status=escalated")
            trace.add("decision", {"status": "escalated", "reason": reason})
            return finish(
                conn,
                shape="orchestrator_no_investigator",
                claim_id=claim_id,
                seed=seed,
                status="escalated",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason=reason,
            )

        quote_payload = compute_compensation(conn, order_view["order"])
        budget.add_tool(tool_cost())
        proposal = int(quote_payload["amount_vnd"])
        trace.add("quote", quote_payload)
        complete(budget, seed=seed, purpose="draft", prompt=f"claim={claim_id} proposal={proposal}")
        return _finalize_refund(
            conn,
            shape="orchestrator_no_investigator",
            claim_id=claim_id,
            seed=seed,
            proposal=proposal,
            quote_reason=quote_payload.get("reason"),
            budget=budget,
            trace=trace,
            crash_at=crash_at,
        )
    finally:
        conn.close()


def run_workflow_no_policy_guard(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Ablation on workflow: drop structured-delay guard and trust ticket delay numbers."""
    conn = connect(store_path)
    try:
        budget = Budget()
        trace = Trace(make_run_id("workflow_no_policy_guard", claim_id, seed))
        claim_view = get_claim_view(conn, claim_id)
        budget.add_tool(tool_cost())
        if not claim_view["found"]:
            trace.add("error", {"reason": "unknown_claim"})
            return finish(
                conn,
                shape="workflow_no_policy_guard",
                claim_id=claim_id,
                seed=seed,
                status="failed",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="unknown_claim",
            )

        order_id = claim_view.get("order_id")
        principal_id = claim_view["principal_id"]
        trace.add("claim_view", {"claim_id": claim_id, "has_order_id": bool(order_id)})
        if not order_id:
            complete(budget, seed=seed, purpose="draft", prompt=f"claim={claim_id} status=needs_info")
            trace.add("decision", {"status": "needs_info", "reason": "missing_order_id"})
            return finish(
                conn,
                shape="workflow_no_policy_guard",
                claim_id=claim_id,
                seed=seed,
                status="needs_info",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="missing_order_id",
            )

        order_view = lookup_order(conn, order_id, principal_id)
        budget.add_tool(tool_cost())
        trace.add("lookup_order", order_view)
        if not order_view.get("visible"):
            reason = order_view.get("reason")
            complete(budget, seed=seed, purpose="draft", prompt=f"claim={claim_id} status=escalated")
            trace.add("decision", {"status": "escalated", "reason": reason})
            return finish(
                conn,
                shape="workflow_no_policy_guard",
                claim_id=claim_id,
                seed=seed,
                status="escalated",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason=reason,
            )

        order = dict(order_view["order"])
        parsed_delay = parse_delay_days(claim_view["ticket"])
        if parsed_delay is not None and parsed_delay != int(order["delay_days"]):
            order["delay_days"] = parsed_delay
            trace.add("unguarded_ticket_delay", {"delay_days": parsed_delay})

        quote_payload = compute_compensation(conn, order)
        budget.add_tool(tool_cost())
        proposal = int(quote_payload["amount_vnd"])
        trace.add("quote", quote_payload)
        complete(budget, seed=seed, purpose="draft", prompt=f"claim={claim_id} proposal={proposal}")
        return _finalize_refund(
            conn,
            shape="workflow_no_policy_guard",
            claim_id=claim_id,
            seed=seed,
            proposal=proposal,
            quote_reason=quote_payload.get("reason"),
            budget=budget,
            trace=trace,
            crash_at=crash_at,
        )
    finally:
        conn.close()
