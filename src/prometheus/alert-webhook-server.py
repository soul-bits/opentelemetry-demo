#!/usr/bin/env python3
"""
Alertmanager Webhook Receiver - HTTP server that writes alerts to a file
Listens on port 5000 for Alertmanager webhooks
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, request

app = Flask(__name__)
ALERTS_FILE = Path("/tmp/alerts.log")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Alertmanager webhook endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return {"error": "No JSON data"}, 400
        
        # Write to file
        timestamp = datetime.now().isoformat()
        with open(ALERTS_FILE, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{timestamp}]\n")
            f.write(f"Status: {data.get('status', 'unknown')}\n")
            
            # Write each alert
            for alert in data.get('alerts', []):
                f.write(f"\nAlert: {alert.get('labels', {}).get('alertname', 'Unknown')}\n")
                f.write(f"  Service: {alert.get('labels', {}).get('service', 'N/A')}\n")
                f.write(f"  Severity: {alert.get('labels', {}).get('severity', 'N/A')}\n")
                f.write(f"  Summary: {alert.get('annotations', {}).get('summary', 'N/A')}\n")
                f.write(f"  Description: {alert.get('annotations', {}).get('description', 'N/A')}\n")
            
            f.write(f"{'='*80}\n")
        
        num_alerts = len(data.get('alerts', []))
        logger.info(f"Received {num_alerts} alert(s)")
        print(f"✓ Alert logged to {ALERTS_FILE}")
        
        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"error": str(e)}, 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return {"status": "healthy"}, 200

if __name__ == '__main__':
    logger.info("Starting Alertmanager webhook receiver on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
