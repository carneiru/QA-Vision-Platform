"""The caller's role in an organization, from organization-service's members/me.

The response shape is a contract pinned in docs/superpowers/specs/2026-09-28-project-service-design.md:
200 -> exactly {"role": <one of ORG_ROLES>}. Anything else on a 200 is treated as the service being
unavailable, so a changed or broken response can never be read as a granted role.
"""
import httpx

from src.project.core.config import settings

ORG_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


class OrgServiceUnavailable(Exception):
    """organization-service could not give a trustworthy answer."""


class NotAMember(Exception):
    """The caller is not an active member, or the organization does not exist or is deleted."""


class InvalidCredentials(Exception):
    """organization-service rejected the caller's token."""


def get_my_role(org_id: int, token: str) -> str:
    url = f"{settings.ORGANIZATION_SERVICE_URL}/api/v1/organizations/{int(org_id)}/members/me"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=settings.ORGANIZATION_SERVICE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise OrgServiceUnavailable(f"could not reach organization-service: {exc}") from exc

    if response.status_code == 404:
        raise NotAMember()
    if response.status_code == 401:
        raise InvalidCredentials()
    if response.status_code != 200:
        raise OrgServiceUnavailable(f"unexpected organization-service status {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise OrgServiceUnavailable("organization-service returned a non-JSON body") from exc
    if not isinstance(body, dict) or set(body) != {"role"} or body["role"] not in ORG_ROLES:
        raise OrgServiceUnavailable("organization-service response does not match the members/me contract")
    return body["role"]
