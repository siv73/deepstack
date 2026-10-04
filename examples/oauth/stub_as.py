"""A minimal authorization-server stand-in for the tests.

It remembers the PKCE code_challenge for each issued code and checks the S256 verifier
at the token endpoint. Codes are single use.
"""

import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

CODES: dict[str, tuple[str, str, str]] = {}  # code -> (challenge, redirect_uri, client_id)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output quiet
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"])).decode()
        form = {k: v[0] for k, v in parse_qs(raw).items()}
        record = CODES.pop(form.get("code", ""), None)  # pop = single use
        ok = False
        if (
            record
            and form.get("grant_type") == "authorization_code"
            and form.get("redirect_uri") == record[1]
            and form.get("client_id") == record[2]
        ):
            digest = hashlib.sha256(form.get("code_verifier", "").encode("ascii")).digest()
            ok = base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == record[0]
        body = (
            {"access_token": "at-123", "token_type": "Bearer", "expires_in": 600}
            if ok
            else {"error": "invalid_grant"}
        )
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


def serve() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 0), _Handler)  # port 0: pick a free port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
