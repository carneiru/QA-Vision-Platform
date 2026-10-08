from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class FeatureItem(BaseModel):
    feature_name: Optional[str] = None  # None with path None: the manual cases
    path: Optional[str] = None
    folder: Optional[str] = None
    case_count: int
    case_numbers: List[int]  # the first 200, by number
    test_keys: List[str] = []  # distinct automated_test_keys of the cases, sorted, at most 200
    has_source: bool  # the raw file text is stored
    linked_count: int  # cases with an automated_test_key
    top_priority: Optional[Literal["critical", "high", "medium", "low"]] = None  # the highest in the group
    status_counts: Dict[str, int]  # every status, 0 when none


class FeatureList(BaseModel):
    total: int
    items: List[FeatureItem]


class FeatureCase(BaseModel):
    number: int
    key: str
    title: str
    scenario_name: Optional[str] = None
    status: str
    priority: str
    automated_test_key: Optional[str] = None
    line: Optional[int] = None  # the scenario's heading in the stored file; None without the file text


class FeatureDetail(BaseModel):
    feature_name: Optional[str] = None
    path: str
    folder: Optional[str] = None
    content: Optional[str] = None
    imported_at: Optional[datetime] = None
    cases: List[FeatureCase]
