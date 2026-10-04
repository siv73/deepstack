"""Tests for api.py: every rejection the page lists, executed."""

import time

import api
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
NOW = int(time.time())
BASE = {
    "iss": api.ISSUER,
    "aud": api.AUDIENCE,
    "sub": "u1",
    "client_id": "photo-app",
    "iat": NOW,
    "exp": NOW + 600,
    "jti": "j1",
    "scope": "photos.read",
}


def make(claims=None, typ="at+jwt", key=KEY):
    return jwt.encode({**BASE, **(claims or {})}, key, algorithm="RS256", headers={"typ": typ})


def check(token, scope="photos.read"):
    claims = api.verify_access_token(token, KEY.public_key())
    api.require_scope(claims, scope)
    return claims


def test_valid_token_is_accepted():
    assert check(make())["sub"] == "u1"


@pytest.mark.parametrize(
    ("token", "error"),
    [
        (make({"aud": "https://billing.example.com"}), jwt.InvalidAudienceError),
        (make({"iss": "https://evil.example.com"}), jwt.InvalidIssuerError),
        (make({"exp": NOW - 5, "iat": NOW - 700}), jwt.ExpiredSignatureError),
        (make(typ="JWT"), jwt.InvalidTokenError),  # e.g. an ID token
        (jwt.encode(BASE, None, algorithm="none", headers={"typ": "at+jwt"}), jwt.InvalidAlgorithmError),
        (make(key=OTHER_KEY), jwt.InvalidSignatureError),
    ],
    ids=["wrong-audience", "wrong-issuer", "expired", "id-token", "alg-none", "other-key"],
)
def test_bad_tokens_are_rejected(token, error):
    with pytest.raises(error):
        check(token)


def test_missing_scope_is_refused():
    with pytest.raises(PermissionError, match="insufficient_scope"):
        check(make(), scope="photos.delete")
