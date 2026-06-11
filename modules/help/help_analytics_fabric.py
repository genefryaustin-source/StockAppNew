# modules/help/help_analytics_fabric.py

import streamlit as st


def render_help_analytics_fabric():

    st.header("⚙ Analytics Fabric")

    st.markdown("""
Analytics Fabric powers large-scale analytics execution.

## Components

### Analytics Operations Center

Operational oversight.

### Analytics Scheduler

Schedules workloads.

### Analytics Governor

Controls execution limits.

### Analytics Optimizer

Optimizes workload execution.

### Universe Analytics Orchestrator

Coordinates analytics across symbol universes.

### Runtime Controller

Controls execution lifecycle.

### Workload Balancer

Distributes work across workers.

### Execution Queue

Tracks pending workloads.

### Resource Governor

Protects system resources.

### Self Diagnostic Engine

Identifies failures.

### Self Healing Engine

Builds recovery plans.

### Validation Engine

Validates platform integrity.
""")