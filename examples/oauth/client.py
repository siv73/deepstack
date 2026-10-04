import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AUTHZ_ENDPOINT = "https://login.example.com/authorize"
TOKEN_ENDPOINT = "https://login.example.com/token"
CLIENT_ID = "photo-app"
REDIRECT_URI = "https://photos.example.com/callback"


def make_pkce():
    verifier = secrets.token_urlsafe(64)  # 86 URL-safe chars
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def start_login(session):
    state = secrets.token_urlsafe(32)
    verifier, challenge = make_pkce()
    session["state"], session["verifier"] = state, verifier  # kept server-side
    return (
        AUTHZ_ENDPOINT
        + "?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": "photos.read",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )


def on_callback(session, params):
    if not secrets.compare_digest(params["state"], session.pop("state")):
        raise PermissionError("state mismatch: possible CSRF")
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": params["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": session.pop("verifier"),
        }
    ).encode()
    req = Request(TOKEN_ENDPOINT, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req) as resp:
        return json.load(resp)
