#!/usr/bin/env python3
"""
Alertmanager Webhook Receiver - HTTP server that receives alerts
Listens on port 5000 for Alertmanager webhooks
Stores alerts in memory for query via REST API
"""
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from collections import deque

app = Flask(__name__)

# In-memory storage of last 100 alerts
alerts_history = deque(maxlen=100)

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
            logger.warning("Received empty POST to /webhook")
            return {"error": "No JSON data"}, 400
        
        num_alerts = len(data.get('alerts', []))
        status = data.get('status', 'unknown')
        
        # Store in memory
        for alert in data.get('alerts', []):
            alerts_history.append({
                'timestamp': datetime.now().isoformat(),
                'alert': alert,
                'status': status
            })
        
        logger.info(f"✓ Received {status} status with {num_alerts} alert(s)")
        print(f"✓ [{datetime.now().isoformat()}] {status} - {num_alerts} alerts")
        
        return {"status": "ok", "alerts_received": num_alerts}, 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {"error": str(e)}, 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "alerts_in_memory": len(alerts_history)}, 200

@app.route('/alerts', methods=['GET'])
def get_alerts():
    """Get stored alerts"""
    return jsonify({
        "total_in_memory": len(alerts_history),
        "alerts": list(alerts_history)
    }), 200

@app.route('/alerts/last', methods=['GET'])
def get_last_alert():
    """Get the last received alert"""
    if not alerts_history:
        return {"message": "No alerts received yet"}, 200
    return jsonify(alerts_history[-1]), 200

@app.route('/alerts/clear', methods=['POST'])
def clear_alerts():
    """Clear in-memory alerts"""
    count = len(alerts_history)
    alerts_history.clear()
    return {"message": f"Cleared {count} alerts from memory"}, 200

@app.route('/', methods=['GET'])
def index():
    """Simple HTML dashboard"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Alertmanager Webhook Receiver</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .status { padding: 15px; border-radius: 5px; margin: 10px 0; font-weight: bold; }
            .status.healthy { background-color: #d4edda; color: #155724; }
            .status.firing { background-color: #f8d7da; color: #721c24; }
            .status.resolved { background-color: #d1ecf1; color: #0c5460; }
            code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
            .endpoint { margin: 10px 0; padding: 15px; background: #f9f9f9; border-left: 4px solid #007bff; border-radius: 4px; }
            .endpoint strong { color: #007bff; }
            .alert-box { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0; border: 1px solid #ddd; max-height: 400px; overflow-y: auto; }
            .alert-item { background: white; padding: 10px; margin: 5px 0; border-radius: 3px; border-left: 4px solid #ffc107; }
            h1 { color: #333; margin-bottom: 10px; }
            h2 { color: #666; margin-top: 30px; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
            pre { background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }
            .btn { display: inline-block; padding: 8px 15px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
            .btn:hover { background: #0056b3; }
        </style>
        <script>
            function refreshStatus() {
                fetch('/health')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('status').innerHTML = 
                            '<strong>🟢 Healthy</strong> - Alerts in memory: ' + data.alerts_in_memory;
                    })
                    .catch(e => {
                        document.getElementById('status').innerHTML = '<strong>🔴 Error:</strong> ' + e;
                    });
            }
            
            function loadAlerts() {
                fetch('/alerts')
                    .then(r => r.json())
                    .then(data => {
                        let html = '<p>Total alerts in memory: <strong>' + data.total_in_memory + '</strong></p>';
                        if (data.alerts.length > 0) {
                            html += '<div style="max-height: 500px; overflow-y: auto;">';
                            data.alerts.slice().reverse().forEach((item, idx) => {
                                const alert = item.alert || {};
                                const alertname = alert.labels?.alertname || 'Unknown';
                                const severity = alert.labels?.severity || 'N/A';
                                const status = item.status;
                                const summary = alert.annotations?.summary || 'N/A';
                                html += '<div class="alert-item">';
                                html += '<strong>' + alertname + '</strong> [' + severity.toUpperCase() + '] <em>' + status.toUpperCase() + '</em><br/>';
                                html += '<small>' + item.timestamp + '</small><br/>';
                                html += '<small>' + summary + '</small>';
                                html += '</div>';
                            });
                            html += '</div>';
                        } else {
                            html += '<p><em>No alerts received yet...</em></p>';
                        }
                        document.getElementById('alerts-list').innerHTML = html;
                    })
                    .catch(e => console.error(e));
            }
            
            function clearAlerts() {
                if (confirm('Clear all alerts from memory?')) {
                    fetch('/alerts/clear', { method: 'POST' })
                        .then(r => r.json())
                        .then(data => alert(data.message))
                        .then(() => loadAlerts())
                        .catch(e => console.error(e));
                }
            }
            
            setInterval(refreshStatus, 2000);
            setInterval(loadAlerts, 2000);
            
            window.onload = function() {
                refreshStatus();
                loadAlerts();
            };
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🚨 Alertmanager Webhook Receiver</h1>
            
            <div class="status healthy" id="status">
                Loading status...
            </div>
            
            <h2>📊 Alerts (Last 100)</h2>
            <button class="btn" onclick="clearAlerts()">Clear Alerts</button>
            <div class="alert-box" id="alerts-list">
                Loading...
            </div>
            
            <h2>🔗 API Endpoints</h2>
            <div class="endpoint">
                <strong>POST</strong> <code>/webhook</code><br/>
                Alertmanager webhook receiver endpoint
            </div>
            <div class="endpoint">
                <strong>GET</strong> <code>/health</code><br/>
                Health check - returns alerts in memory count
            </div>
            <div class="endpoint">
                <strong>GET</strong> <code>/alerts</code><br/>
                Get all alerts stored in memory
            </div>
            <div class="endpoint">
                <strong>GET</strong> <code>/alerts/last</code><br/>
                Get the last received alert
            </div>
            <div class="endpoint">
                <strong>POST</strong> <code>/alerts/clear</code><br/>
                Clear all in-memory alerts
            </div>
            
            <h2>💡 Examples</h2>
            <p><strong>Check webhook status:</strong></p>
            <code>curl http://localhost:5001/health</code>
            <p><strong>View all alerts:</strong></p>
            <code>curl http://localhost:5001/alerts</code>
            <p><strong>View last alert:</strong></p>
            <code>curl http://localhost:5001/alerts/last</code>
        </div>
    </body>
    </html>
    """
    return html

if __name__ == '__main__':
    logger.info("Starting Alertmanager webhook receiver on port 5000")
    logger.info("Alerts will be stored in memory (last 100)")
    app.run(host='0.0.0.0', port=5000, debug=False)
