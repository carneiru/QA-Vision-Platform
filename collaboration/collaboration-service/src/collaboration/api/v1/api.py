from fastapi import APIRouter

# This used to wire in a cloned copy of auth-service's auth/users/sso endpoints -- the same
# hardcoded-identity SSO mock that existed in every clone service, deleted repo-wide once it
# was found. Nothing here ever depended on it: endpoints/activity.py, comments.py,
# dashboard.py, discussions.py, knowledge.py, mentions.py, notifications.py and reports.py
# are unauthenticated, in-memory stub routers with no persistence (every handler is
# `# TODO: Implement actual ...`), and none of them import it.
#
# They are also not wired in here. Doing that is a design decision -- what auth model these
# routes should use, whether they share auth-service's users at all -- not a mechanical
# consequence of removing the mock, so it is left for whoever builds this service for real.
api_router = APIRouter()

__all__ = ["api_router"]
