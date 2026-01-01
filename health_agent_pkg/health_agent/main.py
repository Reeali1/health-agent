#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
import logging
import os
import requests
from dotenv import load_dotenv

# -----------------------------
# Environment & logging
# -----------------------------
load_dotenv()
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")

DISK_ALERT_FILE = "/tmp/disk_alert_sent"
SERVICE_ALERT_FILE = "/tmp/service_alert_sent"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# -----------------------------
# Arguments
# -----------------------------
parser = argparse.ArgumentParser(description="System health agent")

parser.add_argument(
    "--disk-path",
    default="/",
    help="Disk path to check (default: /)"
)

parser.add_argument(
    "--disk-threshold",
    type=int,
    default=10,
    help="Minimum free disk space in GB"
)

parser.add_argument(
    "--service",
    help="Process name to monitor (example: Dock, Docker, ssh)"
)

parser.add_argument(
    "--restart-cmd",
    help="Command to restart service if down (optional)"
)

args = parser.parse_args()

# -----------------------------
# Helper functions
# -----------------------------
def send_slack_alert(message):
    if not SLACK_WEBHOOK:
        return
    try:
        requests.post(SLACK_WEBHOOK, json={"text": message}, timeout=5)
    except Exception:
        logging.error("Failed to send Slack alert")

def alert_exists(path):
    return os.path.exists(path)

def mark_alert(path):
    open(path, "w").close()

def clear_alert(path):
    if os.path.exists(path):
        os.remove(path)

# -----------------------------
# Disk check
# -----------------------------
def check_disk():
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
                f"{free_gb:.2f} GB remaining"
            )
            mark_alert(DISK_ALERT_FILE)

        return False

    clear_alert(DISK_ALERT_FILE)
    return True

# -----------------------------
# Service check
# -----------------------------
def check_service():
    if not args.service:
        return True

    result = subprocess.run(
        ["pgrep", "-f", args.service],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if result.returncode == 0:
        logging.info(f"Service '{args.service}' is running")
        clear_alert(SERVICE_ALERT_FILE)
        return True

    logging.error(f"Service '{args.service}' is DOWN")

    if not alert_exists(SERVICE_ALERT_FILE):
        send_slack_alert(f"🚨 Service '{args.service}' is DOWN")
        mark_alert(SERVICE_ALERT_FILE)

    if args.restart_cmd:
        logging.info(f"Attempting restart: {args.restart_cmd}")
        restart = subprocess.run(args.restart_cmd, shell=True)

        if restart.returncode == 0:
            recheck = subprocess.run(
                ["pgrep", "-f", args.service],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            if recheck.returncode == 0:
                logging.info(
                    f"Service '{args.service}' restarted successfully"
                )
                clear_alert(SERVICE_ALERT_FILE)
                return True

        send_slack_alert(
            f"❌ Restart failed for service '{args.service}'"
        )

    return False

# -----------------------------
# Main execution
# -----------------------------
try:
    disk_ok = check_disk()
    service_ok = check_service()

    if disk_ok and service_ok:
        logging.info("System health: OK")
        sys.exit(0)

    logging.error("System health: PROBLEM DETECTED")
    sys.exit(1)

except Exception as e:
    logging.exception("Health agent crashed")
    send_slack_alert(f"🔥 Health agent crashed: {e}")
    sys.exit(2)

