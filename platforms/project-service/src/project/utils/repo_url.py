"""Turn whatever a user pasted into a canonical repository identity. No network access."""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

HOSTS = {"github.com": "github", "gitlab.com": "gitlab"}
MAX_GITLAB_SEGMENTS = 20

_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
_SSH = re.compile(r"^git@([^:/]+):(.+)$")

UNSUPPORTED_HOST = "Only github.com and gitlab.com repositories are supported"


@dataclass(frozen=True)
class ParsedRepo:
    provider: str
    owner: str
    name: str
    full_name_key: str
    url: str


def parse_repo_url(raw: str) -> ParsedRepo:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("A repository URL is required")
    raw = raw.strip()

    ssh = _SSH.match(raw)
    if ssh:
        host, path = ssh.group(1), ssh.group(2)
    else:
        parts = urlsplit(raw)
        if parts.scheme.lower() not in ("http", "https"):
            raise ValueError("The repository URL must start with https://, http:// or git@")
        if parts.username is not None or parts.password is not None:
            raise ValueError("The repository URL must not contain credentials")
        try:
            port = parts.port
        except ValueError:
            raise ValueError(UNSUPPORTED_HOST)
        if port is not None:
            raise ValueError("The repository URL must not specify a port")
        host = parts.hostname or ""
        path = parts.path  # query and fragment (?tab=..., #readme) are dropped on purpose

    host = host.lower()
    if host.startswith("www."):
        host = host[len("www."):]
    provider = HOSTS.get(host)
    if provider is None:
        raise ValueError(UNSUPPORTED_HOST)

    segments = _repository_segments(provider, path)
    if segments[-1].endswith(".git"):
        segments[-1] = segments[-1][: -len(".git")]
    for segment in segments:
        if not segment or set(segment) == {"."} or not _SEGMENT.match(segment):
            raise ValueError("The repository path contains characters that are not allowed")

    owner, name = "/".join(segments[:-1]), segments[-1]
    return ParsedRepo(
        provider=provider,
        owner=owner,
        name=name,
        full_name_key=f"{owner}/{name}".lower(),
        url=f"https://{host}/{owner}/{name}",
    )


def _repository_segments(provider: str, path: str) -> list[str]:
    path = path.strip("/")
    if provider == "gitlab" and "/-/" in f"/{path}/":
        # GitLab puts every non-repository page under /-/ (tree, blob, merge_requests, ...)
        path = f"/{path}/".split("/-/")[0].strip("/")
    segments = path.split("/") if path else []

    if provider == "github":
        if len(segments) < 2:
            raise ValueError("A GitHub repository URL needs an owner and a repository name")
        return segments[:2]  # anything after owner/name is a page inside the repository
    if len(segments) < 2:
        raise ValueError("A GitLab repository URL needs a group and a project name")
    if len(segments) > MAX_GITLAB_SEGMENTS:
        raise ValueError("The GitLab repository path is too deep")
    return segments
