import os
import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Disable default server logs to keep console clean
        pass

    def do_GET(self):
        if self.path == '/':
            filepath = os.path.join('giao diện', 'Dashboard.html')
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Dashboard.html khong ton tai!")
                
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        script_to_run = None

        if self.path == '/run_setup':
            cmd = ['python', '-X', 'utf8', 'setup_db.py']
        elif self.path == '/run_clean':
            cmd = ['python', '-X', 'utf8', '-c', 'from src.data_cleaning import clean_data; clean_data()']
        elif self.path == '/run_import':
            cmd = ['python', '-X', 'utf8', '-c', 'from src.import_to_db import import_data; import_data()']

        if cmd:
            # Set system encoding implicitly via env var for python scripts running as subprocess
            env = os.environ.copy()
            env['PYTHONPATH'] = os.getcwd()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            try:
                # Add '-X', 'utf8' to ensure python runtime forces utf-8 output encoding for checkmarks
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    env=env,
                    encoding='utf-8',
                    errors='replace' # Avoid crashes if Windows yields weird characters
                )
                output = result.stdout + result.stderr
            except Exception as e:
                output = f"Command failed: {str(e)}"
                
            self.wfile.write(json.dumps({'output': output}).encode('utf-8'))
        else:
            self.wfile.write(json.dumps({'output': 'Unknown Command'}).encode('utf-8'))

if __name__ == '__main__':
    port = 8000
    server = HTTPServer(('localhost', port), DashboardHandler)
    print(f"==================================================")
    print(f" SERVER DASHBOARD ĐANG CHẠY TẠI: http://localhost:{port}")
    print(f" (Bấm Ctrl+C trên biểu tượng cửa sổ này để tắt server)")
    print(f"==================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã tắt Server.")
        server.server_close()
