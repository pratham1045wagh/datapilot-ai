import datetime
import logging
from typing import List, Dict, Any, Optional
from app.services.database_service import database_service
from app.services.gemini_service import gemini_service
from app.validators.sql_validator import validate_read_only_sql, sanitize_sql
from app.models.query_models import QueryResponse, SelfCorrectionLog
from app.utils.sql_formatter import format_sql_for_display

logger = logging.getLogger("sql_agent")

class SqlAgent:
    def __init__(self):
        self._history: List[QueryResponse] = []

    def execute_query(self, user_question: str, dataset_id: str, table_name: Optional[str] = None) -> QueryResponse:
        """
        Processes natural language question against SQLite database.
        Performs validation, execution, and self-correction loop up to 3 tries.
        """
        # Determine SQLite table name if not provided directly
        if not table_name:
            # Look up table in SQLite DB matching dataset_id
            conn = database_service._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?;", (f"%{dataset_id[:8]}%",))
                row = cursor.fetchone()
                if row:
                    table_name = row["name"]
                else:
                    # Fallback to first non-system table
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    row = cursor.fetchone()
                    if not row:
                        raise ValueError("No table found in SQLite database. Please clean and ingest dataset first.")
                    table_name = row["name"]
            finally:
                conn.close()

        # Step 1: Inspect database schema
        schema_info = database_service.get_table_schema(table_name)
        sample_rows = database_service.get_sample_rows(table_name, limit=3)
        valid_cols = [c["name"] for c in schema_info]

        # Step 2: Generate SQL Query
        gen_payload = gemini_service.generate_sql_query(user_question, table_name, schema_info, sample_rows)
        query_plan = gen_payload.get("query_plan", "Generated query based on schema analysis.")
        raw_sql = gen_payload.get("sql", f'SELECT * FROM "{table_name}" LIMIT 10;')
        viz_type = gen_payload.get("visualization_type", "table")
        explanation = gen_payload.get("explanation", "")

        initial_sql = sanitize_sql(raw_sql)
        cleaned_sql = initial_sql
        self_correction_logs: List[SelfCorrectionLog] = []
        max_attempts = 3
        attempt = 1
        executed = False
        execution_error = None
        columns: List[str] = []
        rows: List[Dict[str, Any]] = []
        row_count = 0

        # Self-Correction Execution Loop
        while attempt <= max_attempts and not executed:
            # Validate read-only security rules
            is_valid, val_error = validate_read_only_sql(cleaned_sql, valid_cols)
            if not is_valid:
                execution_error = f"SQL Security Validation Error: {val_error}"
                self_correction_logs.append(SelfCorrectionLog(
                    attempt=attempt,
                    sql_attempted=cleaned_sql,
                    error_message=execution_error,
                    reasoning=f"Query failed security validation: {val_error}"
                ))
                # Request correction from LLM
                corr_payload = gemini_service.correct_sql_query(
                    user_question, table_name, schema_info, cleaned_sql, execution_error, attempt
                )
                cleaned_sql = sanitize_sql(corr_payload.get("sql", f'SELECT * FROM "{table_name}" LIMIT 10;'))
                attempt += 1
                continue

            # Execute query against SQLite
            try:
                columns, rows, row_count = database_service.execute_query(cleaned_sql)
                
                # Step 3: Categorical Duplicate Result Validation
                dup_err = self._validate_categorical_results(columns, rows)
                if dup_err:
                    logger.warning(f"Categorical result validation failed on attempt {attempt}: {dup_err}")
                    self_correction_logs.append(SelfCorrectionLog(
                        attempt=attempt,
                        sql_attempted=cleaned_sql,
                        error_message=dup_err,
                        reasoning=f"Query returned duplicate-looking categorical labels due to un-normalized grouping."
                    ))
                    if attempt < max_attempts:
                        corr_payload = gemini_service.correct_sql_query(
                            user_question, table_name, schema_info, cleaned_sql, dup_err, attempt
                        )
                        cleaned_sql = sanitize_sql(corr_payload.get("sql", f'SELECT * FROM "{table_name}" LIMIT 10;'))
                        # Fallback fix if LLM didn't fix GROUP BY
                        if "LOWER" not in cleaned_sql.upper() and "COLLATE" not in cleaned_sql.upper():
                            import re
                            cleaned_sql = re.sub(
                                r'GROUP\s+BY\s+(?:TRIM\s*\(\s*"?(\w+)"?\s*\)|"?(\w+)"?)',
                                r'GROUP BY LOWER(TRIM("\1\2"))',
                                cleaned_sql,
                                flags=re.IGNORECASE
                            )
                    else:
                        execution_error = f"Execution validation failed after {max_attempts} attempts: {dup_err}"
                    attempt += 1
                    continue

                executed = True
                execution_error = None
            except Exception as e:
                db_err_msg = str(e)
                logger.warning(f"SQL Execution error on attempt {attempt}: {db_err_msg}")
                self_correction_logs.append(SelfCorrectionLog(
                    attempt=attempt,
                    sql_attempted=cleaned_sql,
                    error_message=db_err_msg,
                    reasoning=f"Database execution error: {db_err_msg}"
                ))

                if attempt < max_attempts:
                    corr_payload = gemini_service.correct_sql_query(
                        user_question, table_name, schema_info, cleaned_sql, db_err_msg, attempt
                    )
                    cleaned_sql = sanitize_sql(corr_payload.get("sql", f'SELECT * FROM "{table_name}" LIMIT 10;'))
                else:
                    execution_error = f"Execution failed after {max_attempts} attempts: {db_err_msg}"
                attempt += 1

        # Check for location/city field note requirement
        q_lower = user_question.lower()
        if "city" in q_lower and "city" not in [c.lower() for c in valid_cols] and "branch" in [c.lower() for c in valid_cols]:
            loc_note = "The dataset does not contain a city column, so I used the branch field as the available location field."
            if loc_note not in explanation:
                explanation = f"{explanation} ({loc_note})" if explanation else loc_note

        # Generate NL explanation & Chart configuration if query succeeded
        if executed:
            exp_res = gemini_service.explain_query_results(user_question, cleaned_sql, columns, rows)
            if exp_res.get("summary"):
                explanation = exp_res["summary"]
                q_lower = user_question.lower()
                if "city" in q_lower and "city" not in [c.lower() for c in valid_cols] and "branch" in [c.lower() for c in valid_cols]:
                    loc_note = "The dataset does not contain a city column, so I used the branch field as the available location field."
                    if loc_note not in explanation:
                        explanation = f"{explanation} ({loc_note})"
            if exp_res.get("visualization_type"):
                viz_type = exp_res["visualization_type"]
            chart_config = {
                "x_axis": exp_res.get("x_axis") or (columns[0] if columns else None),
                "y_axis": exp_res.get("y_axis") or (columns[1] if len(columns) > 1 else columns[0] if columns else None)
            }
        else:
            chart_config = None

        x_ax = chart_config.get("x_axis") if chart_config else None
        y_ax = chart_config.get("y_axis") if chart_config else None

        exec_sql_final = cleaned_sql if executed else (cleaned_sql if self_correction_logs else initial_sql)
        formatted_sql_final = format_sql_for_display(exec_sql_final)

        response = QueryResponse(
            user_question=user_question,
            dataset_id=dataset_id,
            table_name=table_name,
            query_plan=query_plan,
            initial_sql=initial_sql,
            executed_sql=exec_sql_final,
            generated_sql=cleaned_sql,
            formatted_sql=formatted_sql_final,
            is_valid=True if executed else False,
            executed=executed,
            execution_error=execution_error,
            retries=len(self_correction_logs),
            self_correction_logs=self_correction_logs,
            columns=columns,
            rows=rows,
            row_count=row_count,
            explanation=explanation,
            visualization_type=viz_type,
            chart_config=chart_config,
            x_axis=x_ax,
            y_axis=y_ax,
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        self._history.append(response)
        return response

    def _validate_categorical_results(self, columns: List[str], rows: List[Dict[str, Any]]) -> Optional[str]:
        """
        Validates that GROUP BY aggregation results do not contain duplicate-looking categorical labels
        due to whitespace or case inconsistencies (e.g. 'Bandra' and 'bandra' or 'Bandra ').
        """
        if not rows or len(rows) <= 1 or not columns:
            return None

        for col in columns:
            vals = [r[col] for r in rows if r.get(col) is not None]
            if not vals:
                continue
            # Check if values are string categoricals (not pure numbers)
            str_vals = [str(v) for v in vals if isinstance(v, str) and not v.replace('.', '', 1).isdigit()]
            if len(str_vals) <= 1:
                continue

            norm_vals = [v.strip().lower() for v in str_vals]
            if len(set(norm_vals)) < len(norm_vals):
                return (
                    f"Validation Error: Query result column '{col}' contains duplicate categorical labels after casing/whitespace normalization: {str_vals}. "
                    f"The GROUP BY clause must use LOWER(TRIM(\"{col}\")) or TRIM(\"{col}\") COLLATE NOCASE so identical logical categories are aggregated into a single row."
                )

        return None

    def get_query_history(self, dataset_id: Optional[str] = None) -> List[QueryResponse]:
        if dataset_id:
            return [q for q in self._history if q.dataset_id == dataset_id]
        return self._history

sql_agent = SqlAgent()
