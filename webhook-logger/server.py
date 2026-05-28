"""
Webhook Logger — reçoit les alertes d'Alertmanager et les affiche dans les logs.
Accès : docker logs webhook-logger
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import datetime


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for alert in data.get("alerts", []):
                status = alert.get("status", "unknown").upper()
                name = alert.get("labels", {}).get("alertname", "N/A")
                severity = alert.get("labels", {}).get("severity", "N/A")
                summary = alert.get("annotations", {}).get("summary", "")
                print(f"[{ts}] [{status}] [{severity}] {name} — {summary}", flush=True)
        except Exception as e:
            print(f"[ERROR] Impossible de parser le webhook : {e}", flush=True)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # Supprime les logs HTTP par défaut


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5001), WebhookHandler)
    print("Webhook logger en écoute sur :5001", flush=True)
    server.serve_forever()
