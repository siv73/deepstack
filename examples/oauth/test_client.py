"""Tests for client.py: the page's claims about the client flow, executed."""

import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import client
import pytest
import stub_as


@pytest.fixture
def token_endpoint(monkeypatch):
    server = stub_as.serve()
    monkeypatch.setattr(client, "TOKEN_ENDPOINT", f"http://127.0.0.1:{server.server_port}/token")
    yield
    server.shutdown()


def _login():
    session = {}
    query = {k: v[0] for k, v in parse_qs(urlparse(client.start_login(session)).query).items()}
    return session, query


def _issue_code(code, query):
    stub_as.CODES[code] = (query["code_challenge"], query["redirect_uri"], query["client_id"])


def test_authorization_request_uses_code_flow_with_s256():
    session, q = _login()
    assert q["response_type"] == "code"
    assert q["code_challenge_method"] == "S256"
    assert 43 <= len(session["verifier"]) <= 128
    assert re.fullmatch(r"[A-Za-z0-9\-._~]+", session["verifier"])
    assert len(q["code_challenge"]) == 43  # base64url of a 32-byte SHA-256, no padding


PAGE = Path(__file__).resolve().parents[2] / "content" / "oauth" / "body.html"
DEMO_VERIFIER = "printnest-demo-verifier-0123456789abcdefghi"
DEMO_CHALLENGE = "YMU4z7-lwFN16O0dmZC4Ib7dj3vxWKHvPgrThxB62w4"
GUESS_VERIFIER = "attacker-guess-0000000000000000000000000000"
GUESS_CHALLENGE = "rtCvDrjz9YjfXEuR11scJVP10HWyGica368JiOx_rPM"


def test_pkce_worked_example_on_the_page():
    """The solved example in the PKCE part uses these exact values."""
    assert len(DEMO_VERIFIER) == 43
    assert client.challenge_for(DEMO_VERIFIER) == DEMO_CHALLENGE
    assert client.challenge_for(GUESS_VERIFIER) == GUESS_CHALLENGE
    assert len(DEMO_CHALLENGE) == 43
    page = PAGE.read_text()
    for value in (DEMO_VERIFIER, DEMO_CHALLENGE, GUESS_VERIFIER, GUESS_CHALLENGE):
        assert value in page


def test_state_and_verifier_lengths():
    session, _ = _login()
    assert len(session["state"]) == 43  # token_urlsafe(32)
    assert len(session["verifier"]) == 86  # token_urlsafe(64)


def test_happy_path_returns_token(token_endpoint):
    session, q = _login()
    _issue_code("code-1", q)
    tokens = client.on_callback(session, {"code": "code-1", "state": q["state"]})
    assert tokens["access_token"] == "at-123"


def test_code_is_single_use(token_endpoint):
    session, q = _login()
    _issue_code("code-2", q)
    client.on_callback(session, {"code": "code-2", "state": q["state"]})
    replay = {"state": "s", "verifier": "x" * 43}
    with pytest.raises(HTTPError) as err:
        client.on_callback(replay, {"code": "code-2", "state": "s"})
    assert err.value.code == 400


def test_stolen_code_without_verifier_is_rejected(token_endpoint):
    _, q = _login()
    _issue_code("code-3", q)
    thief = {"state": "t", "verifier": "x" * 43}
    with pytest.raises(HTTPError) as err:
        client.on_callback(thief, {"code": "code-3", "state": "t"})
    assert b"invalid_grant" in err.value.read()


def test_forged_callback_is_rejected_before_any_network_call():
    session, _ = _login()
    with pytest.raises(PermissionError, match="state mismatch"):
        client.on_callback(session, {"code": "evil", "state": "attacker-chosen"})
