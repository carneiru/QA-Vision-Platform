"""Value object for model evaluation metrics."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass(frozen=True)
class ModelMetrics:
    """Value object for model evaluation metrics."""

    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    auc_roc: Optional[float] = None
    mse: Optional[float] = None
    mae: Optional[float] = None
    r2_score: Optional[float] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "auc_roc": self.auc_roc,
            "mse": self.mse,
            "mae": self.mae,
            "r2_score": self.r2_score,
            "custom_metrics": self.custom_metrics,
            "calculated_at": self.calculated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetrics":
        """Create from dictionary."""
        data_copy = data.copy()
        if "calculated_at" in data_copy and isinstance(data_copy["calculated_at"], str):
            data_copy["calculated_at"] = datetime.fromisoformat(data_copy["calculated_at"])
        return cls(**data_copy)