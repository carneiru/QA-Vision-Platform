"""Turn whatever a user pasted into a canonical repository identity. No network access."""
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, unquote, urlsplit

HOSTS = {"github.com": "github", "gitlab.com": "gitlab"}
MAX_GITLAB_SEGMENTS = 20

_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
_SSH = re.compile(r"^git@([^:/]+):(.+)$")

UNSUPPORTED_HOST = "Only github.com, gitlab.com and dev.azure.com repositories are supported"

# Azure DevOps: organization / project / repository. Project and repository names may hold spaces.
_AZURE_SEGMENT = re.compile(r"^[A-Za-z0-9._\-]+(?: [A-Za-z0-9._\-]+)*$")
_AZURE_SSH = re.compile(r"^[A-Za-z0-9._\-]+@(?:ssh\.dev\.azure\.com|vs-ssh\.visualstudio\.com):v3/(.+)$")
_VISUALSTUDIO = re.compile(r"^([a-z0-9][a-z0-9\-]{0,62})\.visualstudio\.com$")


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

    azure = _parse_azure(raw)
    if azure is not None:
        return azure

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
    if len(owner) > 255 or len(name) > 255:
        raise ValueError("The repository path is too long")
    return ParsedRepo(
        provider=provider,
        owner=owner,
        name=name,
        full_name_key=f"{owner}/{name}".lower(),
        url=f"https://{host}/{owner}/{name}",
    )


def _parse_azure(raw: str) -> Optional[ParsedRepo]:
    """An Azure DevOps repository, or None when the input is not an Azure DevOps address at all
    (then the GitHub/GitLab rules apply). Raises ValueError for an Azure address that is wrong."""
    ssh = _AZURE_SSH.match(raw)
    if ssh:
        segments = ssh.group(1).split("/")
        if len(segments) != 3:
            raise ValueError("An Azure DevOps SSH URL needs v3/organization/project/repository")
        return _azure(*segments)

    parts = urlsplit(raw)
    try:
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    legacy = _VISUALSTUDIO.match(host)
    if host != "dev.azure.com" and legacy is None:
        return None
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError("The repository URL must start with https://, http:// or git@")
    try:
        port = parts.port
    except ValueError:
        raise ValueError(UNSUPPORTED_HOST)
    if port is not None:
        raise ValueError("The repository URL must not specify a port")

    segments = [s for s in parts.path.split("/") if s]
    if legacy:
        organization = legacy.group(1)
        if segments and segments[0].lower() == "defaultcollection":
            segments = segments[1:]
        segments = [organization] + segments
    if parts.password is not None:
        raise ValueError("The repository URL must not contain credentials")
    # Clone URLs carry the organization as the user name (https://acme@dev.azure.com/acme/...)
    if parts.username is not None and (not segments or parts.username.lower() != segments[0].lower()):
        raise ValueError("The repository URL must not contain credentials")
    if len(segments) < 4 or segments[2] != "_git":
        raise ValueError("An Azure DevOps repository URL looks like dev.azure.com/organization/project/_git/repository")
    return _azure(segments[0], segments[1], segments[3])


def _azure(organization: str, project: str, repository: str) -> ParsedRepo:
    names = []
    for position, raw in enumerate((organization, project, repository)):
        name = unquote(raw)
        if position == 2 and name.endswith(".git"):
            name = name[: -len(".git")]
        if "/" in name or set(name) <= {"."} or not _AZURE_SEGMENT.match(name):
            raise ValueError("The repository path contains characters that are not allowed")
        names.append(name)
    organization, project, repository = names
    owner = f"{organization}/{project}"
    if len(owner) > 255 or len(repository) > 255:
        raise ValueError("The repository path is too long")
    return ParsedRepo(
        provider="azure_devops",
        owner=owner,
        name=repository,
        full_name_key=f"{owner}/{repository}".lower(),
        url=f"https://dev.azure.com/{quote(organization, safe='')}/{quote(project, safe='')}/_git/{quote(repository, safe='')}",
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
