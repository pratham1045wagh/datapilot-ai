from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    user_question: str
    dataset_id: str

class SelfCorrectionLog(BaseModel):
    attempt: int
    sql_attempted: str
    error_message: str
    reasoning: str

class QueryResponse(BaseModel):
    user_question: str
    dataset_id: str
    table_name: str
    query_plan: str
    generated_sql: str
    initial_sql: Optional[str] = None
    executed_sql: Optional[str] = None
    formatted_sql: Optional[str] = None
    is_valid: bool
    executed: bool
    execution_error: Optional[str] = None
    retries: int = 0
    self_correction_logs: List[SelfCorrectionLog] = []
    columns: List[str] = []
    rows: List[Dict[str, Any]] = []
    row_count: int = 0
    explanation: str = ""
    visualization_type: str = "none"  # bar, line, pie, stat, table, none
    chart_config: Optional[Dict[str, Any]] = None
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    timestamp: Optional[str] = None
