import socket
import threading

import pytest

from qav_collector import __version__, upload
from qav_collector.payload import Part
from qav_collector.upload import ConfigError, UploadError, endpoint_for, make_context, upload_part

KEY = "qav_test_key_123"
PART = Part(body=b'{"run":{},"results":[]}', idempotency_key="gh-1-1-test", count=0)
RECEIPT = {"id": 42, "project_id": 1, "total": 2, "passed": 1, "failed": 1, "skipped": 0, "errored": 0,
           "created_at": "2026-09-29T12:00:00Z"}


class FakeTime:
    """sleep() only records; clock() advances by `step` on every call, plus whatever was slept."""

    def __init__(self, step=0.0):
        self.now = 0.0
        self.step = step
        self.sleeps = []

    def clock(self):
        value = self.now
        self.now += self.step
        return value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def send(endpoint, fake=None, context=None):
    fake = fake or FakeTime()
    return upload_part(endpoint, KEY, PART, context, sleep=fake.sleep, clock=fake.clock, rand=lambda: 0.0)


def collect(platform):
    return platform.url + "/api/v1/collect/runs"


def closed_port_endpoint():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/api/v1/collect/runs"


def test_a_stored_run_is_returned_with_its_status(platform):
    platform.reply(201, RECEIPT)

    assert send(collect(platform)) == (201, RECEIPT)
    request = platform.requests[0]
    assert request["path"] == "/api/v1/collect/runs"
    assert request["body"] == PART.body
    assert request["headers"]["Authorization"] == f"Bearer {KEY}"
    assert request["headers"]["Idempotency-Key"] == "gh-1-1-test"
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["headers"]["User-Agent"] == f"qav-collector/{__version__}"


def test_a_replay_counts_as_success(platform):
    platform.reply(200, RECEIPT)
    assert send(collect(platform)) == (200, RECEIPT)


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_are_retried_with_backoff(platform, status):
    platform.reply(status)
    platform.reply(status)
    platform.reply(201, RECEIPT)
    fake = FakeTime()

    assert send(collect(platform), fake) == (201, RECEIPT)
    assert fake.sleeps == [1, 2]
    assert {r["headers"]["Idempotency-Key"] for r in platform.requests} == {"gh-1-1-test"}


def test_backoff_has_up_to_25_percent_jitter(platform):
    platform.reply(503)
    platform.reply(201, RECEIPT)
    fake = FakeTime()

    upload_part(collect(platform), KEY, PART, sleep=fake.sleep, clock=fake.clock, rand=lambda: 1.0)
    assert fake.sleeps == [1.25]


def test_an_unreachable_platform_is_retried_until_the_attempt_budget():
    fake = FakeTime()

    with pytest.raises(UploadError, match=r"cannot reach the platform .*gave up after 5 attempts"):
        send(closed_port_endpoint(), fake)
    assert fake.sleeps == [1, 2, 4, 8]


def test_429_waits_for_retry_after_capped_at_10_seconds(platform):
    platform.reply(429, headers={"Retry-After": "3"})
    platform.reply(429, headers={"Retry-After": "60"})
    platform.reply(429)
    platform.reply(201, RECEIPT)
    fake = FakeTime()

    assert send(collect(platform), fake) == (201, RECEIPT)
    assert fake.sleeps == [3, 10, 1]


def test_no_new_attempt_starts_after_120_seconds(platform):
    for _ in range(5):
        platform.reply(503)
    fake = FakeTime(step=40)  # every clock() call is 40 s later

    with pytest.raises(UploadError, match="gave up after 120 s"):
        send(collect(platform), fake)
    assert len(platform.requests) == 3


def test_a_timed_out_post_is_retried_with_the_same_key(platform, monkeypatch):
    monkeypatch.setattr(upload, "TIMEOUT_SECONDS", 0.3)
    platform.reply(201, RECEIPT, delay=1.0)  # stored, but the answer comes too late
    platform.reply(200, RECEIPT)             # the retry is answered as a replay
    fake = FakeTime()

    assert send(collect(platform), fake) == (200, RECEIPT)
    assert fake.sleeps == [1]
    assert [r["headers"]["Idempotency-Key"] for r in platform.requests] == ["gh-1-1-test", "gh-1-1-test"]


