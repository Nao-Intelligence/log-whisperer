"""CLI entry point for Log Whisperer.

Parses arguments, orchestrates the read -> cluster -> report pipeline,
and dispatches notifications when new patterns are detected.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .core import build_report, cluster, format_alert_message
from .notify.dispatch import dispatch_notifications
from .paths import default_state_dir
from .report import print_text_report, report_to_json
from .sources import read_lines
from .state import BaselineState, PatternDB, fmt_local_ts, parse_duration


def parse_args(argv=None) -> argparse.Namespace:
    """Build the argument parser and return parsed arguments."""
    parser = argparse.ArgumentParser(
        prog="log-whisperer",
        description="Cluster logs into patterns, detect new patterns, and optionally notify.",
    )

    src = parser.add_argument_group("Sources (choose one)")
    src.add_argument("--docker", help="docker logs --since <since> <container>")
    src.add_argument("--compose", help="docker compose logs --since <since> <service>")
    src.add_argument("--compose-all", action="store_true", help="docker compose logs --since <since> (all services)")
    src.add_argument("--service", help="journalctl -u <service> --since <since>")
    src.add_argument("--file", help="Read last N lines from a file")

    parser.add_argument("--since", default="1h", help='Time window: e.g. "10m", "1h", "today"')
    parser.add_argument("--lines", type=int, default=5000, help="Max lines to process")
    parser.add_argument("--show-new", action="store_true", help="Only show never-seen patterns")
    parser.add_argument("--min-severity", choices=["INFO", "WARN", "ERROR"], default="INFO", help="Filter by severity")
    parser.add_argument("--show-samples", action="store_true", help="Print one raw sample line per pattern")
    parser.add_argument("--json", action="store_true", help="Output report as JSON (still updates DB)")

    state_dir = default_state_dir()
    parser.add_argument("--state-db", default=str(state_dir / "patterns.db"), help="Pattern DB path")
    parser.add_argument("--baseline-state", default=str(state_dir / "baseline.json"), help="Baseline state path")
    parser.add_argument("--reset", action="store_true", help="Reset pattern DB and baseline state")

    parser.add_argument("--baseline-learn", type=str, default="", help='Start baseline learning like "24h", "30m"')

    notify = parser.add_argument_group("Notifications")
    notify.add_argument("--notify-ntfy-topic", default=os.getenv("LOGWHISPERER_NTFY_TOPIC", ""), help="ntfy topic")
    notify.add_argument("--notify-ntfy-server", default=os.getenv("LOGWHISPERER_NTFY_SERVER", "https://ntfy.sh"), help="ntfy server")
    notify.add_argument("--notify-telegram-token", default=os.getenv("LOGWHISPERER_TELEGRAM_TOKEN", ""), help="Telegram bot token")
    notify.add_argument("--notify-telegram-chat-id", default=os.getenv("LOGWHISPERER_TELEGRAM_CHAT_ID", ""), help="Telegram chat id")
    notify.add_argument("--notify-email-host", default=os.getenv("LOGWHISPERER_SMTP_HOST", ""), help="SMTP host")
    notify.add_argument("--notify-email-port", type=int, default=int(os.getenv("LOGWHISPERER_SMTP_PORT", "587")), help="SMTP port")
    notify.add_argument("--notify-email-user", default=os.getenv("LOGWHISPERER_SMTP_USER", ""), help="SMTP username")
    notify.add_argument("--notify-email-pass", default=os.getenv("LOGWHISPERER_SMTP_PASS", ""), help="SMTP password")
    notify.add_argument("--notify-email-from", default=os.getenv("LOGWHISPERER_EMAIL_FROM", ""), help="Email From")
    notify.add_argument("--notify-email-to", default=os.getenv("LOGWHISPERER_EMAIL_TO", ""), help="Email To")
    notify.add_argument("--notify-email-no-tls", action="store_true", help="Disable STARTTLS for SMTP")

    args = parser.parse_args(argv)

    chosen = sum(bool(x) for x in [args.docker, args.compose, args.compose_all, args.service, args.file])
    if chosen != 1 and not args.reset:
        parser.error("Choose exactly one source: --docker, --compose, --compose-all, --service, or --file")

    return args


def main(argv=None) -> None:
    """Entry point: read logs, cluster patterns, report results, notify."""
    args = parse_args(argv)

    db_path = Path(args.state_db)
    baseline_path = Path(args.baseline_state)

    if args.reset:
        PatternDB(db_path).reset()
        BaselineState.reset(baseline_path)
        print(f"Reset: removed {db_path} and {baseline_path}")
        return

    if args.baseline_learn:
        try:
            seconds = parse_duration(args.baseline_learn)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
        until = BaselineState.enable_learning(baseline_path, seconds)
        print(f"Baseline learning enabled until {fmt_local_ts(until)}. (No alerts during this period)")

    try:
        lines, src_desc = read_lines(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    window = cluster(lines)
    report, alerted_items, baseline_active = build_report(
        src_desc=src_desc,
        since=args.since,
        lines_limit=args.lines,
        db_path=db_path,
        baseline_path=baseline_path,
        window=window,
        show_new_only=args.show_new,
        min_severity=args.min_severity,
    )

    if args.json:
        print(report_to_json(report))
    else:
        print_text_report(report, show_samples=args.show_samples)

    if baseline_active or not alerted_items:
        return

    alert_msg = format_alert_message(report, alerted_items)
    failures = dispatch_notifications(args, alert_msg)
    if failures:
        print("Notification failures:", file=sys.stderr)
        for f in failures:
            print(f" - {f}", file=sys.stderr)


if __name__ == "__main__":
    main()
