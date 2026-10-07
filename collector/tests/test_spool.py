"""The spool keeps parts a failed upload could not deliver, so the next
invocation can retry them with their original Idempotency-Key."""

from qeos_collector.payload import Part
from qeos_collector import spool


def part(key="job-1", body=b'{"run":{}}'):
    return Part(body=body, idempotency_key=key, count=1)


def test_roundtrip(tmp_path):
    body = '{"name": "café"}'.encode("utf-8")
    saved = spool.spool_part(tmp_path, part(body=body))
    assert saved is not None

    loaded = spool.spooled_parts(tmp_path)
    assert len(loaded) == 1
    path, restored = loaded[0]
    assert restored.idempotency_key == "job-1"
    assert restored.body == body
    assert path.exists()


def test_spooling_stops_at_the_cap(tmp_path):
    for i in range(spool.MAX_SPOOLED):
        assert spool.spool_part(tmp_path, part(key=f"k{i}")) is not None
    assert spool.spool_part(tmp_path, part(key="one-too-many")) is None


def test_a_corrupt_file_is_skipped(tmp_path):
    spool.spool_part(tmp_path, part())
    (tmp_path / "junk.json").write_text("not json", encoding="utf-8")

    loaded = spool.spooled_parts(tmp_path)
    assert [p.idempotency_key for _, p in loaded] == ["job-1"]


def test_spooling_never_raises(tmp_path):
    file_not_dir = tmp_path / "file"
    file_not_dir.write_text("x", encoding="utf-8")
    assert spool.spool_part(file_not_dir, part()) is None
    assert spool.spooled_parts(file_not_dir) == []
