#!/usr/bin/env python3
"""
serve_local.py — Servidor local para probar el dashboard sin CORS
Uso: python serve_local.py
Luego abre: http://localhost:8080
"""
import http.server
import socketserver
import webbrowser
import sys
import os
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

PORT = 8080
DASHBOARD_DIR = Path(__file__).parent / "dashboard"

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silenciar logs

os.chdir(DASHBOARD_DIR)
print(f"\n{'═'*50}")
print(f"  🚀 Cloud Delivery Intelligence")
print(f"  Local server corriendo en:")
print(f"  → http://localhost:{PORT}")
print(f"\n  Ctrl+C para detener")
print(f"{'═'*50}\n")

webbrowser.open(f"http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
