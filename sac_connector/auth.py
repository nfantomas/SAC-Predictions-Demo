import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib import error, parse, request

from config import Config


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class TokenInfo:
    access_token: str
    token_type: str
    expires_in: int
    obtained_at: datetime

    @property
    def expires_at(self) -> datetime:
        return self.obtained_at + timedelta(seconds=self.expires_in)


def _build_request(
    token_url: str,
    client_id: str,
    client_secret: str,
) -> request.Request:
    auth_pair = f"{client_id}:{client_secret}".encode("utf-8")
    auth_header = base64.b64encode(auth_pair).decode("ascii")

    form = parse.urlencode({"grant_type": "client_credentials"}).encode("ascii")
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    return request.Request(token_url, data=form, headers=headers, method="POST")


def _error_message(status: int, body: str) -> str:
    if status == 401:
        return "Unauthorized. Check SAC_CLIENT_ID/SAC_CLIENT_SECRET and SAC_TOKEN_URL."
    if status == 403:
        return "Forbidden. Ensure the client has Data Export Service access."
    if status == 404:
        return "Not found. Verify SAC_TOKEN_URL is correct for the tenant."
    if status == 429:
        return "Too many requests. Retry after backoff or reduce load."
    if status >= 500:
        return "SAC auth service error. Retry later."
    if body:
        return body.strip()
    return f"HTTP {status}"


def request_token(config: Config, timeout: int = 30) -> TokenInfo:
    req = _build_request(config.token_url, config.client_id, config.client_secret)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        message = _error_message(exc.code, body)
        raise AuthError(f"Auth failed ({exc.code}): {message}") from exc
    except error.URLError as exc:
        raise AuthError(f"Auth failed: {exc.reason}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AuthError("Auth failed: Invalid JSON in token response.") from exc

    token = data.get("access_token")
    token_type = data.get("token_type", "Bearer")
    expires_in = data.get("expires_in")
    if not token or not expires_in:
        raise AuthError("Auth failed: Token response missing required fields.")

    return TokenInfo(
        access_token=token,
        token_type=token_type,
        expires_in=int(expires_in),
        obtained_at=datetime.now(timezone.utc),
    )
