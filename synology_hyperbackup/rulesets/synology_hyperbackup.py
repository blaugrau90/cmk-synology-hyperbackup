#!/usr/bin/env python3
"""Rulesets for the Synology Hyper Backup special agent and check plugin."""

from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
    Password,
    SingleChoice,
    SingleChoiceElement,
    String,
    TimeMagnitude,
    TimeSpan,
    migrate_to_password,
    validators,
)
from cmk.rulesets.v1.rule_specs import (
    CheckParameters,
    Help,
    HostAndItemCondition,
    SpecialAgent,
    Title,
    Topic,
)


# ---------------------------------------------------------------------------
# Special Agent Ruleset
# ---------------------------------------------------------------------------

def _special_agent_formspec() -> Dictionary:
    return Dictionary(
        title=Title("Synology Hyper Backup"),
        help_text=Help(
            "Connect to the Synology DSM Web API to monitor all Hyper Backup tasks. "
            "The configured user must be a member of the administrators group."
        ),
        elements={
            "username": DictElement(
                required=True,
                parameter_form=String(
                    title=Title("DSM Username"),
                    help_text=Help(
                        "DSM user account with administrator privileges for API access."
                    ),
                ),
            ),
            "password": DictElement(
                required=True,
                parameter_form=Password(
                    title=Title("Password"),
                    migrate=migrate_to_password,
                ),
            ),
            "port": DictElement(
                required=True,
                parameter_form=Integer(
                    title=Title("HTTPS Port"),
                    help_text=Help("DSM HTTPS port. Default: 5001."),
                    prefill=DefaultValue(5001),
                    custom_validate=(
                        validators.NumberInRange(min_value=1, max_value=65535),
                    ),
                ),
            ),
            "no_verify_ssl": DictElement(
                required=True,
                parameter_form=BooleanChoice(
                    title=Title("Disable SSL certificate verification"),
                    help_text=Help(
                        "Warning: Disabling SSL verification reduces security. "
                        "Enable this only when using self-signed certificates."
                    ),
                    prefill=DefaultValue(False),
                ),
            ),
            "timeout": DictElement(
                required=True,
                parameter_form=Integer(
                    title=Title("Request timeout (seconds)"),
                    prefill=DefaultValue(30),
                    custom_validate=(
                        validators.NumberInRange(min_value=5, max_value=300),
                    ),
                ),
            ),
        },
    )


rule_spec_synology_hyperbackup_agent = SpecialAgent(
    topic=Topic.STORAGE,
    name="synology_hyperbackup",
    title=Title("Synology Hyper Backup"),
    parameter_form=_special_agent_formspec,
)


# ---------------------------------------------------------------------------
# Check Parameters Ruleset
# ---------------------------------------------------------------------------