@pytest.mark.parametrize("status, body, message", [
    (401, {"detail": "Invalid API key"}, "the API key is invalid or revoked (401)"),
    (409, {"detail": "Idempotency-Key reused"}, "this Idempotency-Key was already used for different results (409)"),
    (413, {"detail": "Request Entity Too Large"}, "the platform rejected the upload (413): Request Entity Too Large"),
    (422, {"detail": [{"loc": ["body", "run"], "msg": "Field required"}]},
     'the platform rejected the upload (422): [{"loc": ["body", "run"]'),
    (400, b"not json", "the platform rejected the upload (400): not json"),
])
def test_client_errors_are_not_retried(platform, status, body, message):
    platform.reply(status, body)
    fake = FakeTime()

    with pytest.raises(UploadError) as info:
        send(collect(platform), fake)
    assert message in str(info.value)
    assert fake.sleeps == [] and len(platform.requests) == 1


def test_the_servers_detail_is_cut_to_500_characters(platform):
    platform.reply(422, {"detail": "x" * 2000})

    with pytest.raises(UploadError) as info:
        send(collect(platform))
    assert str(info.value).endswith("x" * 500)
    assert "x" * 501 not in str(info.value)


@pytest.mark.parametrize("status", [301, 307, 308])
def test_redirects_are_not_followed(platform, status):
    # Following would re-send the Authorization header to wherever Location points
    platform.reply(status, headers={"Location": platform.url + "/elsewhere"})

    with pytest.raises(UploadError, match=f"redirected to {platform.url}/elsewhere \\({status}\\)"):
        send(collect(platform))
    assert [r["path"] for r in platform.requests] == ["/api/v1/collect/runs"]


@pytest.fixture
def not_tls():
    """A port that answers a TLS ClientHello with plain HTTP, which fails the handshake at once.

    The ClientHello is read before answering: closing a socket with unread data sends a reset,
    which the client would see as a (retryable) dropped connection instead of a TLS error.
    """
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)

    def serve():
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            with conn:
                conn.recv(65536)
                conn.sendall(b"HTTP/1.0 400 Bad Request\r\n\r\n")

    threading.Thread(target=serve, daemon=True).start()
    yield f"https://127.0.0.1:{listener.getsockname()[1]}/api/v1/collect/runs"
    listener.close()


def test_tls_errors_are_not_retried(not_tls):
    fake = FakeTime()

    with pytest.raises(UploadError, match="TLS error .*--ca-file"):
        send(not_tls, fake, context=make_context(None))
    assert fake.sleeps == []


@pytest.mark.parametrize("url, endpoint", [
    ("https://qav.acme.test", "https://qav.acme.test/api/v1/collect/runs"),
    ("https://qav.acme.test/", "https://qav.acme.test/api/v1/collect/runs"),
    (" https://qav.acme.test:8443 ", "https://qav.acme.test:8443/api/v1/collect/runs"),
    ("http://localhost:8080", "http://localhost:8080/api/v1/collect/runs"),
    ("http://127.0.0.1:9", "http://127.0.0.1:9/api/v1/collect/runs"),
    ("http://[::1]:9", "http://[::1]:9/api/v1/collect/runs"),
])
def test_endpoint_for(url, endpoint):
    assert endpoint_for(url) == endpoint


@pytest.mark.parametrize("url", ["http://qav.acme.test", "ftp://qav.acme.test", "qav.acme.test", "", "https://", "http://[::1"])
def test_endpoint_for_refuses_what_cannot_work(url):
    with pytest.raises(ConfigError, match="https://"):
        endpoint_for(url)


def test_make_context_refuses_an_unusable_ca_file(tmp_path):
    not_a_cert = tmp_path / "not-a-cert.pem"
    not_a_cert.write_text("hello")

    for path in (str(not_a_cert), str(tmp_path / "missing.pem")):
        with pytest.raises(ConfigError, match="cannot use --ca-file"):
            make_context(path)
