<h1 align="center">
  <br>
  LogWhisperer
  <br>
</h1>

<p align="center">
  <b>CLI log pattern analysis &amp; anomaly detection tool</b><br>
  <a href="https://pypi.org/project/log-whisperer/"><img src="https://img.shields.io/pypi/v/log-whisperer" alt="PyPI"></a>
  <a href="https://pypi.org/project/log-whisperer/"><img src="https://img.shields.io/pypi/pyversions/log-whisperer" alt="Python versions"></a>
  <a href="https://github.com/Nao-Intelligence/log-whisperer/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/log-whisperer" alt="License"></a>
</p>

<p align="center">
  <a href="#installation">Installation</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#sources">Sources</a> &bull;
  <a href="#pattern-engine">Pattern Engine</a> &bull;
  <a href="#baseline-learning">Baseline Learning</a> &bull;
  <a href="#notifications">Notifications</a> &bull;
  <a href="#recipes">Recipes</a>
</p>

---

## What Is LogWhisperer?

LogWhisperer reads logs from **multiple sources** (Docker containers, Compose
services, systemd journals, plain files), **normalizes** variable data out of
each line (IPs, UUIDs, timestamps, paths, numbers), and **clusters** them into
patterns.  It remembers every pattern it has ever seen and tells you which ones
are **new**.

```
                 ┌───────────┐
  docker logs ──>│           │     normalize      cluster       diff
  compose     ──>│  Sources  │──> "ERROR <IP>" ──> pattern A ──> [NEW]
  journalctl  ──>│           │    "INFO <UUID>"    pattern B     [seen]
  plain file  ──>└───────────┘                     pattern C     [NEW]
                                                       │
                                       ┌───────────────┼───────────────┐
                                       ▼               ▼               ▼
                                   patterns.db     text/JSON       alerts
                                   (JSON-lines)     report      (ntfy/tg/email)
```

---

## Installation

### From PyPI (recommended)

```bash
pip install log-whisperer
```

