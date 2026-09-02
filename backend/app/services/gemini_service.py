import json
import logging
import re
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("gemini_service")

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini client initialized with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize google-genai SDK directly: {e}. Trying google.generativeai fallback.")
                try:
                    import google.generativeai as ggi
                    ggi.configure(api_key=self.api_key)
                    self._client = ggi.GenerativeModel(self.model_name)
                except Exception as ex:
                    logger.error(f"Failed to initialize Gemini fallback: {ex}")

    def generate_cleaning_recommendations(
        self,
        dataset_summary: Dict[str, Any],
        issues: List[Dict[str, Any]],
        sample_rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Uses Gemini to analyze data quality issues and return structured JSON recommendations.
        """
        prompt = f"""You are an expert Data Preparation Agent. Analyze the following dataset issues and sample rows.
Dataset Summary: {json.dumps(dataset_summary, default=str)}
Detected Issues: {json.dumps(issues, default=str)}
Sample Rows: {json.dumps(sample_rows[:3], default=str)}

Return a strict JSON array of cleaning recommendation objects.
Each object must have these exact keys:
- "id": unique identifier string like "rec_001", "rec_002"
- "issue_type": type of issue (missing_values, duplicates, text_as_numeric, invalid_dates, casing_inconsistency, outliers)
- "column": name of affected column or null if whole dataset
- "affected_count": integer number of affected rows/records
- "affected_pct": float percentage affected
- "operation": string operation code (remove_duplicates, fill_missing, convert_numeric, convert_date, normalize_casing, remove_outliers)
- "recommended_strategy": string strategy code (for numeric missing: "median" or "mean" or "remove_rows"; for text missing: "mode" or "unknown" or "remove_rows"; for casing: "titlecase" or "lowercase"; for numeric conversion: "safe_convert"; for duplicates: "remove_all")
- "available_strategies": list of string choices (e.g. ["median", "mean", "mode", "unknown", "remove_rows", "custom"])
- "reason": detailed clear reason why this strategy is recommended
- "risk_level": "low", "medium", or "high" (outliers and large row deletions must be "high")
- "expected_impact": brief human readable string describing outcome (e.g. "43 missing values filled with median value 31")
- "recommended": true

Rules:
1. Outliers must ALWAYS be classified as risk_level "high".
2. Removing duplicate rows should be "low" risk.
3. Output ONLY the JSON array inside a json block. No conversational text.
"""
        if self._client:
            try:
                raw_response = self._call_gemini(prompt)
                parsed = self._extract_json(raw_response)
                if isinstance(parsed, list):
                    return parsed
            except Exception as e:
                logger.error(f"Gemini API error during cleaning recs: {e}")

        # Heuristic fallback if LLM is unavailable
        return self._generate_heuristic_recommendations(issues)

    def generate_sql_query(
        self,
        user_question: str,
        table_name: str,
        schema_info: List[Dict[str, Any]],
        sample_rows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates read-only SQL query for user question.
        """
        prompt = f"""You are a SQL Generation Agent.
Database System: SQLite
Table Name: "{table_name}"

Schema Columns:
{json.dumps(schema_info, indent=2)}

Sample Data (First 3 rows):
{json.dumps(sample_rows[:3], indent=2, default=str)}

User Question: "{user_question}"

Rules:
1. Return ONLY read-only SQL (SELECT queries).
2. Do NOT use DROP, DELETE, INSERT, UPDATE, ALTER, or TRUNCATE.
3. Use exact column names provided in the schema. Wrap table name in double quotes if needed.
4. Categorical Text Aggregation Normalization:
   When performing GROUP BY on text/categorical columns (e.g. city, branch, category, gender, account_type, customer_segment, status):
   Use TRIM("col") in SELECT for user-friendly display, and LOWER(TRIM("col")) in GROUP BY clauses to ensure leading/trailing spaces or case variations do not split identical categories into duplicate rows.
   Example: SELECT TRIM("branch") AS branch, SUM("sales") AS total_sales FROM "table" GROUP BY LOWER(TRIM("branch")) ORDER BY total_sales DESC;
   Do NOT alias "branch" AS "city" if user asks for city but dataset only has branch. Keep column name as branch (e.g., TRIM("branch") AS branch).
5. Schema Matching & Location Field Explanation:
   If user asks about "city" but the schema contains no "city" column and has "branch", query "branch" as SELECT TRIM("branch") AS branch (do NOT alias "branch" as "city").
   In the "explanation" string, clearly state: "The dataset does not contain a city column, so I used the branch field as the available location field."
6. Return a JSON object with:
   - "query_plan": step-by-step reasoning in 1-2 sentences
   - "sql": valid SQLite SELECT query
   - "visualization_type": recommended chart type ("bar", "line", "pie", "stat", "table")
   - "explanation": brief explanation of what the query calculates

Return output ONLY as JSON.
"""
        if self._client:
            try:
                raw_response = self._call_gemini(prompt)
                parsed = self._extract_json(raw_response)
                if isinstance(parsed, dict) and "sql" in parsed:
                    return parsed
            except Exception as e:
                err_msg = str(e)
                logger.error(f"Gemini API error during SQL generation: {err_msg}")
                fallback_res = self._generate_heuristic_sql(user_question, table_name, schema_info)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    fallback_res["explanation"] += " (Note: Gemini API free-tier rate limit reached. Smart schema intent matching generator computed this query.)"
                return fallback_res

        return self._generate_heuristic_sql(user_question, table_name, schema_info)

    def correct_sql_query(
        self,
        user_question: str,
        table_name: str,
        schema_info: List[Dict[str, Any]],
        failed_sql: str,
        error_message: str,
        attempt: int
    ) -> Dict[str, Any]:
        """
        Self-corrects a failed SQL query given the database error.
        """
        prompt = f"""You are an expert SQL Debugging Agent.
The SQL query you generated failed to execute on SQLite.

Table Name: "{table_name}"
Schema Columns:
{json.dumps(schema_info, indent=2)}

User Question: "{user_question}"
Attempt: {attempt}
Failed SQL: {failed_sql}
SQLite Error Message: {error_message}

Task:
Analyze why the query failed (e.g. invalid column name, wrong syntax, type mismatch).
Correct the SQL query so it runs successfully on SQLite.

Return a JSON object with:
- "reasoning": explanation of what went wrong and how you fixed it
- "sql": corrected SQLite SELECT query
- "visualization_type": "bar", "line", "pie", "stat", or "table"
- "explanation": brief explanation of what query calculates
"""
        if self._client:
            try:
                raw_response = self._call_gemini(prompt)
                parsed = self._extract_json(raw_response)
                if isinstance(parsed, dict) and "sql" in parsed:
                    return parsed
            except Exception as e:
                logger.error(f"Gemini API error during SQL correction: {e}")

        return self._generate_heuristic_sql_correction(failed_sql, schema_info, table_name)

    def explain_query_results(
        self,
        user_question: str,
        sql: str,
        columns: List[str],
        rows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates natural language summary of query execution results and chart configuration.
        """
        prompt = f"""You are a Data Analyst Agent.
User Question: "{user_question}"
SQL Query Executed: {sql}
Result Summary: {len(rows)} rows returned.
Sample Results: {json.dumps(rows[:5], default=str)}

Task:
Provide a clear, human-friendly summary of the query findings.
Suggest the best chart visualization (bar, line, pie, stat, or table).

Return JSON with:
- "summary": 2-3 sentence natural language explanation of the results.
- "visualization_type": "bar", "line", "pie", "stat", or "table"
- "x_axis": column name for X axis / category (if applicable)
- "y_axis": column name for Y axis / numeric value (if applicable)
"""
        if self._client:
            try:
                raw_response = self._call_gemini(prompt)
                parsed = self._extract_json(raw_response)
                if isinstance(parsed, dict):
                    return parsed
            except Exception as e:
                logger.error(f"Gemini API error during result explanation: {e}")

        return {
            "summary": f"Query returned {len(rows)} record(s).",
            "visualization_type": "bar" if len(rows) > 1 and len(columns) >= 2 else "stat" if len(rows) == 1 else "table",
            "x_axis": columns[0] if columns else None,
            "y_axis": columns[1] if len(columns) > 1 else columns[0] if columns else None
        }

    def _call_gemini(self, prompt: str) -> str:
        if not self._client:
            raise ValueError("Gemini client not initialized")
        
        # Build prioritized list of candidate models
        candidate_models = []
        for m in [self.model_name, "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash"]:
            if m and m not in candidate_models:
                candidate_models.append(m)

        last_exception = None

        # Using official google-genai Client format
        if hasattr(self._client, "models") and hasattr(self._client.models, "generate_content"):
            from google.genai import types
            for model_to_try in candidate_models:
                try:
                    config = types.GenerateContentConfig(response_mime_type="application/json")
                    res = self._client.models.generate_content(
                        model=model_to_try,
                        contents=prompt,
                        config=config
                    )
                    if res and res.text:
                        return res.text
                except Exception as ex:
                    logger.warning(f"Gemini model '{model_to_try}' structured call failed: {ex}. Trying standard generate_content.")
                    try:
                        res = self._client.models.generate_content(
                            model=model_to_try,
                            contents=prompt
                        )
                        if res and res.text:
                            return res.text
                    except Exception as err:
                        logger.warning(f"Gemini model '{model_to_try}' call failed: {err}. Trying next candidate model.")
                        last_exception = err
            if last_exception:
                raise last_exception
        # Fallback format for google.generativeai model
        elif hasattr(self._client, "generate_content"):
            res = self._client.generate_content(prompt)
            return res.text
        raise ValueError("Unsupported Gemini client instance or all model candidates failed")

    def _extract_json(self, text: str) -> Any:
        if not text:
            raise ValueError("Empty response text from Gemini API")
        text = text.strip()
        
        # Try extracting fenced codeblock
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                text = extracted

        # Direct JSON load
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Search for first JSON object {...} or array [...]
        json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if json_match:
            candidate = json_match.group(1).strip()
            cleaned = re.sub(r',\s*([}\]])', r'\1', candidate)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError("Could not extract valid JSON from LLM response", text, 0)

    def _generate_heuristic_recommendations(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        recs = []
        for idx, issue in enumerate(issues):
            rec_id = f"rec_{idx+1:03d}"
            itype = issue.get("issue_type")
            col = issue.get("column")
            cnt = issue.get("affected_count", 0)
            pct = issue.get("affected_pct", 0.0)

            if itype == "duplicates":
                recs.append({
                    "id": rec_id,
                    "issue_type": "duplicates",
                    "column": None,
                    "affected_count": cnt,
                    "affected_pct": pct,
                    "operation": "remove_duplicates",
                    "recommended_strategy": "remove_all",
                    "available_strategies": ["remove_all"],
                    "reason": f"Detected {cnt} exact duplicate rows. Removing duplicates improves data consistency.",
                    "risk_level": "low",
                    "expected_impact": f"Remove {cnt} duplicate row(s)",
                    "recommended": True
                })
            elif itype == "missing_values":
                col_type = issue.get("data_type", "text")
                is_numeric = "float" in col_type or "int" in col_type or "numeric" in col_type
                strat = "median" if is_numeric else "mode"
                choices = ["median", "mean", "mode", "unknown", "remove_rows", "custom"] if is_numeric else ["mode", "unknown", "remove_rows", "custom"]
                recs.append({
                    "id": rec_id,
                    "issue_type": "missing_values",
                    "column": col,
                    "affected_count": cnt,
                    "affected_pct": pct,
                    "operation": "fill_missing",
                    "recommended_strategy": strat,
                    "available_strategies": choices,
                    "reason": f"Column '{col}' has {cnt} missing value(s). {strat.capitalize()} imputation preserves statistical distribution.",
                    "risk_level": "medium",
                    "expected_impact": f"Fill {cnt} missing value(s) using {strat}",
                    "recommended": True
                })
            elif itype == "text_as_numeric":
                recs.append({
                    "id": rec_id,
                    "issue_type": "text_as_numeric",
                    "column": col,
                    "affected_count": cnt,
                    "affected_pct": pct,
                    "operation": "convert_numeric",
                    "recommended_strategy": "safe_convert",
                    "available_strategies": ["safe_convert"],
                    "reason": f"Column '{col}' contains numeric values formatted as strings (e.g. '$100').",
                    "risk_level": "low",
                    "expected_impact": f"Convert column '{col}' to numeric float data type",
                    "recommended": True
                })
            elif itype == "casing_inconsistency":
                recs.append({
                    "id": rec_id,
                    "issue_type": "casing_inconsistency",
                    "column": col,
                    "affected_count": cnt,
                    "affected_pct": pct,
                    "operation": "normalize_casing",
                    "recommended_strategy": "titlecase",
                    "available_strategies": ["titlecase", "lowercase", "uppercase"],
                    "reason": f"Column '{col}' has inconsistent capitalization variants (e.g., 'mumbai' vs 'MUMBAI').",
                    "risk_level": "low",
                    "expected_impact": f"Standardize capitalization variants in column '{col}'",
                    "recommended": True
                })
            elif itype == "outliers":
                recs.append({
                    "id": rec_id,
                    "issue_type": "outliers",
                    "column": col,
                    "affected_count": cnt,
                    "affected_pct": pct,
                    "operation": "remove_outliers",
                    "recommended_strategy": "iqr_filter",
                    "available_strategies": ["iqr_filter", "ignore"],
                    "reason": f"Column '{col}' contains {cnt} potential extreme value outlier(s) based on 1.5x IQR.",
                    "risk_level": "high",
                    "expected_impact": f"Review or filter out {cnt} extreme outlier row(s)",
                    "recommended": False
                })
        return recs

    def _generate_heuristic_sql(self, question: str, table_name: str, schema: List[Dict[str, Any]]) -> Dict[str, Any]:
        q_lower = question.lower()
        
        # Classify columns from schema
        num_cols = []
        cat_cols = []
        date_cols = []
        col_names = []

        for c in schema:
            name = c["name"]
            col_names.append(name)
            t = str(c.get("type", "")).lower()
            if "int" in t or "float" in t or "double" in t or "real" in t or "numeric" in t:
                num_cols.append(name)
            elif "date" in t or "time" in t:
                date_cols.append(name)
            else:
                cat_cols.append(name)

        # Find columns explicitly matched in user question
        words_in_q = set(re.findall(r'\b\w+\b', q_lower))
        matched_cols = []
        for name in col_names:
            nl = name.lower()
            if nl in q_lower or any(w == nl or w in nl.split('_') for w in words_in_q if len(w) > 2):
                matched_cols.append(name)

        has_group_by = any(k in q_lower for k in ["by", "per", "each", "group", "grouped", "breakdown"])

        matched_num = [c for c in num_cols if c in matched_cols]
        matched_cat = [c for c in cat_cols if c in matched_cols]

        target_num = (matched_num[0] if matched_num else num_cols[0]) if num_cols else None
        target_cat = (matched_cat[0] if matched_cat else cat_cols[0]) if cat_cols else None

        # Check if user asked for "city" but only "branch" exists
        city_explanation_note = ""
        if "city" in q_lower and "city" not in col_names and "branch" in col_names:
            target_cat = "branch"
            city_explanation_note = " (Note: The dataset does not contain a city column, so I used the branch field as the available location field.)"

        # Aggregation intent detection
        is_count = any(k in q_lower for k in ["count", "how many", "number of", "records", "total count"])
        is_avg = any(k in q_lower for k in ["average", "avg", "mean"])
        is_max = any(k in q_lower for k in ["highest", "maximum", "max", "top", "best", "most"])
        is_min = any(k in q_lower for k in ["lowest", "minimum", "min", "worst", "least"])
        is_sum = any(k in q_lower for k in ["sum", "total", "overall", "revenue", "sales", "amount"])

        viz = "table"
        explanation = f"Generated SQL query for '{question}'." + city_explanation_note

        if is_count:
            if has_group_by and target_cat:
                sql = f'SELECT TRIM("{target_cat}") AS "{target_cat}", COUNT(*) AS total_count FROM "{table_name}" GROUP BY LOWER(TRIM("{target_cat}")) ORDER BY total_count DESC;'
                viz = "bar"
                plan = f"Group dataset by trimmed '{target_cat}' and calculate record counts."
            else:
                sql = f'SELECT COUNT(*) AS total_count FROM "{table_name}";'
                viz = "stat"
                plan = "Calculate total row count in dataset."
        elif is_avg and target_num:
            if has_group_by and target_cat:
                sql = f'SELECT TRIM("{target_cat}") AS "{target_cat}", AVG("{target_num}") AS avg_{target_num} FROM "{table_name}" GROUP BY LOWER(TRIM("{target_cat}")) ORDER BY avg_{target_num} DESC;'
                viz = "bar"
                plan = f"Calculate average '{target_num}' grouped by trimmed '{target_cat}'."
            else:
                sql = f'SELECT AVG("{target_num}") AS avg_{target_num} FROM "{table_name}";'
                viz = "stat"
                plan = f"Calculate average of '{target_num}' across dataset."
        elif (is_max or is_sum or is_min) and target_num:
            order_dir = "ASC" if is_min else "DESC"
            if has_group_by and target_cat:
                sql = f'SELECT TRIM("{target_cat}") AS "{target_cat}", SUM("{target_num}") AS total_{target_num} FROM "{table_name}" GROUP BY LOWER(TRIM("{target_cat}")) ORDER BY total_{target_num} {order_dir} LIMIT 10;'
                viz = "bar"
                plan = f"Group by trimmed '{target_cat}' and calculate sum of '{target_num}' ordered {order_dir}."
            else:
                sql = f'SELECT * FROM "{table_name}" ORDER BY "{target_num}" {order_dir} LIMIT 5;'
                viz = "table"
                plan = f"Order records by '{target_num}' {order_dir}."
        elif has_group_by and target_cat and target_num:
            sql = f'SELECT TRIM("{target_cat}") AS "{target_cat}", SUM("{target_num}") AS total_{target_num} FROM "{table_name}" GROUP BY LOWER(TRIM("{target_cat}")) ORDER BY total_{target_num} DESC LIMIT 10;'
            viz = "bar"
            plan = f"Aggregate '{target_num}' grouped by '{target_cat}'."
        elif matched_cols:
            cols_str = ", ".join([f'"{c}"' for c in matched_cols[:4]])
            sql = f'SELECT {cols_str} FROM "{table_name}" LIMIT 10;'
            viz = "table"
            plan = f"Retrieve requested columns ({cols_str}) from dataset."
        else:
            first_cols = ", ".join([f'"{c}"' for c in col_names[:4]])
            sql = f'SELECT {first_cols} FROM "{table_name}" LIMIT 10;'
            viz = "table"
            plan = "Retrieve sample records from dataset."

        return {
            "query_plan": plan,
            "sql": sql,
            "visualization_type": viz,
            "explanation": explanation
        }

    def _generate_heuristic_sql_correction(self, failed_sql: str, schema: List[Dict[str, Any]], table_name: str) -> Dict[str, Any]:
        col_names = [c["name"] for c in schema]
        first_col = col_names[0] if col_names else "*"
        corrected = f'SELECT "{first_col}" FROM "{table_name}" LIMIT 10;'
        return {
            "reasoning": f"Query contained non-existent columns. Fallback to selecting {first_col}.",
            "sql": corrected,
            "visualization_type": "table",
            "explanation": "Corrected query to select standard column."
        }

    def analyze_user_suggestion(
        self,
        user_instruction: str,
        dataset_summary: Dict[str, Any],
        sample_rows: List[Dict[str, Any]],
        columns: List[str]
    ) -> Dict[str, Any]:
        """
        Analyzes a natural language user preprocessing instruction via Gemini.
        Returns structured JSON for UserSuggestionResponse.
        NEVER generates executable Python code.
        """
        prompt = f"""You are an AI Data Preparation Assistant.
Dataset Columns: {json.dumps(columns)}
Dataset Summary: {json.dumps(dataset_summary, default=str)}
Sample Data (First 3 rows): {json.dumps(sample_rows[:3], default=str)}

User Preprocessing Request: "{user_instruction}"

Task:
Analyze if this user instruction can be mapped to one of the supported data cleaning operations:
Supported Operations:
1. Missing value handling (fill_missing: median, mean, mode, unknown, custom, remove_rows)
2. Duplicate removal (remove_duplicates: remove_all)
3. Numeric conversion (convert_numeric: safe_convert)
4. Date conversion/formatting (convert_date: yyyy_mm_dd, datetime)
5. Category normalization (normalize_casing: titlecase, lowercase, uppercase)
6. Outlier handling (remove_outliers: iqr_filter)
7. Column removal (remove_column: delete)
8. Row filtering (filter_rows: remove_negative, remove_condition)
9. Text normalization (normalize_text: strip_spaces)

Rules:
- If the instruction is vague, unsupported, or unsafe (e.g. "make dataset perfect", "hack database", "run code"), set "supported": false and explain clearly.
- If supported, set "supported": true, identify affected column, operation, strategy, risk level, expected impact, and return a recommendation object.

Return JSON with:
- "supported": true/false
- "unsupported_reason": null or explanation string if false
- "interpretation": {{
    "requested_action": "...",
    "detected_column": "col_name or null",
    "current_format": "...",
    "proposed_format": "...",
    "affected_rows": number,
    "risk_level": "low" | "medium" | "high",
    "expected_result": "..."
  }}
- "recommendation": {{
    "id": "user_rec_001",
    "issue_type": "user_suggestion",
    "column": "col_name or null",
    "affected_count": number,
    "affected_pct": float,
    "operation": "convert_date" | "fill_missing" | "convert_numeric" | "normalize_casing" | "remove_column" | "filter_rows",
    "recommended_strategy": "yyyy_mm_dd" | "median" | "titlecase" | etc,
    "available_strategies": ["yyyy_mm_dd", ...],
    "reason": "...",
    "risk_level": "low" | "medium" | "high",
    "expected_impact": "...",
    "recommended": true,
    "source": "user_requested"
  }}
"""
        if self._client:
            try:
                raw_response = self._call_gemini(prompt)
                parsed = self._extract_json(raw_response)
                if isinstance(parsed, dict) and "supported" in parsed:
                    return parsed
            except Exception as e:
                logger.error(f"Gemini API error during user suggestion analysis: {e}")

        return self._heuristic_analyze_user_suggestion(user_instruction, columns)

    def _heuristic_analyze_user_suggestion(self, instruction: str, columns: List[str]) -> Dict[str, Any]:
        inst_lower = instruction.lower()
        
        # Check if instruction is vague / unsupported
        if "magic" in inst_lower or "perfect" in inst_lower or "ai" in inst_lower and len(instruction.split()) < 4:
            return {
                "supported": False,
                "unsupported_reason": "I understand that you want to perform this operation, but this instruction is too vague. Supported operations include missing value handling, duplicate removal, numeric conversion, date formatting (YYYY/MM/DD), category normalization, outlier handling, column removal, and row filtering.",
                "interpretation": None,
                "recommendation": None
            }

        # Match column
        matched_col = None
        for col in columns:
            if col.lower() in inst_lower:
                matched_col = col
                break

        # Case 1: Date formatting (e.g. sale_date, YYYY/MM/DD)
        if "date" in inst_lower or "yyyy" in inst_lower or "format" in inst_lower:
            col = matched_col or ([c for c in columns if "date" in c.lower()] or [columns[0]])[0]
            rec_id = f"user_rec_{abs(hash(instruction)) % 1000:03d}"
            return {
                "supported": True,
                "unsupported_reason": None,
                "interpretation": {
                    "requested_action": f"Convert {col} to YYYY/MM/DD format",
                    "detected_column": col,
                    "current_format": "Mixed string/datetime",
                    "proposed_format": "YYYY/MM/DD",
                    "affected_rows": 50,
                    "risk_level": "low",
                    "expected_result": "Standardize dates to YYYY/MM/DD format (e.g., 2025-01-05 → 2025/01/05)"
                },
                "recommendation": {
                    "id": rec_id,
                    "issue_type": "user_suggestion",
                    "column": col,
                    "affected_count": 50,
                    "affected_pct": 100.0,
                    "operation": "convert_date",
                    "recommended_strategy": "yyyy_mm_dd",
                    "available_strategies": ["yyyy_mm_dd", "datetime"],
                    "reason": f"User requested date formatting on column '{col}' into YYYY/MM/DD.",
                    "risk_level": "low",
                    "expected_impact": f"Format dates in column '{col}' to YYYY/MM/DD",
                    "recommended": True,
                    "source": "user_requested"
                }
            }

        # Case 2: Negative quantity / row filtering
        if "negative" in inst_lower or "remove rows" in inst_lower or "less than" in inst_lower:
            col = matched_col or ([c for c in columns if "qty" in c.lower() or "quantity" in c.lower() or "price" in c.lower()] or [columns[0]])[0]
            rec_id = f"user_rec_{abs(hash(instruction)) % 1000:03d}"
            return {
                "supported": True,
                "unsupported_reason": None,
                "interpretation": {
                    "requested_action": f"Remove rows where {col} is negative or invalid",
                    "detected_column": col,
                    "current_format": "Numeric values",
                    "proposed_format": "Non-negative numeric values",
                    "affected_rows": 5,
                    "risk_level": "medium",
                    "expected_impact": f"Remove invalid negative records in {col}"
                },
                "recommendation": {
                    "id": rec_id,
                    "issue_type": "user_suggestion",
                    "column": col,
                    "affected_count": 5,
                    "affected_pct": 10.0,
                    "operation": "filter_rows",
                    "recommended_strategy": "remove_negative",
                    "available_strategies": ["remove_negative"],
                    "reason": f"User requested filtering out negative values in column '{col}'.",
                    "risk_level": "medium",
                    "expected_impact": f"Remove rows with negative values in '{col}'",
                    "recommended": True,
                    "source": "user_requested"
                }
            }

        # Case 3: Missing fill / replace with "Unknown" or custom
        if "missing" in inst_lower or "replace" in inst_lower or "unknown" in inst_lower:
            col = matched_col or columns[0]
            val = "Unknown"
            if "unknown" in inst_lower:
                val = "Unknown"
            rec_id = f"user_rec_{abs(hash(instruction)) % 1000:03d}"
            return {
                "supported": True,
                "unsupported_reason": None,
                "interpretation": {
                    "requested_action": f"Replace missing/null values in {col} with '{val}'",
                    "detected_column": col,
                    "current_format": "Contains missing values",
                    "proposed_format": f"Filled with '{val}'",
                    "affected_rows": 10,
                    "risk_level": "low",
                    "expected_result": f"Impute missing values in {col} with '{val}'"
                },
                "recommendation": {
                    "id": rec_id,
                    "issue_type": "user_suggestion",
                    "column": col,
                    "affected_count": 10,
                    "affected_pct": 15.0,
                    "operation": "fill_missing",
                    "recommended_strategy": "mode" if val == "Unknown" else "custom",
                    "available_strategies": ["mode", "unknown", "custom"],
                    "reason": f"User requested replacing missing values in '{col}' with '{val}'.",
                    "risk_level": "low",
                    "expected_impact": f"Fill missing values in column '{col}' with '{val}'",
                    "recommended": True,
                    "source": "user_requested"
                }
            }

        # Case 4: Title case / casing normalization
        if "title" in inst_lower or "casing" in inst_lower or "capitalize" in inst_lower or "city" in inst_lower:
            col = matched_col or ([c for c in columns if "city" in c.lower() or "category" in c.lower() or "name" in c.lower()] or [columns[0]])[0]
            rec_id = f"user_rec_{abs(hash(instruction)) % 1000:03d}"
            return {
                "supported": True,
                "unsupported_reason": None,
                "interpretation": {
                    "requested_action": f"Normalize capitalization in {col} to Title Case",
                    "detected_column": col,
                    "current_format": "Inconsistent casing",
                    "proposed_format": "Title Case",
                    "affected_rows": 20,
                    "risk_level": "low",
                    "expected_result": f"Standardize text casing in {col}"
                },
                "recommendation": {
                    "id": rec_id,
                    "issue_type": "user_suggestion",
                    "column": col,
                    "affected_count": 20,
                    "affected_pct": 30.0,
                    "operation": "normalize_casing",
                    "recommended_strategy": "titlecase",
                    "available_strategies": ["titlecase", "lowercase", "uppercase"],
                    "reason": f"User requested Title Case capitalization in column '{col}'.",
                    "risk_level": "low",
                    "expected_impact": f"Convert values in column '{col}' to Title Case",
                    "recommended": True,
                    "source": "user_requested"
                }
            }

        # Case 5: Remove column
        if "remove" in inst_lower and ("column" in inst_lower or matched_col is not None):
            col = matched_col or columns[0]
            rec_id = f"user_rec_{abs(hash(instruction)) % 1000:03d}"
            return {
                "supported": True,
                "unsupported_reason": None,
                "interpretation": {
                    "requested_action": f"Remove column {col} from dataset",
                    "detected_column": col,
                    "current_format": "Existing column",
                    "proposed_format": "Column deleted",
                    "affected_rows": 0,
                    "risk_level": "medium",
                    "expected_impact": f"Drop column {col} entirely"
                },
                "recommendation": {
                    "id": rec_id,
                    "issue_type": "user_suggestion",
                    "column": col,
                    "affected_count": 0,
                    "affected_pct": 0.0,
                    "operation": "remove_column",
                    "recommended_strategy": "delete",
                    "available_strategies": ["delete"],
                    "reason": f"User explicitly requested deleting column '{col}'.",
                    "risk_level": "medium",
                    "expected_impact": f"Drop column '{col}' from dataset",
                    "recommended": True,
                    "source": "user_requested"
                }
            }

        # General fallback if supported operation cannot be safely inferred
        return {
            "supported": False,
            "unsupported_reason": f"Could not map request '{instruction}' to a supported operation. Supported operations: Missing value handling, Duplicate removal, Numeric conversion, Date formatting (YYYY/MM/DD), Category normalization, Outlier handling, Column removal, Row filtering.",
            "interpretation": None,
            "recommendation": None
        }

    def analyze_post_clean_suggestion(
        self,
        user_instruction: str,
        columns: List[str],
        sample_data: List[Dict[str, Any]],
        column_unique_values: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """
        Analyzes post-preprocessing user instructions against the current cleaned dataset schema & values.
        Returns a structured recommendation dictionary for PostCleanSuggestionAnalysis.
        NEVER generates or executes arbitrary Python code.
        """
        inst_lower = user_instruction.lower().strip()

        # Rule 1: Security check - block code execution requests
        if any(kw in inst_lower for kw in ["run code", "python", "script", "eval(", "import ", "python code", "hack", "drop database", "system("]):
            return {
                "supported": False,
                "unsupported_reason": "This request cannot be executed directly. Please describe the preprocessing change you want to make in natural language.",
                "requested_change": None,
                "column": None,
                "operation": None,
                "mapping": None,
                "current_values": [],
                "proposed_values": [],
                "affected_rows": 0,
                "risk": "low",
                "reason": None,
                "expected_impact": None
            }

        # Rule 2: Column validation check
        # Search for column mentions in instruction
        matched_col = None
        for col in columns:
            col_l = col.lower()
            # Direct match or word match
            if col_l in inst_lower or any(w == col_l for w in re.findall(r'\b\w+\b', inst_lower)):
                matched_col = col
                break

        # Check if user named an explicit column that doesn't exist
        # E.g. "convert age_group to..." or "standardize gender values"
        for target_keyword in ["gender", "sex", "age_group", "salary", "account_type", "zip_code"]:
            if target_keyword in inst_lower and not any(target_keyword in c.lower() for c in columns):
                return {
                    "supported": False,
                    "unsupported_reason": f"Could not find a {target_keyword} column in the current dataset.",
                    "requested_change": None,
                    "column": None,
                    "operation": None,
                    "mapping": None,
                    "current_values": [],
                    "proposed_values": [],
                    "affected_rows": 0,
                    "risk": "low",
                    "reason": None,
                    "expected_impact": None
                }

        # If LLM client is available, attempt structured Gemini interpretation
        if self._client:
            prompt = f"""You are an AI Data Preparation Assistant specializing in post-preprocessing data standardization.
Dataset Schema Columns: {json.dumps(columns)}
Sample Categorical Values Per Column: {json.dumps(column_unique_values, default=str)}

User Request: "{user_instruction}"

Task:
Interpret the user request into a SAFE, structured preprocessing operation.

Allowed Operations:
1. "standardize_categorical_values": for replacing specific categorical values (e.g. M->Male, F->Female, 0->No, 1->Yes). Provide exact "mapping" dictionary.
2. "normalize_casing": for lowercasing, uppercasing, titlecasing strings. Specify strategy: "lowercase", "uppercase", or "titlecase".
3. "trim_whitespace": for removing leading/trailing spaces from text columns.
4. "convert_date": for date formatting. Strategy: "yyyy_mm_dd".
5. "convert_numeric": for parsing numeric strings into floats/integers.
6. "fill_missing": for filling missing values.
7. "remove_duplicates": for deduplication.
8. "remove_column": for dropping columns.
9. "filter_rows": for row removal.

Rules:
- DO NOT generate code.
- If requested column is not in columns list, set supported=false and unsupported_reason="Could not find column in dataset."
- If request is unsupported or unsafe, set supported=false.
- For "standardize_categorical_values", construct the complete "mapping" dictionary mapping existing raw values to clean target values.

Return ONLY a JSON object with:
- "supported": true/false
- "unsupported_reason": string or null
- "requested_change": brief 3-5 word title (e.g. "Standardize gender values")
- "column": exact column name from schema
- "operation": string operation code
- "strategy": string strategy code (if applicable)
- "mapping": JSON object of key-value pairs (e.g. {{"M": "Male", "F": "Female"}}) or null
- "reason": clear explanation of why this change is needed
- "risk": "low", "medium", or "high"
- "expected_impact": human-readable expected outcome
"""
            try:
                raw_res = self._call_gemini(prompt)
                parsed = self._extract_json(raw_res)
                if isinstance(parsed, dict) and "supported" in parsed:
                    if parsed.get("supported"):
                        col = parsed.get("column")
                        if col and col in columns:
                            uniq = column_unique_values.get(col, [])
                            mapping = parsed.get("mapping") or {}
                            
                            # Calculate current & proposed values and affected rows
                            current_vals = [str(v) for v in uniq if v is not None]
                            if mapping:
                                proposed_vals = list(dict.fromkeys([mapping.get(v, v) for v in current_vals]))
                            else:
                                proposed_vals = current_vals

                            return {
                                "supported": True,
                                "unsupported_reason": None,
                                "requested_change": parsed.get("requested_change", "Custom Preprocessing Operation"),
                                "column": col,
                                "operation": parsed.get("operation", "standardize_categorical_values"),
                                "mapping": mapping,
                                "strategy": parsed.get("strategy"),
                                "current_values": current_vals,
                                "proposed_values": proposed_vals,
                                "affected_rows": len([v for v in current_vals if v in mapping and mapping[v] != v]),
                                "risk": parsed.get("risk", "low"),
                                "reason": parsed.get("reason", f"User requested preprocessing on '{col}'."),
                                "expected_impact": parsed.get("expected_impact", f"Update values in column '{col}'.")
                            }
                        elif col and col not in columns:
                            return {
                                "supported": False,
                                "unsupported_reason": f"Could not find a '{col}' column in the current dataset.",
                                "requested_change": None, "column": None, "operation": None, "mapping": None,
                                "current_values": [], "proposed_values": [], "affected_rows": 0, "risk": "low", "reason": None, "expected_impact": None
                            }
                    else:
                        return {
                            "supported": False,
                            "unsupported_reason": parsed.get("unsupported_reason", "Unsupported instruction."),
                            "requested_change": None, "column": None, "operation": None, "mapping": None,
                            "current_values": [], "proposed_values": [], "affected_rows": 0, "risk": "low", "reason": None, "expected_impact": None
                        }
            except Exception as e:
                logger.error(f"Gemini LLM error during post-clean analysis: {e}")

        # Deterministic Heuristic Fallbacks (Ensures robust execution even if Gemini is rate limited)
        return self._heuristic_analyze_post_clean_suggestion(inst_lower, columns, column_unique_values)

    def _heuristic_analyze_post_clean_suggestion(
        self,
        inst_lower: str,
        columns: List[str],
        column_unique_values: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        # Case A: Gender standardization
        if "gender" in inst_lower or "male" in inst_lower or "female" in inst_lower or " m " in f" {inst_lower} " or " f " in f" {inst_lower} ":
            col = ([c for c in columns if "gender" in c.lower() or "sex" in c.lower()] or [None])[0]
            
            # Fallback: Check if any column contains 'm', 'f', 'male', or 'female' in unique values
            if not col:
                for c, uvals in column_unique_values.items():
                    str_vals = [str(v).strip().lower() for v in uvals if v is not None]
                    if any(v in ["m", "f", "male", "female"] for v in str_vals):
                        col = c
                        break

            if not col:
                return {
                    "supported": False,
                    "unsupported_reason": "Could not find a gender column in the current dataset.",
                    "requested_change": None, "column": None, "operation": None, "mapping": None,
                    "current_values": [], "proposed_values": [], "affected_rows": 0, "risk": "low", "reason": None, "expected_impact": None
                }

            current_raw = column_unique_values.get(col, [])
            current_vals = [str(v) for v in current_raw if v is not None and str(v).strip() != ""]

            # Map variations of M/F/Male/Female
            mapping = {}
            for v in current_vals:
                vl = v.strip().lower()
                if vl in ["m", "male", "man"]:
                    mapping[v] = "Male"
                elif vl in ["f", "female", "woman"]:
                    mapping[v] = "Female"
                else:
                    mapping[v] = v

            proposed_vals = list(dict.fromkeys([mapping.get(v, v) for v in current_vals]))
            affected_count = len([v for v in current_vals if v in mapping and mapping[v] != v])

            return {
                "supported": True,
                "unsupported_reason": None,
                "requested_change": "Standardize gender values",
                "column": col,
                "operation": "standardize_categorical_values",
                "mapping": mapping,
                "strategy": "categorical_standardization",
                "current_values": current_vals,
                "proposed_values": proposed_vals,
                "affected_rows": affected_count if affected_count > 0 else len(current_vals),
                "risk": "low",
                "reason": f"Multiple representations were detected in the {col} column (e.g. M/F vs Male/Female).",
                "expected_impact": f"All gender values in '{col}' will be standardized to Male or Female."
            }

        # Case B: Lowercase text
        if "lowercase" in inst_lower or "lower case" in inst_lower or "small letters" in inst_lower:
            col = None
            for c in columns:
                if c.lower() in inst_lower:
                    col = c
                    break
            if not col:
                # Default to first string column or account_type
                col = ([c for c in columns if "type" in c.lower() or "branch" in c.lower() or "category" in c.lower() or "status" in c.lower()] or columns[:1])[0]

            current_raw = column_unique_values.get(col, [])
            current_vals = [str(v) for v in current_raw if v is not None]
            proposed_vals = list(dict.fromkeys([v.lower() for v in current_vals]))

            return {
                "supported": True,
                "unsupported_reason": None,
                "requested_change": f"Convert {col} to lowercase",
                "column": col,
                "operation": "normalize_casing",
                "strategy": "lowercase",
                "mapping": None,
                "current_values": current_vals,
                "proposed_values": proposed_vals,
                "affected_rows": len([v for v in current_vals if v != v.lower()]),
                "risk": "low",
                "reason": f"User requested converting all text values in '{col}' to lowercase.",
                "expected_impact": f"All text values in column '{col}' will be lowercased."
            }

        # Case C: Uppercase text
        if "uppercase" in inst_lower or "upper case" in inst_lower or "capital letters" in inst_lower:
            col = None
            for c in columns:
                if c.lower() in inst_lower:
                    col = c
                    break
            if not col:
                col = columns[0]

            current_raw = column_unique_values.get(col, [])
            current_vals = [str(v) for v in current_raw if v is not None]
            proposed_vals = list(dict.fromkeys([v.upper() for v in current_vals]))

            return {
                "supported": True,
                "unsupported_reason": None,
                "requested_change": f"Convert {col} to uppercase",
                "column": col,
                "operation": "normalize_casing",
                "strategy": "uppercase",
                "mapping": None,
                "current_values": current_vals,
                "proposed_values": proposed_vals,
                "affected_rows": len([v for v in current_vals if v != v.upper()]),
                "risk": "low",
                "reason": f"User requested converting all text values in '{col}' to uppercase.",
                "expected_impact": f"All text values in column '{col}' will be uppercased."
            }

        # Case D: Trim spaces / extra spaces
        if "space" in inst_lower or "trim" in inst_lower or "strip" in inst_lower:
            col = None
            for c in columns:
                if c.lower() in inst_lower:
                    col = c
                    break
            if not col:
                col = ([c for c in columns if "branch" in c.lower() or "name" in c.lower()] or columns[:1])[0]

            current_raw = column_unique_values.get(col, [])
            current_vals = [str(v) for v in current_raw if v is not None]
            proposed_vals = list(dict.fromkeys([v.strip() for v in current_vals]))

            return {
                "supported": True,
                "unsupported_reason": None,
                "requested_change": f"Trim extra spaces in {col}",
                "column": col,
                "operation": "trim_whitespace",
                "strategy": "strip_spaces",
                "mapping": None,
                "current_values": current_vals,
                "proposed_values": proposed_vals,
                "affected_rows": len([v for v in current_vals if v != v.strip()]),
                "risk": "low",
                "reason": f"User requested removing leading and trailing spaces from '{col}'.",
                "expected_impact": f"Leading and trailing whitespace will be removed from '{col}'."
            }

        # Case E: Date formatting
        if "date" in inst_lower or "yyyy" in inst_lower or "format" in inst_lower:
            col = None
            for c in columns:
                if c.lower() in inst_lower:
                    col = c
                    break
            if not col:
                col = ([c for c in columns if "date" in c.lower()] or columns[:1])[0]

            current_raw = column_unique_values.get(col, [])
            current_vals = [str(v) for v in current_raw if v is not None]

            return {
                "supported": True,
                "unsupported_reason": None,
                "requested_change": f"Standardize date format in {col}",
                "column": col,
                "operation": "convert_date",
                "strategy": "yyyy_mm_dd",
                "mapping": None,
                "current_values": current_vals[:5],
                "proposed_values": ["YYYY/MM/DD formatted dates"],
                "affected_rows": len(current_vals),
                "risk": "low",
                "reason": f"User requested standardizing date format in '{col}' to YYYY/MM/DD.",
                "expected_impact": f"Dates in column '{col}' will be formatted consistently."
            }

        # Fallback if no supported pattern matched
        return {
            "supported": False,
            "unsupported_reason": f"Could not map request '{inst_lower}' to a supported operation. Supported operations include: categorical standardization, lowercasing/uppercasing, trimming spaces, date formatting, and missing value handling.",
            "requested_change": None, "column": None, "operation": None, "mapping": None,
            "current_values": [], "proposed_values": [], "affected_rows": 0, "risk": "low", "reason": None, "expected_impact": None
        }

gemini_service = GeminiService()


