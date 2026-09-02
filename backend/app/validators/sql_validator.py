import re
from typing import Tuple, Optional, List

FORBIDDEN_KEYWORDS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bCREATE\b",
    r"\bREPLACE\b",
    r"\bEXEC\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
]

def validate_read_only_sql(sql: str, valid_columns: Optional[List[str]] = None) -> Tuple[bool, str]:
    """
    Validates that a SQL query is read-only and safe to execute.
    Returns (is_valid, error_message).
    """
    if not sql or not sql.strip():
        return False, "SQL query is empty."

    # Strip surrounding whitespace and markdown code block delimiters if present
    clean_sql = re.sub(r"^```sql\s*", "", sql.strip(), flags=re.IGNORECASE)
    clean_sql = re.sub(r"^```\s*", "", clean_sql)
    clean_sql = re.sub(r"\s*```$", "", clean_sql).strip()

    # Check for forbidden keywords (case-insensitive)
    for pattern in FORBIDDEN_KEYWORDS:
        if re.search(pattern, clean_sql, re.IGNORECASE):
            match = re.search(pattern, clean_sql, re.IGNORECASE).group(0)
            return False, f"Forbidden SQL keyword detected: '{match}'. Only read-only SELECT queries are allowed."

    # Check that query starts with SELECT or WITH
    upper_sql = clean_sql.upper()
    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        return False, "Query must start with 'SELECT' or 'WITH'."

    # Check for multiple statements separated by semicolon
    # Ignore trailing semicolon
    statements = [stmt.strip() for stmt in clean_sql.rstrip(";").split(";") if stmt.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements detected. Only a single query is allowed."

    return True, ""

def sanitize_sql(sql: str) -> str:
    """Clean markdown syntax and normalize semicolon endings."""
    clean_sql = re.sub(r"^```sql\s*", "", sql.strip(), flags=re.IGNORECASE)
    clean_sql = re.sub(r"^```\s*", "", clean_sql)
    clean_sql = re.sub(r"\s*```$", "", clean_sql).strip()
    if not clean_sql.endswith(";"):
        clean_sql += ";"
    return clean_sql
