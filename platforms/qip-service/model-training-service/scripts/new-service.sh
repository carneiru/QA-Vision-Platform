#!/usr/bin/env bash
set -euo pipefail

# Usage: ./new-service.sh <domain> <service-name> [service-title] [service-description]
# Example: ./new-service.sh platforms organization-service "Organization Service" "Manages organizations and tenants"

DOMAIN=${1:?Domain required (e.g., platforms, execution, intelligence)}
SERVICE_NAME=${2:?Service name required (e.g., organization-service)}
SERVICE_TITLE=${3:-$(echo "$SERVICE_NAME" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2); print}' | sed 's/ /-/g')}
SERVICE_DESCRIPTION=${4:-"$SERVICE_TITLE service"}

# Determine target path
TARGET_PATH="./$DOMAIN/$SERVICE_NAME"
if [[ -d "$TARGET_PATH" ]]; then
  echo "Error: $TARGET_PATH already exists."
  exit 1
fi

# Load skeleton from template (we will copy organization-service as base)
SKELETON_DIR="./templates/service-skeleton"
if [[ ! -d "$SKELETON_DIR" ]]; then
  # Fallback: copy from organization-service if template not yet created
  SKELETON_DIR="./platforms/organization-service"
fi

echo "Creating service $SERVICE_NAME under $DOMAIN from skeleton $SKELETON_DIR"
cp -r "$SKELETON_DIR" "$TARGET_PATH"

# Replace placeholders in all text files
find "$TARGET_PATH" -type f \( -name "*.py" -o -name "*.txt" -o -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.env" -o -name "*.md" -o -name "Dockerfile" -o -name "alembic.ini" -o -name "*.ini" -o -name "requirements.txt" -o -name "pytest.ini" \) -print0 | while IFS= read -r -d '' file; do
  sed -i "s/{{SERVICE_NAME}}/$SERVICE_NAME/g" "$file"
  sed -i "s/{{SERVICE_TITLE}}/$SERVICE_TITLE/g" "$file"
  sed -i "s/{{SERVICE_DESCRIPTION}}/$SERVICE_DESCRIPTION/g" "$file"
done

# Rename internal package directory from 'organization' to service base name (strip -service)
SERVICE_BASE=$(echo "$SERVICE_NAME" | sed 's/-service$//')
if [[ -d "$TARGET_PATH/src/organization" ]]; then
  mv "$TARGET_PATH/src/organization" "$TARGET_PATH/src/$SERVICE_BASE"
fi
# Update any import references from src.organization to src.$SERVICE_BASE
find "$TARGET_PATH" -type f -name "*.py" -print0 | while IFS= read -r -d '' file; do
  sed -i "s/src\.organization/src.$SERVICE_BASE/g" "$file"
done

# Update alembic env.py to import from new base
if [[ -f "$TARGET_PATH/alembic/env.py" ]]; then
  sed -i "s/from organization\.db\.base import Base/from $SERVICE_BASE\.db\.base import Base/g" "$TARGET_PATH/alembic/env.py"
fi

# Update .env and .env.example DB name if present
if [[ -f "$TARGET_PATH/.env" ]]; then
  sed -i "s/POSTGRES_DB=org_db/POSTGRES_DB=${SERVICE_BASE}_db/g" "$TARGET_PATH/.env"
  sed -i "s/DATABASE_URL=postgresql:\/\/postgres:postgres@localhost:5432\/org_db/DATABASE_URL=postgresql:\/\/postgres:postgres@localhost:5432\/${SERVICE_BASE}_db/g" "$TARGET_PATH/.env"
fi
if [[ -f "$TARGET_PATH/.env.example" ]]; then
  sed -i "s/POSTGRES_DB=org_db/POSTGRES_DB=${SERVICE_BASE}_db/g" "$TARGET_PATH/.env.example"
  sed -i "#DATABASE_URL=postgresql:\/\/postgres:postgres@localhost:5432\/org_db#DATABASE_URL=postgresql:\/\/postgres:postgres@localhost:5432\/${SERVICE_BASE}_db#g" "$TARGET_PATH/.env.example"
fi

# Update README.md
if [[ -f "$TARGET_PATH/README.md" ]]; then
  sed -i "s/# Organization Service/# $SERVICE_TITLE/g" "$TARGET_PATH/README.md"
  sed -i "s/Part of the QA Vision Platform (QEOS) – Platform Domain./Part of the QA Vision Platform (QEOS) – $DOMAIN Domain./g" "$TARGET_PATH/README.md"
  sed -i "s/Provides CRUD operations for Organizations (tenants) and related metadata./Provides CRUD operations for $SERVICE_DESCRIPTION./g" "$TARGET_PATH/README.md"
fi

echo "Service $SERVICE_NAME created at $TARGET_PATH"
echo "Next steps:"
echo "  1. Review and adjust configuration in $TARGET_PATH/.env"
echo "  2. Update API contracts in shared/contracts/ if needed"
echo "  3. Run initial build/test: cd $TARGET_PATH && make build (or docker build)"
echo "  4. Register service in infrastructure (Helm chart under infra/helm/$DOMAIN/$SERVICE_NAME)"
