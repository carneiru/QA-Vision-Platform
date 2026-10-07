from sqlalchemy.orm import declarative_base

# Deliberately per-service (not in qeos_shared): a declarative base is a global registry of
# mapped classes, and sharing one would mix services' tables into a single metadata.
Base = declarative_base()
