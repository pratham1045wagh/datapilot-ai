from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CleaningRecommendation(BaseModel):
    id: str
    issue_type: str
    column: Optional[str] = None
    affected_count: int = 0
    affected_pct: float = 0.0
    operation: str  # remove_duplicates, fill_missing, convert_numeric, convert_date, normalize_casing, remove_outliers, remove_column, filter_rows, normalize_text
    recommended_strategy: str  # mean, median, mode, unknown, remove_rows, titlecase, yyyy_mm_dd, etc.
    available_strategies: List[str] = []
    reason: str
    risk_level: str = "low"  # low, medium, high
    expected_impact: str
    recommended: bool = True
    source: str = "ai_recommended"  # "ai_recommended" or "user_requested"

class UserActionApproval(BaseModel):
    recommendation_id: str
    approved: bool
    selected_strategy: Optional[str] = None
    custom_value: Optional[Any] = None

class UserSuggestionRequest(BaseModel):
    user_instruction: str

class UserSuggestionResponse(BaseModel):
    supported: bool
    unsupported_reason: Optional[str] = None
    interpretation: Optional[Dict[str, Any]] = None
    recommendation: Optional[CleaningRecommendation] = None

class PreviewRequest(BaseModel):
    actions: List[UserActionApproval]

class PreviewImpactItem(BaseModel):
    recommendation_id: str
    column: Optional[str] = None
    operation: str
    strategy: str
    expected_effect: str
    affected_rows: int
    source: str = "ai_recommended"

class CleaningExecutionRequest(BaseModel):
    actions: List[UserActionApproval]

class CleaningHistoryItem(BaseModel):
    recommendation_id: str
    operation: str
    column: Optional[str] = None
    strategy: str
    user_decision: str  # approved, declined
    execution_status: str  # applied, failed, skipped
    details: str
    source: str = "ai_recommended"

class BeforeAfterComparison(BaseModel):
    metric: str
    before: Any
    after: Any
    improvement: str

class VerificationCheck(BaseModel):
    check_name: str
    status: str  # PASSED, WARNING, FAILED
    expected: str
    actual: str
    details: str

class VerificationReport(BaseModel):
    overall_status: str  # PASSED, WARNING, FAILED
    message: str
    checks: List[VerificationCheck]
    repair_attempts: int = 0

class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    total_rows: int
    total_cols: int
    columns: List[str]
    rows: List[Dict[str, Any]]
    page: int
    page_size: int
    total_pages: int
    verification_status: str = "VERIFIED"  # VERIFIED, WARNING, FAILED

class CleaningReport(BaseModel):
    dataset_id: str
    original_filename: str
    timestamp: str
    original_rows: int
    final_rows: int
    original_cols: int
    final_cols: int
    operations_applied: List[CleaningHistoryItem]
    operations_declined: List[CleaningHistoryItem]
    user_requested_actions: List[CleaningHistoryItem] = []
    before_after_comparison: List[BeforeAfterComparison]
    verification_report: Optional[VerificationReport] = None
    sqlite_table_name: Optional[str] = None
    agent_state: str = "VERIFIED"  # ANALYZING, AWAITING_APPROVAL, PROCESSING, VERIFYING, VERIFIED, WARNING, FAILED

class PostCleanSuggestionRequest(BaseModel):
    user_instruction: str

class PostCleanSuggestionAnalysis(BaseModel):
    supported: bool
    unsupported_reason: Optional[str] = None
    requested_change: Optional[str] = None
    column: Optional[str] = None
    operation: Optional[str] = None
    mapping: Optional[Dict[str, str]] = None
    strategy: Optional[str] = None
    current_values: List[str] = []
    proposed_values: List[str] = []
    affected_rows: int = 0
    risk: str = "low"  # low, medium, high
    reason: Optional[str] = None
    expected_impact: Optional[str] = None

class PostCleanApplyRequest(BaseModel):
    user_instruction: str
    requested_change: str
    column: Optional[str] = None
    operation: str
    mapping: Optional[Dict[str, str]] = None
    strategy: Optional[str] = None
    approved: bool = True

class PostCleanApplyResponse(BaseModel):
    status: str
    message: str
    affected_rows: int = 0
    before_values: List[str] = []
    after_values: List[str] = []
    report: CleaningReport