Or with [pipx](https://pipx.pypa.io/) for an isolated install:

```bash
pipx install log-whisperer
```

### From source (development)

```bash
git clone https://github.com/Nao-Intelligence/log-whisperer.git
cd log-whisperer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify

```bash
log-whisperer --help
```

---

## Quick Start

**1. Analyse a log file**

```bash
log-whisperer --file /var/log/syslog --show-samples
```

**2. See only never-before-seen patterns**

```bash
log-whisperer --file /var/log/syslog --show-new
```

**3. First run shows `[NEW]`, second run shows `[seen]`**

```bash
$ log-whisperer --file app.log
[NEW][ERROR] x12    total=12       ERROR something failed with code <N>
[NEW][INFO]  x841   total=841      INFO  request from <IP> processed in <N>ms

$ log-whisperer --file app.log
[seen][ERROR] x12   total=24       ERROR something failed with code <N>
[seen][INFO]  x841  total=1682     INFO  request from <IP> processed in <N>ms
```

---

## Usage

```
log-whisperer [SOURCE] [OPTIONS]
```

### Source Flags

> Exactly **one** source must be specified (unless using `--reset`).

| Flag | Description | Example |
|:-----|:------------|:--------|
| `--file PATH` | Read from a plain text file | `--file /var/log/app.log` |
| `--docker NAME` | Read from a Docker container | `--docker my-api` |
| `--compose SERVICE` | Read from a Compose service | `--compose web` |
| `--compose-all` | Read from **all** Compose services | `--compose-all` |
| `--service UNIT` | Read from a systemd journal unit | `--service nginx` |

### Display Options

| Flag | Default | Description |
|:-----|:--------|:------------|
| `--show-samples` | off | Print one raw sample line per pattern |
| `--show-new` | off | Only display patterns never seen before |
| `--min-severity` | `INFO` | Filter output: `INFO`, `WARN`, or `ERROR` |
| `--json` | off | Output the full report as JSON |

### Window Options

| Flag | Default | Description |
|:-----|:--------|:------------|
| `--since` | `1h` | Time window passed to docker/journalctl (e.g. `10m`, `1h`, `today`) |
| `--lines` | `5000` | Maximum number of lines to process |

### State Management

| Flag | Default | Description |
|:-----|:--------|:------------|
| `--state-db PATH` | `~/.local/state/logwhisperer/patterns.db` | Pattern database file |
| `--baseline-state PATH` | `~/.local/state/logwhisperer/baseline.json` | Baseline state file |
| `--baseline-learn DURATION` | — | Enter baseline learning mode (e.g. `24h`, `30m`) |
| `--reset` | off | Delete the pattern DB and baseline state |

### Notification Flags

| Flag | Env Variable | Description |
|:-----|:-------------|:------------|
| `--notify-ntfy-topic` | `LOGWHISPERER_NTFY_TOPIC` | ntfy topic name |
| `--notify-ntfy-server` | `LOGWHISPERER_NTFY_SERVER` | ntfy server URL (default: `https://ntfy.sh`) |
| `--notify-telegram-token` | `LOGWHISPERER_TELEGRAM_TOKEN` | Telegram bot token |
| `--notify-telegram-chat-id` | `LOGWHISPERER_TELEGRAM_CHAT_ID` | Telegram chat ID |
| `--notify-email-host` | `LOGWHISPERER_SMTP_HOST` | SMTP server hostname |
| `--notify-email-port` | `LOGWHISPERER_SMTP_PORT` | SMTP port (default: `587`) |
| `--notify-email-user` | `LOGWHISPERER_SMTP_USER` | SMTP username |
| `--notify-email-pass` | `LOGWHISPERER_SMTP_PASS` | SMTP password |
| `--notify-email-from` | `LOGWHISPERER_EMAIL_FROM` | Sender email address |
| `--notify-email-to` | `LOGWHISPERER_EMAIL_TO` | Recipient email address |
| `--notify-email-no-tls` | — | Disable STARTTLS |

---

## Sources

### Plain File

Reads the last `--lines` lines from any text file.  No external tools required.

```bash
log-whisperer --file /var/log/nginx/error.log --since 1h
```

> **Note:** `--since` is passed to docker/journalctl only.  For files, all
> lines are read and the last `--lines` are analysed.

### Docker Container

Fetches logs from a running (or stopped) container via `docker logs`.

```bash
log-whisperer --docker my-api --since 30m --show-new
```

### Docker Compose

Fetches logs from one service or all services in the current project.

```bash
# Single service
log-whisperer --compose web --since 1h

# All services
log-whisperer --compose-all --since 1h
```

### systemd Journal

Reads from `journalctl` for a specific unit, with bare message output (`-o cat`).

```bash
log-whisperer --service nginx --since today
```

---

## Pattern Engine

### How Normalisation Works

LogWhisperer transforms each raw log line into a **pattern** by replacing
variable data with fixed placeholders:

```
Raw:    2024-03-15T10:23:45 ERROR Connection to 192.168.1.42 failed (attempt 3)
Pattern:                    ERROR Connection to <IP> failed (attempt <N>)
```

The following substitutions are applied **in order**:

| Data Type | Example | Placeholder |
|:----------|:--------|:------------|
| Timestamp prefix | `2024-03-15T10:23:45` | *(stripped)* |
| Syslog prefix | `Mar 15 10:23:45 host app:` | *(stripped)* |
| UUID | `550e8400-e29b-41d4-a716-446655440000` | `<UUID>` |
| Hash (32-64 hex chars) | `d41d8cd98f00b204e9800998ecf8427e` | `<HASH>` |
| IPv4 address | `192.168.1.42` | `<IP>` |
| MAC address | `aa:bb:cc:dd:ee:ff` | `<MAC>` |
| Hex literal | `0x1A2F` | `<HEX>` |
| File path | `/usr/local/bin/app` | `<PATH>` |
| Number | `42`, `3000` | `<N>` |

> **Order matters.** UUIDs and long hashes are matched *before* the generic
> number pattern to prevent partial replacement (e.g. a UUID being half-replaced
> with `<N>`).

### Pattern Hashing

Each normalized pattern is hashed with **SHA-1** to produce a stable identifier.
Two log lines that normalize to the same string will always share the same hash
and be counted together.

### Severity Classification

Patterns are classified by scanning for keywords (case-insensitive):

| Severity | Keywords |
|:---------|:---------|
| **ERROR** | `error`, `fatal`, `exception`, `traceback`, `panic`, `segfault`, `failed`, `failure`, `critical` |
| **WARN** | `warn`, `warning`, `timeout`, `timed out`, `retry`, `throttle`, `rate limit`, `deprecated`, `slow`, `unavailable` |
| **INFO** | Everything else |

Use `--min-severity` to filter the report output:

```bash
# Only show warnings and errors
log-whisperer --file app.log --min-severity WARN

# Only show errors
log-whisperer --file app.log --min-severity ERROR
```

> **Note:** Patterns below the severity threshold are still recorded in the
> database — they just don't appear in the report.

---

## Baseline Learning

When you first deploy LogWhisperer against a service, *every* pattern is new.
**Baseline learning** lets the tool silently learn existing patterns for a
set period before it starts alerting.

```bash
# Learn patterns for the next 24 hours — no alerts during this time
log-whisperer --file app.log --baseline-learn 24h
```

```
Baseline learning enabled until 2024-03-16 10:30:00. (No alerts during this period)
```

During baseline learning:
- All patterns are recorded in the database as usual.
- The report still shows `[NEW]` / `[seen]` tags.
- **No alert notifications are dispatched.**

Once the learning window expires, any genuinely new pattern will trigger alerts.

### Duration Format

| Example | Meaning |
|:--------|:--------|
| `30s` | 30 seconds |
| `10m` | 10 minutes |
| `2h` | 2 hours |
| `1d` | 1 day |

---

## State & Database

### Pattern Database

The pattern DB is a **JSON-lines** file (one JSON object per line):

```bash
$ cat ~/.local/state/logwhisperer/patterns.db
{"h":"d72cb82a...","first_seen":1710500000,"last_seen":1710503600,"total_seen":47,"severity":"ERROR","pattern":"ERROR something failed","sample":"2024-03-15 ERROR something failed"}
{"h":"8c39b05a...","first_seen":1710500000,"last_seen":1710503600,"total_seen":1203,"severity":"INFO","pattern":"INFO all good","sample":"2024-03-15 INFO all good"}
```

You can inspect it with standard tools:

```bash
# Pretty-print all entries
cat ~/.local/state/logwhisperer/patterns.db | jq .

# Count total patterns
wc -l ~/.local/state/logwhisperer/patterns.db

# Find ERROR patterns
grep '"severity":"ERROR"' ~/.local/state/logwhisperer/patterns.db | jq .
```

### Concurrency Safety

The database uses **file-level locking** (`fcntl.flock`):

- **Readers** acquire a shared lock — multiple concurrent reads are safe.
- **Writers** acquire an exclusive lock — writes are serialized.

This prevents corruption when two cron jobs overlap.

### Reset

To clear all learned patterns and start fresh:

```bash
log-whisperer --reset --file /dev/null
```

### Custom State Location

```bash
log-whisperer --file app.log \
  --state-db /opt/logwhisperer/myapp.db \
  --baseline-state /opt/logwhisperer/myapp-baseline.json
```

---

## Notifications

LogWhisperer can alert you when **new patterns appear** (outside baseline
learning mode).  Configure one or more channels:

### ntfy

[ntfy](https://ntfy.sh) is a simple pub/sub notification service.

```bash
log-whisperer --file app.log \
  --notify-ntfy-topic my-alerts \
  --notify-ntfy-server https://ntfy.sh
```

Or via environment variables:

```bash
export LOGWHISPERER_NTFY_TOPIC=my-alerts
log-whisperer --file app.log
```

### Telegram

```bash
log-whisperer --file app.log \
  --notify-telegram-token "123456:ABC-DEF..." \
  --notify-telegram-chat-id "-100123456789"
```

Or via environment:

```bash
export LOGWHISPERER_TELEGRAM_TOKEN="123456:ABC-DEF..."
export LOGWHISPERER_TELEGRAM_CHAT_ID="-100123456789"
```

### Email (SMTP)

```bash
log-whisperer --file app.log \
  --notify-email-host smtp.gmail.com \
  --notify-email-port 587 \
  --notify-email-user me@gmail.com \
  --notify-email-pass "app-password" \
  --notify-email-from me@gmail.com \
  --notify-email-to ops-team@company.com
```

Use `--notify-email-no-tls` to disable STARTTLS for local/internal relays.

### Alert Format

When new patterns are detected, all configured channels receive a message like:

```
Log Whisperer ALERT (2 new patterns)
Source: file:/var/log/app.log | since=1h

[NEW][ERROR] x5  ERROR connection to <IP> refused
sample: 2024-03-15 10:23:45 ERROR connection to 10.0.0.3 refused

[NEW][WARN] x12  WARN request latency <N>ms exceeds threshold
sample: 2024-03-15 10:24:01 WARN request latency 3502ms exceeds threshold
```

> **Tip:** Multiple channels can be configured simultaneously.  A failure in
> one channel does not block delivery to the others.

---

## JSON Output

Use `--json` for machine-readable output (piping, dashboards, further processing):

```bash
log-whisperer --file app.log --json | python3 -m json.tool
```

```json
{
  "source": "file:app.log",
  "since": "1h",
  "lines_limit": 5000,
  "state_db": "/home/user/.local/state/logwhisperer/patterns.db",
  "baseline_active": false,
  "baseline_until": 0,
  "generated_at": 1710503600,
  "items": [
    {
      "tag": "NEW",
      "count_window": 5,
      "total_seen": 5,
      "severity": "ERROR",
      "pattern": "ERROR connection to <IP> refused",
      "sample": "2024-03-15 10:23:45 ERROR connection to 10.0.0.3 refused",
      "hash": "a1b2c3d4..."
    }
  ]
}
```

### Useful jq Queries

```bash
# Count of new patterns only
log-whisperer --file app.log --json | jq '[.items[] | select(.tag == "NEW")] | length'

# List ERROR patterns with their counts
log-whisperer --file app.log --json | jq '.items[] | select(.severity == "ERROR") | {pattern, count_window}'

# Exit non-zero if any new ERROR patterns found
log-whisperer --file app.log --json | jq -e '[.items[] | select(.tag == "NEW" and .severity == "ERROR")] | length > 0'
```

---

## Recipes

### Cron Job — Check Every 5 Minutes, Alert on New Patterns

```cron
*/5 * * * * /usr/local/bin/log-whisperer --file /var/log/app.log --since 5m --notify-ntfy-topic my-alerts 2>>/var/log/logwhisperer-errors.log
```

### First-Time Setup with Baseline Learning

```bash
# Step 1: Learn existing patterns for 24 hours
log-whisperer --file /var/log/app.log --baseline-learn 24h

# Step 2: Set up the cron job (alerts will start after 24h)
crontab -e
# */5 * * * * log-whisperer --file /var/log/app.log --since 5m --notify-ntfy-topic my-alerts
```

### Monitor Multiple Services

```bash
#!/bin/bash
# monitor-all.sh — run from cron

log-whisperer --docker api-server   --since 5m --state-db /var/lib/lw/api.db
log-whisperer --docker worker       --since 5m --state-db /var/lib/lw/worker.db
log-whisperer --service nginx       --since 5m --state-db /var/lib/lw/nginx.db
log-whisperer --file /var/log/app.log --since 5m --state-db /var/lib/lw/app.db
```

> Use separate `--state-db` paths to keep pattern histories isolated per service.

### Errors-Only Daily Digest

```bash
log-whisperer --file /var/log/app.log \
  --since 24h \
  --min-severity ERROR \
  --show-samples \
  --notify-email-host smtp.company.com \
  --notify-email-from lw@company.com \
  --notify-email-to oncall@company.com
```

### CI / Smoke Test — Fail If New Error Patterns Appear

```bash
log-whisperer --file test-output.log --json \
  | jq -e '[.items[] | select(.tag == "NEW" and .severity == "ERROR")] | length == 0' \
  || { echo "New error patterns detected!"; exit 1; }
```

### Pipe Logs Directly (via process substitution)

```bash
log-whisperer --file <(kubectl logs deploy/my-app --since=1h) --show-new
```

---

## Environment Variables

All notification settings can be set via environment variables so they don't
appear in process listings or shell history:

| Variable | Maps To |
|:---------|:--------|
| `LOGWHISPERER_NTFY_TOPIC` | `--notify-ntfy-topic` |
| `LOGWHISPERER_NTFY_SERVER` | `--notify-ntfy-server` |
| `LOGWHISPERER_TELEGRAM_TOKEN` | `--notify-telegram-token` |
| `LOGWHISPERER_TELEGRAM_CHAT_ID` | `--notify-telegram-chat-id` |
| `LOGWHISPERER_SMTP_HOST` | `--notify-email-host` |
| `LOGWHISPERER_SMTP_PORT` | `--notify-email-port` |
| `LOGWHISPERER_SMTP_USER` | `--notify-email-user` |
| `LOGWHISPERER_SMTP_PASS` | `--notify-email-pass` |
| `LOGWHISPERER_EMAIL_FROM` | `--notify-email-from` |
| `LOGWHISPERER_EMAIL_TO` | `--notify-email-to` |
| `XDG_STATE_HOME` | Base directory for state files (default: `~/.local/state`) |

---

## Troubleshooting

### "Command not found: docker"

The Docker or journalctl binary isn't on `$PATH`.  Make sure the relevant tool
is installed and accessible to the user running LogWhisperer.

### "Choose exactly one source"

You must specify exactly one of `--file`, `--docker`, `--compose`, `--compose-all`,
or `--service`.  You cannot combine sources in a single run.

### Every run shows `[NEW]`

Your state DB is being reset or isn't persisting.  Check:

```bash
ls -la ~/.local/state/logwhisperer/patterns.db
```

If the file doesn't exist between runs, verify that `--state-db` points to a
writable, persistent location.

### No alerts firing

- Check that baseline learning has expired: look for `Baseline: ACTIVE` in the
  text report output.
- Alerts only fire for `[NEW]` patterns — if all patterns are `[seen]`, no alert
  is sent.
- Verify your notification credentials are correct by checking stderr for
  `"Notification failures:"` messages.

### Database looks corrupted

The DB is JSON-lines.  Validate it:

```bash
python3 -c "
import json, sys
for i, line in enumerate(open(sys.argv[1]), 1):
    try: json.loads(line)
    except: print(f'Bad line {i}: {line.rstrip()}')
" ~/.local/state/logwhisperer/patterns.db
```

If corruption occurred, reset and re-learn:

```bash
log-whisperer --reset --file /dev/null
log-whisperer --file /var/log/app.log --baseline-learn 1h
```

---

<p align="center">
  <sub>LogWhisperer &mdash; Built with Python 3.9+</sub>
</p>
