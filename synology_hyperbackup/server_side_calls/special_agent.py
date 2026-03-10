#!/usr/bin/env python3
"""Server-side calls for the Synology Hyper Backup special agent."""

from collections.abc import Iterator, Sequence

from pydantic import BaseModel

from cmk.server_side_calls.v1 import (
    HostConfig,
    Secret,
    SpecialAgentCommand,
    SpecialAgentConfig,
)


class Params(BaseModel):
    username: str
    password: Secret
    port: int = 5001
    no_verify_ssl: bool = False
    timeout: int = 30


def _agent_arguments(
    params: Params, host_config: HostConfig
) -> Iterator[SpecialAgentCommand]:
    # Prefer the primary IP address; fall back to the hostname
    host = (
        host_config.primary_ip_config.address
        if host_config.primary_ip_config.address
        and host_config.primary_ip_config.address != "0.0.0.0"
        else host_config.name
    )

    args: list[str | Secret] = [
        "--host", host,
        "--port", str(params.port),
        "--username", params.username,
        "--password", params.password.unsafe("%s"),
        "--timeout", str(params.timeout),
    ]

    if params.no_verify_ssl:
        args.append("--no-verify-ssl")

    yield SpecialAgentCommand(command_arguments=args)


special_agent_synology_hyperbackup = SpecialAgentConfig(
    name="synology_hyperbackup",
    parameter_parser=Params.model_validate,
    commands_function=_agent_arguments,
)
