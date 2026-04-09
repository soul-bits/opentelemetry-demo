#!/usr/bin/env python3
"""
Alertmanager Webhook Receiver - writes alerts to a text file
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Path for alert log file
ALERTS_FILE = Path("/tmp/alerts.log")

def write_alert(alert_data):
    """Write alert to file"""
    try:
        timestamp = datetime.now().isoformat()
        with open(ALERTS_FILE, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{timestamp}]\n")
            f.write(json.dumps(alert_data, indent=2))
            f.write(f"\n{'='*80}\n")
        print(f"Alert written to {ALERTS_FILE}")
    except Exception as e:
        print(f"Error writing alert: {e}", file=sys.stderr)

def main():
    """Read alert from stdin (from curl/webhook)"""
    try:
        data = json.loads(sys.stdin.read())
        
        # Handle Alertmanager webhook payload format
        if 'alerts' in data:
            for alert in data['alerts']:
                write_alert(alert)
        else:
            write_alert(data)
            
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
