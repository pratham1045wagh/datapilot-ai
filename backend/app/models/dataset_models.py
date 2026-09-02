from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ColumnProfile(BaseModel):
    name: str
    data_type: str
    total_count: int
    missing_count: int
    missing_pct: float
    unique_count: int
    sample_values: List[Any] = []
    numeric_stats: Optional[Dict[str, float]] = None
    outlier_count: int = 0
    inconsistent_variants: Optional[List[str]] = None

class DatasetProfile(BaseModel):
    dataset_id: str
    filename: str
    original_filename: str
    row_count: int
    column_count: int
    total_missing: int
    total_duplicates: int
    memory_kb: float
    columns: List[ColumnProfile]
    sample_data: List[Dict[str, Any]] = []

class DataIssue(BaseModel):
    issue_type: str  # missing_values, duplicates, text_as_numeric, invalid_dates, casing_inconsistency, outliers
    column: Optional[str] = None
    affected_count: int
    affected_pct: float
    severity: str  # Low, Medium, High
    explanation: str
    recommended_action: str
    risk_level: str  # low, medium, high
