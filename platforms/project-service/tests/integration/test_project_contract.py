"""Contract with ingestion-service (docs/superpowers/specs/2026-09-29-ingestion-service-design.md):
GET /projects/{id} must return an integer organization_id and my_role in the five roles.
ingestion-service treats any other 200 body as "project service unavailable"."""
import pytest

ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


@pytest.mark.parametrize("role", ROLES)
def test_get_project_carries_organization_id_and_my_role(client, auth, org_role, make_project, role):
    project = make_project(org_id=42)
    org_role(role, org_id=42)
    body = client.get(f"/api/v1/projects/{project.id}", headers=auth()).json()
    assert isinstance(body["organization_id"], int) and not isinstance(body["organization_id"], bool)
    assert body["organization_id"] == 42
    assert body["my_role"] == role
