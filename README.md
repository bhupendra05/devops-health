# devops-health

> SSH-based server health dashboard — check CPU, memory, disk, uptime, and services across all your servers from a single command.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Multi-server dashboard** — parallel SSH checks, summary table in seconds
- **Detailed per-host view** — CPU load, memory, swap, disk, top processes
- **Service status** — check `systemctl` status for any services (nginx, postgres, etc.)
- **Live watch mode** — auto-refresh dashboard every N seconds
- **Quick one-off check** — no config file needed for a single host
- **JSON output** — for alerting pipelines, Slack bots, monitoring scripts
- **Zero agents on servers** — pure SSH + shell commands, nothing to install remotely

## What it checks

| Metric | Source |
|--------|--------|
| Uptime | `/proc/uptime` |
| CPU load (1m/5m/15m) | `/proc/loadavg` |
| Memory / Swap | `/proc/meminfo` |
| Disk usage | `df` |
| Top 5 processes | `ps aux` |
| Service status | `systemctl is-active` |

## Installation

```bash
git clone https://github.com/bhupendra05/devops-health.git
cd devops-health
pip install -e .
```

## Setup

```bash
# Create a starter config
devops-health init

# Edit with your servers
nano hosts.yml
```

`hosts.yml` example:
```yaml
hosts:
  - name: web-01
    hostname: 192.168.1.10
    user: ubuntu
    key_file: ~/.ssh/id_rsa
    tags: [web, production]

  - name: db-01
    hostname: db.example.com
    user: ubuntu
    key_file: ~/.ssh/id_rsa
```

## Usage

### Summary dashboard (all hosts)

```bash
devops-health check
```

### Detailed view per host

```bash
devops-health check --detail

# Single host detail
devops-health check --host web-01
```

### Check specific services

```bash
devops-health check --services nginx,postgres,redis
```

### Live auto-refresh

```bash
# Refresh every 30s (default)
devops-health watch

# Custom interval
devops-health watch --interval 10
```

### Quick one-off check (no config needed)

```bash
devops-health quickcheck myserver.com --user ubuntu --key ~/.ssh/id_rsa
devops-health quickcheck 192.168.1.10 --services nginx,postgres
```

### JSON output for scripting

```bash
devops-health check --json | jq '.[] | select(.cpu_pct > 80)'
devops-health check --json | jq '.[] | {host, mem_pct, disks}'
```

## Example Output

```
 Server Health Dashboard
┌──────────┬──────────┬─────────┬──────────────┬─────────────────────┬─────────────────┬─────────┐
│ Host     │ Status   │ Uptime  │ CPU (1m)     │ Memory              │ Disk (/)        │ Latency │
├──────────┼──────────┼─────────┼──────────────┼─────────────────────┼─────────────────┼─────────┤
│ web-01   │ ✓ OK     │ 12d 4h  │ 0.42 (21%)   │ ████████░░░░ 65.2%  │ ███████░░░ 71%  │ 45ms    │
│ db-01    │ ✓ OK     │ 8d 2h   │ 1.20 (60%)   │ ██████████░░ 84.1%  │ ██████████ 91%  │ 62ms    │
└──────────┴──────────┴─────────┴──────────────┴─────────────────────┴─────────────────┴─────────┘
⚠ Disk usage ≥90% on: db-01
```

## Screenshots

![devops-health demo](docs/demo.png)

## Project Structure

```
devops-health/
├── devops_health/
│   ├── cli.py        # Click CLI (check / watch / init / quickcheck)
│   ├── collector.py  # SSH metric collection via fabric
│   ├── config.py     # YAML host inventory loader
│   └── display.py    # Rich terminal rendering
├── hosts.example.yml
├── requirements.txt
└── setup.py
```

## License

MIT © bhupendra05
