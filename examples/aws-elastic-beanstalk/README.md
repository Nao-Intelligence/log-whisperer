# AWS Elastic Beanstalk Integration

> Tested on: **Docker running on 64bit Amazon Linux 2023/4.9.1**

Automatically installs and configures [Log Whisperer](https://pypi.org/project/log-whisperer/) on every EB deployment. New log patterns trigger alerts via ntfy, Telegram, or email.

## How It Works

```
eb deploy
   │
   ├─ predeploy/00_logwhisperer_cleanup.sh
   │     └─ Removes old cron entries (prevents duplicates)
   │
   └─ postdeploy/99_logwhisperer_setup.sh
         ├─ Installs/upgrades log-whisperer via pip
         ├─ Persists env vars to /opt/logwhisperer/env
         ├─ Writes /opt/logwhisperer/run.sh (analysis wrapper)
         ├─ Registers cron job (default: every 15 min)
         └─ Starts baseline learning window (default: 30 min)
```

Every cron tick, `run.sh`:
1. Finds the running app container
2. Runs `log-whisperer --docker <container-id>`
3. Alerts on any never-before-seen patterns (after baseline expires)

## Installation

Copy the `.platform` directory into your project root:

```
your-project/
├── .platform/
│   └── hooks/
│       ├── predeploy/
│       │   └── 00_logwhisperer_cleanup.sh
│       └── postdeploy/
│           └── 99_logwhisperer_setup.sh
└── ...
```

Set the minimum required env vars and deploy:

```bash
eb setenv LOG_WHISPERER_ENABLED=true APP_ROLE=web LOG_WHISPERER_NTFY_TOPIC=my-alerts
eb deploy
```

## Environment Variables

Set these in the EB console or via `eb setenv`:

### Required

| Variable | Description |
|:---------|:------------|
| `LOG_WHISPERER_ENABLED` | Set to `true` to activate. When `false`, the hook cleans up and exits. |

### Optional

| Variable | Default | Description |
|:---------|:--------|:------------|
| `APP_ROLE` | `unknown` | Identifies the environment role (e.g. `web`, `worker`). Each role gets its own pattern DB so different services don't cross-contaminate. |
| `LOG_WHISPERER_CRON_INTERVAL` | `15` | Minutes between analysis runs. |
| `LOG_WHISPERER_MIN_SEVERITY` | `WARN` | Minimum severity to report: `INFO`, `WARN`, or `ERROR`. |
| `LOG_WHISPERER_BASELINE_MINUTES` | `30` | Baseline learning window after each deploy. No alerts fire during this period. |

### Notifications

Configure at least one channel to receive alerts:

**ntfy** (simplest, no account needed):

| Variable | Description |
|:---------|:------------|
| `LOG_WHISPERER_NTFY_TOPIC` | ntfy topic name |
| `LOG_WHISPERER_NTFY_URL` | ntfy server URL (default: `https://ntfy.sh`) |

**Telegram:**

| Variable | Description |
|:---------|:------------|
| `LOG_WHISPERER_TELEGRAM_TOKEN` | Bot token from @BotFather |
| `LOG_WHISPERER_TELEGRAM_CHAT` | Chat ID to send alerts to |

**Email (SMTP):**

| Variable | Description |
|:---------|:------------|
| `LOG_WHISPERER_EMAIL_TO` | Recipient address |
| `LOG_WHISPERER_EMAIL_FROM` | Sender address |
| `LOG_WHISPERER_SMTP_HOST` | SMTP server |
| `LOG_WHISPERER_SMTP_PORT` | SMTP port (default: `587`) |
| `LOG_WHISPERER_SMTP_USER` | SMTP username |
| `LOG_WHISPERER_SMTP_PASSWORD` | SMTP password |

## Role Isolation

If you run multiple EB environments (e.g. a web server and a background worker), set `APP_ROLE` differently for each:

```bash
# Web environment
eb setenv APP_ROLE=web -e my-app-web

# Worker environment
eb setenv APP_ROLE=worker -e my-app-worker
```

Each role stores its pattern DB under `/opt/logwhisperer/state/<role>/`, so a pattern that's normal for the worker (e.g. `Celery task completed`) won't be flagged as new on the web tier.

## Baseline Learning

Every deployment triggers a baseline learning window (default: 30 minutes). During this period:

- Log patterns are recorded in the database
- No alert notifications are sent

This prevents a flood of false alerts from log changes introduced by the new deployment (new startup messages, changed log formats, etc.). Once the window expires, only genuinely new patterns trigger alerts.

Adjust the window length:

```bash
eb setenv LOG_WHISPERER_BASELINE_MINUTES=60
```

## Container Discovery

The wrapper script finds your app container using these strategies (in order):

1. Container named `/app`
2. Container publishing port 80
3. Container with image `aws_beanstalk/current-app:latest`

This covers the default EB Docker naming conventions. If your setup differs, edit the `CID=` lines in the embedded `run.sh` wrapper inside `99_logwhisperer_setup.sh`.

## Verifying

After deployment, SSH into the instance:

```bash
eb ssh
```

Check that the cron job is installed:

```bash
crontab -l
# */15 * * * * /opt/logwhisperer/run.sh
```

Run the wrapper manually to test:

```bash
sudo /opt/logwhisperer/run.sh
```

Check system logs for output:

```bash
journalctl -t "log-whisperer[web]" --since "1 hour ago"
```

View the pattern database:

```bash
jq . /opt/logwhisperer/state/web/patterns.db
```

## Disabling

Set the env var to `false` and redeploy:

```bash
eb setenv LOG_WHISPERER_ENABLED=false
```

The postdeploy hook will clean up the cron job automatically.
