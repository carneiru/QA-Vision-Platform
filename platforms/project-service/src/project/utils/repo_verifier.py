"""Check a repository is publicly reachable. Unauthenticated, so a private repository and a
missing one look the same (404). Provider and network failures never raise."""
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import httpx

VERIFIED, NOT_FOUND, UNCHECKED = "verified", "not_found", "unchecked"


@dataclass(frozen=True)
class VerificationResult:
    status: str
    default_branch: Optional[str]


def _api_url(provider: str, owner: str, name: str) -> str:
    # The host is fixed here and never taken from user input; every path part is encoded.
    if provider == "github":
        return f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    if provider == "gitlab":
        return f"https://gitlab.com/api/v4/projects/{quote(f'{owner}/{name}', safe='')}"
    raise ValueError(f"unsupported provider: {provider}")


def verify(provider: str, owner: str, name: str, timeout: float) -> VerificationResult:
    url = _api_url(provider, owner, name)
    try:
        response = httpx.get(
            url, timeout=timeout, follow_redirects=False, headers={"Accept": "application/json"}
        )
    except httpx.HTTPError:
        return VerificationResult(UNCHECKED, None)

    if response.status_code == 404:
        return VerificationResult(NOT_FOUND, None)
    if response.status_code != 200:
        # 403/429 are rate limits; 3xx/5xx are not something to retry from a request handler
        return VerificationResult(UNCHECKED, None)
    try:
        body = response.json()
    except ValueError:
        return VerificationResult(UNCHECKED, None)
    if not isinstance(body, dict):
        return VerificationResult(UNCHECKED, None)
    branch = body.get("default_branch")
    return VerificationResult(VERIFIED, branch if isinstance(branch, str) and branch else None)