def _check_parameters_formspec() -> Dictionary:
    return Dictionary(
        title=Title("Synology Hyper Backup"),
        elements={
            "warn_age": DictElement(
                required=True,
                parameter_form=TimeSpan(
                    title=Title("Warning threshold for backup age"),
                    help_text=Help(
                        "Warn if the last successful backup is older than this value. "
                        "Default: 24 hours."
                    ),
                    displayed_magnitudes=[
                        TimeMagnitude.MINUTE,
                        TimeMagnitude.HOUR,
                        TimeMagnitude.DAY,
                    ],
                    prefill=DefaultValue(86400.0),
                ),
            ),
            "crit_age": DictElement(
                required=True,
                parameter_form=TimeSpan(
                    title=Title("Critical threshold for backup age"),
                    help_text=Help(
                        "Critical if the last successful backup is older than this value. "
                        "Default: 48 hours."
                    ),
                    displayed_magnitudes=[
                        TimeMagnitude.MINUTE,
                        TimeMagnitude.HOUR,
                        TimeMagnitude.DAY,
                    ],
                    prefill=DefaultValue(172800.0),
                ),
            ),
            "check_missed_schedule": DictElement(
                required=True,
                parameter_form=BooleanChoice(
                    title=Title("Alert on missed scheduled backup"),
                    help_text=Help(
                        "Trigger a Critical alert if the scheduled backup time has passed "
                        "but no backup has run since then. Detects missed runs independently "
                        "of the age thresholds above."
                    ),
                    prefill=DefaultValue(True),
                ),
            ),
            "states": DictElement(
                required=True,
                parameter_form=Dictionary(
                    title=Title("DSM task state mapping"),
                    help_text=Help(
                        "Map each DSM task state to a Checkmk monitoring state. "
                        "Unknown DSM states not listed here always result in Unknown."
                    ),
                    elements={
                        "backupable": DictElement(
                            required=True,
                            parameter_form=SingleChoice(
                                title=Title("backupable – task ready / last backup OK"),
                                elements=[
                                    SingleChoiceElement(name="ok",      title=Title("OK")),
                                    SingleChoiceElement(name="warn",    title=Title("Warning")),
                                    SingleChoiceElement(name="crit",    title=Title("Critical")),
                                    SingleChoiceElement(name="unknown", title=Title("Unknown")),
                                ],
                                prefill=DefaultValue("ok"),
                            ),
                        ),
                        "error_detect": DictElement(
                            required=True,
                            parameter_form=SingleChoice(
                                title=Title("error_detect – integrity check failed"),
                                elements=[
                                    SingleChoiceElement(name="ok",      title=Title("OK")),
                                    SingleChoiceElement(name="warn",    title=Title("Warning")),
                                    SingleChoiceElement(name="crit",    title=Title("Critical")),
                                    SingleChoiceElement(name="unknown", title=Title("Unknown")),
                                ],
                                prefill=DefaultValue("crit"),
                            ),
                        ),
                        "running": DictElement(
                            required=True,
                            parameter_form=SingleChoice(
                                title=Title("running – backup in progress"),
                                elements=[
                                    SingleChoiceElement(name="ok",      title=Title("OK")),
                                    SingleChoiceElement(name="warn",    title=Title("Warning")),
                                    SingleChoiceElement(name="crit",    title=Title("Critical")),
                                    SingleChoiceElement(name="unknown", title=Title("Unknown")),
                                ],
                                prefill=DefaultValue("ok"),
                            ),
                        ),
                        "backup_running": DictElement(
                            required=True,
                            parameter_form=SingleChoice(
                                title=Title("backup_running – backup in progress (alt.)"),
                                elements=[
                                    SingleChoiceElement(name="ok",      title=Title("OK")),
                                    SingleChoiceElement(name="warn",    title=Title("Warning")),
                                    SingleChoiceElement(name="crit",    title=Title("Critical")),
                                    SingleChoiceElement(name="unknown", title=Title("Unknown")),
                                ],
                                prefill=DefaultValue("ok"),
                            ),
                        ),
                        "detect_running": DictElement(
                            required=True,
                            parameter_form=SingleChoice(
                                title=Title("detect_running – integrity check running"),
                                elements=[
                                    SingleChoiceElement(name="ok",      title=Title("OK")),
                                    SingleChoiceElement(name="warn",    title=Title("Warning")),
                                    SingleChoiceElement(name="crit",    title=Title("Critical")),
                                    SingleChoiceElement(name="unknown", title=Title("Unknown")),
                                ],
                                prefill=DefaultValue("ok"),
                            ),
                        ),
                        "schedule_disabled": DictElement(
                            required=True,
                            parameter_form=SingleChoice(
                                title=Title("Schedule disabled"),
                                elements=[
                                    SingleChoiceElement(name="ok",      title=Title("OK")),
                                    SingleChoiceElement(name="warn",    title=Title("Warning")),
                                    SingleChoiceElement(name="crit",    title=Title("Critical")),
                                    SingleChoiceElement(name="unknown", title=Title("Unknown")),
                                ],
                                prefill=DefaultValue("warn"),
                            ),
                        ),
                    },
                    ignored_elements=(),
                ),
            ),
        },
    )


rule_spec_synology_hyperbackup_check = CheckParameters(
    title=Title("Synology Hyper Backup"),
    topic=Topic.STORAGE,
    name="synology_hyperbackup",
    parameter_form=_check_parameters_formspec,
    condition=HostAndItemCondition(item_title=Title("Backup Task Name")),
)
