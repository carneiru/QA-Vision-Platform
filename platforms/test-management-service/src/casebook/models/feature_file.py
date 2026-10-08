from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from src.casebook.db.base import Base


class FeatureFile(Base):
    """The raw text of an imported .feature file, as of its last import. One row per (project, path)."""

    __tablename__ = "feature_files"
    __table_args__ = (UniqueConstraint("project_id", "path", name="uq_feature_files_project_path"),)

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False, index=True)
    path = Column(String(500), nullable=False)  # the cases' source_path
    feature_name = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)  # at most IMPORT_MAX_FILE_BYTES: larger files are refused at import
    content_sha256 = Column(String(64), nullable=False)
    imported_at = Column(DateTime(timezone=True), nullable=False)
