"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Run one claim through a bounded read-only ReAct loop, then write via host."""
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id("single", claim_id, seed))
    state: dict[str, Any] = {"step": 0}

    def decide(obs: dict[str, Any]) -> dict[str, Any]:
        state["step"] += 1
        last_tool = obs.get("last_tool")
        last_result = obs.get("last_result")

        prompt = json.dumps(
            {
                "claim_id": claim_id,
                "step": state["step"],
                "last_tool": last_tool,
                "has_order": "order" in state,
                "has_quote": "quote" in state,
            },
            ensure_ascii=False,
        )
        complete(budget, seed=seed, purpose="react", prompt=prompt)

        if last_tool is None:
            trace.add("react_step", {"step": state["step"], "action": "call", "tool": "get_claim_view"})
            return {"tool": "get_claim_view", "args": {"claim_id": claim_id}}

        if last_tool == "get_claim_view":
            if not last_result.get("found"):
                trace.add("react_step", {"step": state["step"], "action": "final", "status": "failed"})
                return {"final": {"status": "failed", "proposal_amount": 0, "reason": "unknown_claim"}}
            order_id = last_result.get("order_id")
            principal_id = last_result.get("principal_id")
            state["order_id"] = order_id
            state["principal_id"] = principal_id
            trace.add(
                "react_step",
                {
                    "step": state["step"],
                    "tool": "get_claim_view",
                    "found": True,
                    "has_order_id": bool(order_id),
                },
            )
            if not order_id:
                return {"final": {"status": "needs_info", "proposal_amount": 0, "reason": "missing_order_id"}}
            return {
                "tool": "lookup_order",
                "args": {"order_id": order_id, "principal_id": principal_id},
            }

        if last_tool == "lookup_order":
            trace.add("react_step", {"step": state["step"], "tool": "lookup_order", "result": last_result})
            if not last_result.get("visible"):
                return {
                    "final": {
                        "status": "escalated",
                        "proposal_amount": 0,
                        "reason": last_result.get("reason"),
                    }
                }
            state["order"] = dict(last_result["order"])
            return {"tool": "lookup_policy", "args": {}}

        if last_tool == "lookup_policy":
            policy_ids = [p["policy_id"] for p in (last_result.get("policies") or [])]
            trace.add("react_step", {"step": state["step"], "tool": "lookup_policy", "policy_ids": policy_ids})
            return {
                "tool": "lookup_refund_history",
                "args": {"order_id": state["order_id"], "principal_id": state["principal_id"]},
            }

        if last_tool == "lookup_refund_history":
            trace.add("react_step", {"step": state["step"], "tool": "lookup_refund_history", "result": last_result})
            return {"tool": "compute_compensation", "args": {"order": state["order"]}}

        if last_tool == "compute_compensation":
            state["quote"] = last_result
            trace.add("react_step", {"step": state["step"], "tool": "compute_compensation", "quote": last_result})
            proposal = int(last_result["amount_vnd"])
            return {
                "final": {
                    "status": "propose" if proposal > 0 else "denied",
                    "proposal_amount": proposal,
                    "reason": last_result.get("reason"),
                }
            }

        return {"final": {"status": "failed", "proposal_amount": 0, "reason": f"unexpected_tool:{last_tool}"}}

    react_outcome = run_react(
        conn,
        budget,
        observation={"claim_id": claim_id},
        decide=decide,
        max_steps=8,
        worker=True,
    )

    if react_outcome["stopped"] == "step_cap":
        trace.add("decision", {"status": "failed", "reason": "step_cap"})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="step_cap",
        )

    final = react_outcome["final"]
    final_status = final["status"]
    if final_status in ("failed", "needs_info", "escalated"):
        trace.add("decision", {"status": final_status, "reason": final.get("reason")})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=final_status,
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=final.get("reason"),
        )

    proposal = int(final.get("proposal_amount") or 0)
    if proposal <= 0:
        trace.add("decision", {"status": "denied", "proposal_amount": 0, "reason": final.get("reason")})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=final.get("reason"),
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
            shape="single",
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
        shape="single",
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )
