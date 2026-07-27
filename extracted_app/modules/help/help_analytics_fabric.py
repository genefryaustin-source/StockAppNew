import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_analytics_fabric_help():
    st.title("🏛️ Analytics Fabric Help — Runtime, Diagnostics, Self-Healing")
    _section("Analytics Fabric overview", """
Analytics Fabric is the operational layer for advanced analytics execution. It moves the platform beyond static analytics into scheduled, governed, monitored, and self-healing research operations.
""", True)
    _section("Major components", """
- Analytics scheduler.
- Universe analytics orchestrator.
- Resource governor.
- Autonomous optimizer.
- Universe job registry.
- Execution queue.
- Workload balancer.
- Runtime controller.
- Diagnostics engine.
- Self-healing engine.
- Command center dashboards.
""", True)
    _section("Diagnostic engine", """
## Purpose
Evaluate system health and produce findings.

## Typical outputs
- Health score.
- Risk score.
- Component status.
- Anomaly findings.
- Predicted failures.
- Recommended recovery actions.
""")
    _section("Self-healing engine", """
## Purpose
Generate recovery plans from diagnostic findings.

## Capabilities
- Dry-run recovery plans.
- Approval-aware healing.
- Retry or quarantine failed jobs.
- Reset stuck execution state.
- Rebalance workloads.
- Export healing reports.
""")
    _section("Operations center workflow", """
1. Open Analytics Operations Center.
2. Review job queue and runtime status.
3. Check governor/resource pressure.
4. Review diagnostics.
5. Generate or approve healing plans.
6. Re-run failed analytics jobs.
7. Export results if needed.
""")
    _section("Common failures", """
## Analytics jobs stuck
Check leases, worker heartbeats, execution queue, and database transactions.

## Provider throttling
Use provider health and failover dashboards.

## Resource pressure
Reduce batch size or symbol count; use scheduler/governor.

## Rankings stale
Confirm analytics snapshots and latest market data.
""", True)

def render_help():
    render_analytics_fabric_help()
