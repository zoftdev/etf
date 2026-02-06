#!/usr/bin/env python3
"""
Simple HTTP server to serve ./result directory with directory listing enabled.
Serves on 0.0.0.0 (all interfaces) on port 8000 by default.
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Get the result directory (relative to script location)
SCRIPT_DIR = Path(__file__).parent
RESULT_DIR = SCRIPT_DIR / "result"

if not RESULT_DIR.exists():
    print(f"Error: {RESULT_DIR} does not exist!")
    sys.exit(1)

# Change to result directory so it's served as root
os.chdir(RESULT_DIR)

PORT = int(os.environ.get("PORT", 8000))
HOST = "0.0.0.0"

class DirectoryHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with directory listing enabled."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(RESULT_DIR), **kwargs)
    
    def end_headers(self):
        # Add CORS headers if needed
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

def main():
    with socketserver.TCPServer((HOST, PORT), DirectoryHandler) as httpd:
        print(f"Server running at http://{HOST}:{PORT}/")
        print(f"Serving directory: {RESULT_DIR.absolute()}")
        print("Press Ctrl+C to stop the server")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

if __name__ == "__main__":
    main()
