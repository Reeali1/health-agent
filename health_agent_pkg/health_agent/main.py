#!/usr/bin/env python3

import argparse
import logging
import os
import shutil
import subprocess
import requests
from dotenv import load_dotenv

# -----------------------------
# Alert state files
# -----------------------------
DISK_ALERT_FILE = "/tmp/disk_alert_sent"
SERVICE_ALERT_FILE = "/tmp/service_alert_sent"

# -----------------------------
# Helpers
# -----------------------------
def send_slack_alert(message: str, webhook: str | None):
    if not webhook:
        return
    try:
        requests.post(webhook, json={"text": message}, timeout=5)
    except Exception:
        logging.error("Failed to send Slack alert")

def alert_exists(path: str) -> bool:
    return os.path.exists(path)

def mark_alert(path: str):
    open(path, "w").close()

def clear_alert(path: str):
    if os.path.exists(path):
        os.remove(path)

# -----------------------------
# Disk check
# -----------------------------
def check_disk(args, webhook: str | None) -> bool:
    total, used, free = shutil.disk_usage(args.disk_path)
    free_gb = free / (1024 ** 3)

    logging.info(
        f"Disk check: {free_gb:.2f} GB free on {args.disk_path}"
    )

    if free_gb < args.disk_threshold:
        logging.error("Disk space LOW")

        if not alert_exists(DISK_ALERT_FILE):
            send_slack_alert(
                f"🚨 Low disk space on {args.disk_path}: "
                f"{free_gb:.2f} GB remaining",
                webhook,
            )
            mark_alert(DISK_ALERT_FILE)

        return False

    clear_alert(DISK_ALERT_FILE)
    return True

# -----------------------------
# Service check
# -----------------------------
def check_service(args, webhook: str | None) -> bool:
    if not args.service:
        return True

    result = subprocess.run(
        ["pgrep", "-f", args.service],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode == 0:
        logging.info(f"Service '{args.service}' is running")
        clear_alert(SERVICE_ALERT_FILE)
        return True

    logging.error(f"Service '{args.service}' is DOWN")

    if not alert_exists(SERVICE_ALERT_FILE):
        send_slack_alert(
            f"🚨 Service '{args.service}' is DOWN",
            webhook,
        )
        mark_alert(SERVICE_ALERT_FILE)

    if args.restart_cmd:
        logging.info(f"Attempting restart: {args.restart_cmd}")
        restart = subprocess.run(args.restart_cmd, shell=True)

        if restart.returncode == 0:
            recheck = subprocess.run(
                ["pgrep", "-f", args.service],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if recheck.returncode == 0:
                logging.info(
                    f"Service '{args.service}' restarted successfully"
                )
                clear_alert(SERVICE_ALERT_FILE)
                return True

        send_slack_alert(
            f"❌ Restart failed for service '{args.service}'",
            webhook,
        )

    return False

# -----------------------------
# Main entry point
# -----------------------------
def main() -> int:
    load_dotenv()
    webhook = os.getenv("SLACK_WEBHOOK_URL")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="System health agent")

    parser.add_argument(
        "--disk-path",
        default="/",
        help="Disk path to check",
    )

    parser.add_argument(
        "--disk-threshold",
        type=int,
        default=10,
        help="Minimum free disk space in GB",
    )

    parser.add_argument(
        "--service",
        help="Process name to monitor",
    )

    parser.add_argument(
        "--restart-cmd",
        help="Command to restart service",
    )

    args = parser.parse_args()

    try:
        disk_ok = check_disk(args, webhook)
        service_ok = check_service(args, webhook)

        if disk_ok and service_ok:
            logging.info("System health: OK")
            return 0

        logging.error("System health: PROBLEM DETECTED")
        return 1

    except Exception as exc:
        logging.exception("Health agent crashed")
        send_slack_alert(
            f"🔥 Health agent crashed: {exc}",
            webhook,
        )
        return 2

# -----------------------------
# Script execution
# -----------------------------
if __name__ == "__main__":
    import sys
    sys.exit(main())

