import jwt  # PyJWT

ISSUER = "https://login.example.com"
AUDIENCE = "https://photos.example.com"


def verify_access_token(token, public_key):
    header = jwt.get_unverified_header(token)
    if header.get("typ") not in ("at+jwt", "application/at+jwt"):
        raise jwt.InvalidTokenError("not an access token")  # e.g. an ID token
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],  # fixed list, never read from the token
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"require": ["iss", "aud", "exp", "sub", "client_id", "iat", "jti"]},
    )


def require_scope(claims, needed):
    if needed not in claims.get("scope", "").split():
        raise PermissionError("insufficient_scope")  # answer with 403
