#!/usr/bin/env python3
"""Checkmk 2.4 agent-based check plugin for Synology Hyper Backup.

Section: synology_hyperbackup
One JSON object per line, keyed by task name.

DSM task states:
  backupable    -> task is ready / last backup succeeded
  error_detect  -> integrity check failed
  running       -> backup currently in progress
  backup_running-> backup currently in progress (alt.)
  detect_running-> integrity check currently running
  <unknown>     -> mapped to UNKNOWN

All states and the schedule_disabled condition are configurable via
the check parameters ruleset (defaults shown above).
"""

import json
import time
from datetime import datetime
from typing import Any

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    check_levels,
    render,
)

# Map configured state strings ("ok"/"warn"/"crit"/"unknown") to CMK State
_STR_TO_STATE: dict[str, State] = {
    "ok": State.OK,
    "warn": State.WARN,
    "crit": State.CRIT,
    "unknown": State.UNKNOWN,
}

# Human-readable labels for DSM state strings
_STATE_LABEL: dict[str, str] = {
    "backupable": "ready",
    "error_detect": "integrity check failed",
    "running": "backup running",
    "backup_running": "backup running",
    "detect_running": "integrity check running",
}

# Default state mapping (mirrors check_default_parameters)
_DEFAULT_STATES: dict[str, str] = {
    "backupable": "ok",
    "error_detect": "crit",
    "running": "ok",
    "backup_running": "ok",
    "detect_running": "ok",
    "schedule_disabled": "warn",
}


def parse_synology_hyperbackup(string_table: list) -> dict[str, Any]:
    """Parse agent section into a dict keyed by task name."""
    tasks: dict[str, Any] = {}
    for row in string_table:
        if not row:
            continue
        try:
            task = json.loads(row[0])
            name = task.get("name")
            if name:
                tasks[name] = task
        except (json.JSONDecodeError, KeyError):
            pass
    return tasks


def discover_synology_hyperbackup(section: dict[str, Any]) -> DiscoveryResult:
    for name in section:
        yield Service(item=name)


def check_synology_hyperbackup(
    item: str, params: dict[str, Any], section: dict[str, Any]
) -> CheckResult:
    task = section.get(item)
    if task is None:
        yield Result(state=State.UNKNOWN, summary="Task not found in agent output")
        return

    state_str = task.get("state", "unknown")
    status_str = task.get("status", "none")

    # --- Primary state from DSM task state ---
    state_params = params.get("states", _DEFAULT_STATES)
    configured = state_params.get(state_str, "unknown")
    cmk_state = _STR_TO_STATE.get(configured, State.UNKNOWN)
    state_label = _STATE_LABEL.get(state_str, state_str)

    summary_parts = [f"State: {state_label}"]
    if status_str and status_str not in ("none", ""):
        summary_parts.append(f"status: {status_str}")

    yield Result(state=cmk_state, summary=", ".join(summary_parts))

    # --- Schedule & last backup ---
    schedule_enable = task.get("schedule_enable", True)
    next_trigger = task.get("next_trigger_time")
    now = time.time()
    last_backup_time = task.get("last_backup_time")
    last_backup_result = task.get("last_backup_result")

    if not schedule_enable:
        sched_state = _STR_TO_STATE.get(state_params.get("schedule_disabled", "warn"), State.WARN)
        yield Result(state=sched_state, notice="Scheduled backups are disabled")
    elif next_trigger and next_trigger not in ("N/A", ""):
        yield Result(state=State.OK, notice=f"Next scheduled: {next_trigger}")

    # --- Determine effective CRIT threshold ---
    # When check_missed_schedule is enabled and a schedule exists, derive the CRIT
    # threshold from the next_trigger_time so that CRIT fires exactly when the
    # scheduled backup time is exceeded.  Fall back to the configured crit_age when
    # no schedule information is available.
    backup_is_running = state_str in ("running", "backup_running")
    warn_age = float(params.get("warn_age", 86400))
    crit_age = float(params.get("crit_age", 172800))

    if (
        params.get("check_missed_schedule", True)
        and schedule_enable
        and not backup_is_running
        and next_trigger
        and next_trigger not in ("N/A", "")
        and last_backup_time is not None
    ):
        try:
            next_ts = datetime.strptime(next_trigger, "%Y-%m-%d %H:%M").timestamp()
            # crit = age at which the next scheduled run was due
            crit_age = next_ts - float(last_backup_time)
            # keep warn below crit (use whichever is smaller)
            warn_age = min(warn_age, crit_age)
        except ValueError:
            pass

    if last_backup_time is not None:
        age = now - float(last_backup_time)

        yield from check_levels(
            value=age,
            metric_name="backup_age",
            levels_upper=("fixed", (warn_age, crit_age)),
            render_func=render.timespan,
            label="Last backup",
        )

        if last_backup_result == "failed":
            yield Result(state=State.CRIT, notice="Last backup ended with failure")
        elif last_backup_result == "success":
            yield Result(state=State.OK, notice="Last backup completed successfully")
    else:
        yield Result(
            state=State.UNKNOWN,
            summary="No backup completion found in log (task may not have run yet)",
        )
        yield Metric("backup_age", 0.0)

    # --- Informational ---
    target_type = task.get("target_type", "")
    transfer_type = task.get("transfer_type", "")
    data_enc = task.get("data_enc", False)
    info_parts = []
    if target_type:
        info_parts.append(f"target: {target_type}")
    if transfer_type:
        info_parts.append(f"transport: {transfer_type}")
    if data_enc:
        info_parts.append("encrypted")
    if info_parts:
        yield Result(state=State.OK, notice=", ".join(info_parts).capitalize())


agent_section_synology_hyperbackup = AgentSection(
    name="synology_hyperbackup",
    parse_function=parse_synology_hyperbackup,
)

check_plugin_synology_hyperbackup = CheckPlugin(
    name="synology_hyperbackup",
    service_name="Hyper Backup %s",
    discovery_function=discover_synology_hyperbackup,
    check_function=check_synology_hyperbackup,
    check_default_parameters={
        "warn_age": 86400,            # 24 hours
        "crit_age": 172800,           # 48 hours
        "check_missed_schedule": True,
        "states": {
            "backupable": "ok",
            "error_detect": "crit",
            "running": "ok",
            "backup_running": "ok",
            "detect_running": "ok",
            "schedule_disabled": "warn",
        },
    },
    check_ruleset_name="synology_hyperbackup",
)
