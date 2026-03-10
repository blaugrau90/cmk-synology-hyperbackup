# Synology Hyper Backup – Checkmk 2.4 Plugin

A Checkmk 2.4 MKP plugin that monitors all **Synology Hyper Backup** tasks on a DSM 7.x NAS via the DSM Web API. It reports task state, last backup age, schedule adherence and encryption status for every configured backup task.

**Requires:** Checkmk 2.4.0+ · Synology DSM 7.x · MIT License

---

## Features

- Monitors **all Hyper Backup tasks** automatically (local, image, S3 cloud)
- Reports **backup age** with configurable warn/crit thresholds
- Detects **missed scheduled backups**: CRIT fires exactly when the next scheduled run was due
- All **DSM task states configurable** (backupable, error_detect, running, detect_running, …)
- Shows **target type**, **transport**, **encryption** and next scheduled run time
- Uses only Synology's official DSM Web API — no SSH, no Synology agent required

---

## Requirements

| Component | Version |
|---|---|
| Checkmk | 2.4.0+ (CRE/CEE/CME) |
| Synology DSM | 7.x |
| DSM user | Member of the **administrators** group |
| Network | Checkmk server must reach DSM HTTPS port (default 5001) |

---

## Installation

### Via Checkmk GUI (recommended)

1. Go to **Setup → Extension Packages**
2. Click **Upload package** and select `synology_hyperbackup-1.0.0.mkp`
3. Enable the package

### Via CLI (as site user)

```bash
mkp add synology_hyperbackup-1.0.0.mkp
mkp enable synology_hyperbackup
```

---

## Configuration

### Step 1 – Prepare the Synology Host in Checkmk

Create (or edit) the host representing your Synology NAS:

- Set **"Checkmk agent / API integrations"** to **"Configured API integrations, no Checkmk agent"**

### Step 2 – Create a Special Agent Rule

Navigate to **Setup → Other integrations → Synology Hyper Backup** and create a rule for your NAS host:

| Field | Value |
|---|---|
| DSM Username | DSM admin account |
| Password | DSM password (stored as Checkmk secret) |
| HTTPS Port | 5001 (default) |
| Disable SSL verification | Enable if using self-signed certificates |
| Request timeout | 30 s (default) |

### Step 3 – Run Service Discovery

Execute a service discovery on the host. One service **"Hyper Backup \<task name\>"** will be created for each backup task.

### Step 4 – Adjust Check Parameters (optional)

Navigate to **Setup → Service monitoring rules → Synology Hyper Backup** to override thresholds per host or task:

| Parameter | Default | Description |
|---|---|---|
| Warning threshold | 24 h | Warn if last backup is older than this |
| Critical threshold | 48 h | CRIT if last backup is older than this |
| Alert on missed schedule | Enabled | CRIT fires exactly when `next_trigger_time` is exceeded |
| DSM state mapping | see below | Map each DSM state to OK / Warning / Critical / Unknown |

---

## How It Works

```
Checkmk Check Cycle
  └─ Special Agent (libexec/agent_synology_hyperbackup)
       ├─ 1. Login  →  SYNO.API.Auth v6  →  session SID
       ├─ 2. Tasks  →  SYNO.Backup.Task v1 list + schedule  →  task list
       ├─ 3. Log    →  SYNO.SDS.Backup.Client.Common.Log v1  →  500 entries
       │              Parse newest "Backup task finished/failed" per task
       └─ 4. Logout →  SYNO.API.Auth v6
  └─ Checkmk Section  <<<synology_hyperbackup:sep(0)>>>
       One JSON line per task
  └─ Agent-Based Check Plugin (agent_based/synology_hyperbackup.py)
       ├─ State evaluation (configurable per DSM state string)
       ├─ Schedule check (disabled schedule → configurable state)
       ├─ Dynamic CRIT: crit_age = next_trigger_time − last_backup_time
       └─ check_levels() for backup_age metric with warn/crit thresholds
```

### Dynamic CRIT threshold

When **"Alert on missed schedule"** is enabled, the CRIT threshold is computed dynamically:

```
crit_age = next_trigger_time − last_backup_time
```

This means CRIT fires **exactly** when the scheduled backup was due — independently of the fixed age thresholds.

---

## DSM Task States

| DSM State | Meaning | Default CMK State | Configurable |
|---|---|---|---|
| `backupable` | Task ready / last backup OK | OK | yes |
| `error_detect` | Integrity check failed | CRIT | yes |
| `running` | Backup in progress | OK | yes |
| `backup_running` | Backup in progress (alt.) | OK | yes |
| `detect_running` | Integrity check running | OK | yes |
| *(schedule disabled)* | `schedule_enable = false` | WARNING | yes |
| *(any other)* | Unknown DSM state | UNKNOWN | — |

---

## File Structure

```
synology_hyperbackup/
├── agent_based/
│   └── synology_hyperbackup.py      # Check plugin: parse, discover, check
├── libexec/
│   └── agent_synology_hyperbackup   # Special agent: DSM API → CMK section
├── rulesets/
│   └── synology_hyperbackup.py      # GUI rulesets: special agent + check params
└── server_side_calls/
    └── special_agent.py             # CLI argument builder (Pydantic + Secret)
```

### `libexec/agent_synology_hyperbackup`

Standalone Python 3 script (stdlib only). Connects to DSM, fetches task list and log, outputs one JSON line per task to stdout.

**CLI arguments:**

```
--host HOST          DSM hostname or IP
--port PORT          HTTPS port (default: 5001)
--username USER      DSM username
--password PASS      DSM password
--no-verify-ssl      Skip SSL certificate verification
--timeout SECS       Request timeout (default: 30)
```

**Output format:**

```
<<<synology_hyperbackup:sep(0)>>>
{"task_id": 63, "name": "Wasabi - Dokumente", "state": "backupable", "status": "none",
 "target_type": "cloud_image", "transfer_type": "aws_s3", "data_enc": true,
 "schedule_enable": true, "next_trigger_time": "2026-03-11 19:50",
 "last_backup_time": 1773170478, "last_backup_result": "success"}
```

### `agent_based/synology_hyperbackup.py`

Checkmk 2.4 agent-based plugin using `cmk.agent_based.v2`. Parses the section, discovers one service per task, evaluates state and backup age.

### `server_side_calls/special_agent.py`

Translates GUI parameters (Pydantic `Params` model) into CLI arguments for the special agent. Handles password secrets via `Secret.unsafe("%s")`.

### `rulesets/synology_hyperbackup.py`

Defines two rulesets:
- **Special Agent ruleset** (`SpecialAgent`) — connection parameters
- **Check Parameters ruleset** (`CheckParameters`) — thresholds and state mapping

---

## Building from Source

```bash
# On the Checkmk site (as site user)
mkp package /path/to/manifest_file
```

The manifest file must list all four files under `cmk_addons_plugins`.

---

## License

MIT — see [LICENSE](../LICENSE)

## Author

Luca-Leon Hausdoerfer — [github.com/blaugrau90](https://github.com/blaugrau90)
