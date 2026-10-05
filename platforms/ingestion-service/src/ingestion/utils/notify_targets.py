"""Where a notification may be sent. The server POSTs to URLs users type, so every target is
checked: vendor hosts for Slack and Teams, https on 443 for webhooks, and at send time every
address the host resolves to must be public (not loopback, private, link-local, CGNAT,
multicast or reserved: no Docker network, no cloud metadata endpoint)."""
import ipaddress
import re
import socket
from typing import List
from urllib.parse import urlsplit

KINDS = ("slack", "teams", "webhook", "email")
MAX_RECIPIENTS = 5
_EMAIL = re.compile(r"^[^@\s,<>\"]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}$")

# Teams "Workflows" (Power Automate) webhooks; the retired Office 365 connectors are not accepted
_TEAMS_HOSTS = (re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+\.logic\.azure\.com$"),
                re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.environment\.api\.powerplatform\.com$"))
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def resolve(host: str) -> List[str]:
    """Every address the host resolves to. Tests replace this."""
    return sorted({info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip in _CGNAT:
        return False
    return ip.is_global and not ip.is_multicast


def validate_target(kind: str, url: str) -> str:
    """The URL unchanged when it may be used for this kind; ValueError with the reason otherwise."""
    if kind not in KINDS:
        raise ValueError(f"Unknown kind; use one of {', '.join(KINDS)}")
    if kind == "email":
        return _validate_recipients(url)
    parts = urlsplit(url.strip()) if isinstance(url, str) else None
    if parts is None or parts.scheme != "https" or not parts.hostname:
        raise ValueError("The URL must start with https://")
    if parts.username is not None or parts.password is not None:
        raise ValueError("The URL must not contain credentials")
    try:
        port = parts.port
    except ValueError:
        raise ValueError("The URL has an invalid port") from None
    if port not in (None, 443):
        raise ValueError("The URL must not use a port other than 443")
    host = parts.hostname.lower()

    if kind == "slack" and host != "hooks.slack.com":
        raise ValueError("A Slack URL is an incoming webhook on hooks.slack.com")
    if kind == "teams" and not any(p.match(host) for p in _TEAMS_HOSTS):
        raise ValueError(
            "A Teams URL is a Workflows webhook (Power Automate), on logic.azure.com or "
            "powerplatform.com; Office 365 connectors are retired"
        )
    if kind == "webhook":
        _literal_must_be_public(host)
    return url.strip()


def _literal_must_be_public(host: str) -> None:
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".internal"):
        raise ValueError("The URL must point to a public address")
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return  # a name: checked when sending, against what it resolves to then
    if not is_public_address(str(literal)):
        raise ValueError("The URL must point to a public address")


def check_resolves_publicly(url: str) -> None:
    """Right before sending: a name that resolves to a private address could reach this network."""
    host = urlsplit(url).hostname or ""
    _literal_must_be_public(host)
    try:
        addresses = resolve(host)
    except OSError as exc:
        raise ValueError(f"The host could not be resolved ({exc})") from None
    if not addresses or not all(is_public_address(a) for a in addresses):
        raise ValueError("The URL's host does not resolve to a public address only")


def recipients(target: str) -> list:
    return [address.strip() for address in target.split(",") if address.strip()]


def _validate_recipients(value: str) -> str:
    if not isinstance(value, str) or chr(13) in value or chr(10) in value:
        raise ValueError("Give one to five email addresses, separated by commas")
    addresses = recipients(value)
    if not 1 <= len(addresses) <= MAX_RECIPIENTS:
        raise ValueError(f"Give one to {MAX_RECIPIENTS} email addresses, separated by commas")
    for address in addresses:
        if not _EMAIL.match(address):
            raise ValueError(f"{address} is not an email address")
    return ", ".join(addresses)


def mask_target(url: str, kind: str = "") -> str:
    """Webhook URLs are bearer secrets: show the host and the last 4 characters, nothing else.
    Email addresses are not secrets and show as they are."""
    if kind == "email":
        return url
    parts = urlsplit(url)
    tail = url.rstrip("/")[-4:]
    return f"{parts.hostname}/…{tail}"
