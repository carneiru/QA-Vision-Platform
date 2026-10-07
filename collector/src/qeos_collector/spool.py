"""Keep parts a failed upload could not deliver; the next invocation resends
them with their original Idempotency-Key, so the platform stores each part
exactly once however often it is retried. Spooling is best effort and never
raises: losing a retry opportunity must not break the build that is running."""
from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path
from typing import List, Tuple

from qeos_collector.payload import Part

# A platform outage lasting many runs must not fill the runner's disk
MAX_SPOOLED = 100


def spool_part(directory: Path, part: Part) -> "Path | None":
    """Returns the written path, or None when the part could not be spooled."""
    try:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        if len(list(directory.glob("*.json"))) >= MAX_SPOOLED:
            return None
        record = {
            "idempotency_key": part.idempotency_key,
            "count": part.count,
            "body": base64.b64encode(part.body).decode("ascii"),
        }
        path = directory / f"{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return path
    except OSError:
        return None


def spooled_parts(directory: Path) -> List[Tuple[Path, Part]]:
    """Oldest first; unreadable files are skipped, never deleted."""
    entries: List[Tuple[Path, Part]] = []
    try:
        paths = sorted(Path(directory).glob("*.json"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return []
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            part = Part(
                body=base64.b64decode(record["body"]),
                idempotency_key=str(record["idempotency_key"]),
                count=int(record["count"]),
            )
        except (OSError, ValueError, KeyError, TypeError):
            continue
        entries.append((path, part))
    return entries
