"""CODEOWNERS -> owners per file path, git semantics: the LAST matching
pattern wins, `*`/`?` stay inside one path segment, `**` crosses segments,
a leading `/` anchors to the repository root, a trailing `/` (or a pattern
with no glob and no extension-like tail) matches everything under that
directory. Read from the three places git hosts look: CODEOWNERS,
.github/CODEOWNERS, docs/CODEOWNERS — first one found wins."""
from __future__ import annotations

import os
import re
from typing import Callable, List, Optional, Tuple

LOCATIONS = ("CODEOWNERS", os.path.join(".github", "CODEOWNERS"), os.path.join("docs", "CODEOWNERS"))
MAX_OWNERS_TEXT = 255


def load_codeowners(root: str) -> Callable[[str], Optional[str]]:
    rules: List[Tuple[re.Pattern, str]] = []
    for location in LOCATIONS:
        path = os.path.join(root, location)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            pattern, owners = parts[0], " ".join(parts[1:])
            if owners:
                rules.append((_compile(pattern), owners[:MAX_OWNERS_TEXT]))
        break  # like git hosts: only the first CODEOWNERS found applies

    def owners_for(file_path: str) -> Optional[str]:
        path = file_path.replace("\\", "/").lstrip("/")
        for compiled, owners in reversed(rules):  # last matching line wins
            if compiled.match(path):
                return owners
        return None

    return owners_for


def _compile(pattern: str) -> re.Pattern:
    anchored = pattern.startswith("/")
    pattern = pattern.strip("/") if anchored else pattern.rstrip("/")

    pieces: List[str] = []
    for i, segment in enumerate(pattern.lstrip("/").split("/")):
        if segment == "**":
            pieces.append("(?:[^/]+/)*")
            continue
        translated = ""
        for ch in segment:
            if ch == "*":
                translated += "[^/]*"
            elif ch == "?":
                translated += "[^/]"
            else:
                translated += re.escape(ch)
        pieces.append(translated + "/")
    body = "".join(pieces)
    if body.endswith("/"):
        body = body[:-1]

    prefix = "" if anchored else "(?:[^/]+/)*"
    # A pattern can match the path itself, or a directory holding the path
    return re.compile(f"^{prefix}{body}(?:/.*)?$")
