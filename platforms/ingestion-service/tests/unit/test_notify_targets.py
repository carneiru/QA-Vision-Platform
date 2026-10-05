import pytest

from src.ingestion.utils import notify_targets as nt

SLACK = "https://hooks.slack.com/services/T000/B000/XXXXXXXXXXXXXXXXXXXXabcd"
TEAMS = "https://prod-12.westeurope.logic.azure.com:443/workflows/abc/triggers/manual/paths/invoke?sig=s3cr3t"
TEAMS_NEW = (
    "https://default0123.ab.environment.api.powerplatform.com:443/powerautomate/automations/direct"
    "/workflows/abc/triggers/manual/paths/invoke?sig=s3cr3t"
)


@pytest.mark.parametrize("kind, url", [("slack", SLACK), ("teams", TEAMS), ("teams", TEAMS_NEW),
                                       ("webhook", "https://alerts.example.com/qa?token=abc")])
def test_allowed_targets(kind, url):
    assert nt.validate_target(kind, url) == url


@pytest.mark.parametrize("kind, url, reason", [
    ("slack", "https://evil.com/services/x", "hooks.slack.com"),
    ("slack", "http://hooks.slack.com/services/x", "https"),
    ("teams", "https://outlook.office.com/webhook/x", "Workflows"),     # retired O365 connectors
    ("teams", "https://logic.azure.com.evil.com/x", "Workflows"),
    ("webhook", "http://alerts.example.com/x", "https"),
    ("webhook", "https://alerts.example.com:8443/x", "port"),
    ("webhook", "https://user:pw@alerts.example.com/x", "credentials"),
    ("webhook", "https://localhost/x", "public"),
    ("webhook", "https://127.0.0.1/x", "public"),
    ("webhook", "https://10.1.2.3/x", "public"),
    ("webhook", "https://169.254.169.254/latest/meta-data", "public"),
    ("webhook", "https://[::1]/x", "public"),
    ("sms", "https://example.com", "kind"),
    ("webhook", "not a url", "https"),
])
def test_refused_targets_say_why(kind, url, reason):
    with pytest.raises(ValueError, match=reason):
        nt.validate_target(kind, url)


@pytest.mark.parametrize("address, public", [
    ("8.8.8.8", True), ("140.82.112.3", True), ("2606:4700::1111", True),
    ("127.0.0.1", False), ("10.0.0.5", False), ("172.30.0.10", False), ("192.168.1.1", False),
    ("169.254.169.254", False), ("100.64.0.1", False), ("0.0.0.0", False), ("224.0.0.1", False),
    ("::1", False), ("fd00::1", False), ("fe80::1", False), ("::ffff:127.0.0.1", False),
])
def test_public_addresses(address, public):
    assert nt.is_public_address(address) is public


def test_a_host_resolving_to_any_private_address_is_refused(monkeypatch):
    monkeypatch.setattr(nt, "resolve", lambda host: ["93.184.216.34", "10.0.0.7"])
    with pytest.raises(ValueError, match="public"):
        nt.check_resolves_publicly("https://alerts.example.com/x")


def test_masked_target_shows_host_and_last_four_only():
    assert nt.mask_target(SLACK) == "hooks.slack.com/…abcd"
    assert "s3cr3t" not in nt.mask_target(TEAMS)
