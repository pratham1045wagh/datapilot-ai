import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Tuple
from app.models.cleaning_models import (
    UserActionApproval,
    CleaningRecommendation,
    PreviewImpactItem,
    CleaningHistoryItem,
    BeforeAfterComparison
)

logger = logging.getLogger("cleaning_service")

def execute_cleaning_pipeline(
    df_raw: pd.DataFrame,
    approvals: List[UserActionApproval],
    recommendations: List[CleaningRecommendation]
) -> Tuple[pd.DataFrame, List[CleaningHistoryItem], List[CleaningHistoryItem], List[BeforeAfterComparison]]:
    """
    Executes user-approved cleaning operations on a copy of the dataframe.
    Original raw DataFrame is preserved completely.
    """
    df = df_raw.copy()
    rec_dict = {r.id: r for r in recommendations}
    applied_history: List[CleaningHistoryItem] = []
    declined_history: List[CleaningHistoryItem] = []

    # Before metrics
    before_rows = len(df)
    before_cols = len(df.columns)
    before_duplicates = int(df.duplicated().sum())
    before_missing = int(df.isna().sum().sum())

    for action in approvals:
        rec = rec_dict.get(action.recommendation_id)
        if not rec:
            continue

        op = rec.operation
        col = rec.column
        strat = action.selected_strategy or rec.recommended_strategy or "default"

        if not action.approved:
            declined_history.append(CleaningHistoryItem(
                recommendation_id=rec.id,
                operation=op,
                column=col,
                strategy=strat,
                user_decision="declined",
                execution_status="skipped",
                details="User explicitly declined this recommended operation."
            ))
            continue

        # Execute approved operation
        status = "applied"
        details = ""
        try:
            if op == "remove_duplicates":
                count_before = len(df)
                df = df.drop_duplicates().reset_index(drop=True)
                removed = count_before - len(df)
                details = f"Removed {removed} exact duplicate row(s)."

            elif op == "fill_missing" and col in df.columns:
                # First sanitize invalid placeholders to NaN if present
                df[col] = df[col].replace({"not available": np.nan, "invalid-date": np.nan, "N/A": np.nan, "null": np.nan, "None": np.nan, "-": np.nan})
                missing_cnt = int(df[col].isna().sum())
                if missing_cnt > 0:
                    if strat == "mean" and pd.api.types.is_numeric_dtype(df[col]):
                        val = round(float(df[col].mean()), 2)
                        df[col] = df[col].fillna(val)
                        details = f"Filled {missing_cnt} missing value(s) in '{col}' using mean value ({val})."
                    elif strat == "median" and pd.api.types.is_numeric_dtype(df[col]):
                        val = round(float(df[col].median()), 2)
                        df[col] = df[col].fillna(val)
                        details = f"Filled {missing_cnt} missing value(s) in '{col}' using median value ({val})."
                    elif strat == "mode":
                        mode_vals = df[col].mode()
                        val = mode_vals.iloc[0] if not mode_vals.empty else "Unknown"
                        df[col] = df[col].fillna(val)
                        details = f"Filled {missing_cnt} missing value(s) in '{col}' using mode value ({val})."
                    elif strat == "remove_rows":
                        count_before = len(df)
                        df = df.dropna(subset=[col]).reset_index(drop=True)
                        removed = count_before - len(df)
                        details = f"Removed {removed} row(s) containing missing values in '{col}'."
                    elif strat == "custom" and action.custom_value is not None:
                        df[col] = df[col].fillna(action.custom_value)
                        details = f"Filled {missing_cnt} missing value(s) in '{col}' using custom value ({action.custom_value})."
                    else:  # unknown or string fallback
                        df[col] = df[col].fillna("Unknown")
                        details = f"Filled {missing_cnt} missing value(s) in '{col}' with 'Unknown'."

            elif op == "convert_numeric" and col in df.columns:
                cleaned_str = df[col].astype(str).str.replace(r"[\$,]", "", regex=True).str.strip()
                cleaned_str = cleaned_str.replace({"not available": np.nan, "invalid-date": np.nan, "N/A": np.nan, "null": np.nan, "-": np.nan})
                df[col] = pd.to_numeric(cleaned_str, errors="coerce")
                details = f"Converted column '{col}' to numeric float data type."

            elif op == "convert_date" and col in df.columns:
                sanitized_dates = df[col].astype(str).replace({"not available": np.nan, "invalid-date": np.nan, "N/A": np.nan, "null": np.nan, "-": np.nan})
                parsed_dt = pd.to_datetime(sanitized_dates, errors="coerce")
                if strat == "yyyy_mm_dd":
                    df[col] = parsed_dt.dt.strftime("%Y/%m/%d")
                    details = f"Formatted column '{col}' dates to YYYY/MM/DD representation."
                else:
                    df[col] = parsed_dt
                    details = f"Converted column '{col}' to datetime."

            elif op == "normalize_casing" and col in df.columns:
                if strat == "lowercase":
                    df[col] = df[col].astype(str).str.lower()
                elif strat == "uppercase":
                    df[col] = df[col].astype(str).str.upper()
                else:  # titlecase
                    df[col] = df[col].astype(str).str.title()
                details = f"Normalized string casing in column '{col}' to {strat}."

            elif op == "remove_outliers" and col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    non_nulls = df[col].dropna()
                    q25, q75 = np.percentile(non_nulls, 25), np.percentile(non_nulls, 75)
                    iqr = q75 - q25
                    if iqr > 0:
                        lower_b = q25 - 1.5 * iqr
                        upper_b = q75 + 1.5 * iqr
                        count_before = len(df)
                        df = df[(df[col].isna()) | ((df[col] >= lower_b) & (df[col] <= upper_b))].reset_index(drop=True)
                        removed = count_before - len(df)
                        details = f"Filtered out {removed} outlier row(s) outside IQR [{round(lower_b,2)}, {round(upper_b,2)}]."

            elif op in ("standardize_categorical_values", "replace_categorical") and col in df.columns:
                if hasattr(action, "mapping") and action.mapping:
                    df[col] = df[col].astype(str).replace(action.mapping)
                    details = f"Standardized categorical values in '{col}'."
                elif strat in ("titlecase", "lowercase", "uppercase"):
                    if strat == "lowercase":
                        df[col] = df[col].astype(str).str.lower()
                    elif strat == "uppercase":
                        df[col] = df[col].astype(str).str.upper()
                    else:
                        df[col] = df[col].astype(str).str.title()
                    details = f"Normalized values in '{col}' to {strat}."

            elif op == "trim_whitespace" and col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                details = f"Trimmed whitespace in '{col}'."

            elif op == "remove_column" and col in df.columns:
                df = df.drop(columns=[col])
                details = f"Dropped column '{col}' from dataset."

            elif op == "filter_rows" and col in df.columns:
                if strat == "remove_negative":
                    count_before = len(df)
                    if pd.api.types.is_numeric_dtype(df[col]):
                        df = df[(df[col].isna()) | (df[col] >= 0)].reset_index(drop=True)
                    removed = count_before - len(df)
                    details = f"Filtered out {removed} row(s) with negative values in '{col}'."

            applied_history.append(CleaningHistoryItem(
                recommendation_id=rec.id,
                operation=op,
                column=col,
                strategy=strat,
                user_decision="approved",
                execution_status=status,
                details=details,
                source=getattr(rec, "source", "ai_recommended")
            ))
        except Exception as e:
            logger.error(f"Error executing operation {op} on column {col}: {e}")
            applied_history.append(CleaningHistoryItem(
                recommendation_id=rec.id,
                operation=op,
                column=col,
                strategy=strat,
                user_decision="approved",
                execution_status="failed",
                details=f"Execution error: {str(e)}",
                source=getattr(rec, "source", "ai_recommended")
            ))

    # After metrics comparison
    after_rows = len(df)
    after_cols = len(df.columns)
    after_duplicates = int(df.duplicated().sum())
    after_missing = int(df.isna().sum().sum())

    comparisons = [
        BeforeAfterComparison(
            metric="Row Count",
            before=before_rows,
            after=after_rows,
            improvement=f"{before_rows - after_rows} rows removed" if before_rows != after_rows else "Unchanged"
        ),
        BeforeAfterComparison(
            metric="Duplicate Rows",
            before=before_duplicates,
            after=after_duplicates,
            improvement=f"Reduced by {before_duplicates - after_duplicates}" if before_duplicates > after_duplicates else "0 duplicates"
        ),
        BeforeAfterComparison(
            metric="Total Missing Values",
            before=before_missing,
            after=after_missing,
            improvement=f"Resolved {before_missing - after_missing} missing values" if before_missing > after_missing else "0 missing"
        )
    ]

    return df, applied_history, declined_history, comparisons

def generate_cleaning_preview(
    df: pd.DataFrame,
    approvals: List[UserActionApproval],
    recommendations: List[CleaningRecommendation]
) -> List[PreviewImpactItem]:
    """
    Simulates user-selected actions and generates preview of expected impact without mutating df.
    """
    rec_dict = {r.id: r for r in recommendations}
    previews: List[PreviewImpactItem] = []

    for action in approvals:
        if not action.approved:
            continue
        rec = rec_dict.get(action.recommendation_id)
        if not rec:
            continue

        op = rec.operation
        col = rec.column
        strat = action.selected_strategy or rec.recommended_strategy or "default"
        affected = rec.affected_count

        if op == "remove_duplicates":
            effect = f"Will remove {affected} duplicate row(s). Row count: {len(df)} ➔ {len(df) - affected}"
        elif op == "fill_missing":
            effect = f"Will fill {affected} missing values in '{col}' using strategy '{strat}'."
        elif op == "convert_numeric":
            effect = f"Will parse '{col}' strings into numeric numeric float data type."
        elif op == "normalize_casing":
            effect = f"Will standardize string casing variants in '{col}' to {strat}."
        elif op == "remove_outliers":
            effect = f"Will remove up to {affected} outlier row(s) based on 1.5x IQR rule."
        else:
            effect = f"Will execute {op} using strategy {strat}."

        previews.append(PreviewImpactItem(
            recommendation_id=rec.id,
            column=col,
            operation=op,
            strategy=strat,
            expected_effect=effect,
            affected_rows=affected
        ))

    return previews


def apply_single_post_clean_operation(
    df: pd.DataFrame,
    operation: str,
    column: Optional[str] = None,
    mapping: Optional[Dict[str, str]] = None,
    strategy: Optional[str] = None
) -> Tuple[pd.DataFrame, int, List[str], List[str], str]:
    """
    Applies a single user-approved post-preprocessing operation on a DataFrame copy.
    Returns (df_modified, affected_rows, before_values, after_values, details_string).
    """
    df = df.copy()
    affected_rows = 0
    before_values = []
    after_values = []
    details = ""

    if column and column in df.columns:
        before_values = [str(v) for v in df[column].dropna().unique()[:10]]

        if operation in ("standardize_categorical_values", "replace_categorical") and mapping:
            # Mask of items to be mapped
            orig_series = df[column].astype(str)
            mask = orig_series.isin(mapping.keys()) & (orig_series != orig_series.map(mapping))
            affected_rows = int(mask.sum())
            df[column] = df[column].astype(str).replace(mapping)
            details = f"Standardized categorical values in '{column}' using mapping."

        elif operation == "normalize_casing":
            orig = df[column].astype(str)
            if strategy == "lowercase":
                new_s = orig.str.lower()
                affected_rows = int((orig != new_s).sum())
                df[column] = new_s
                details = f"Converted values in '{column}' to lowercase."
            elif strategy == "uppercase":
                new_s = orig.str.upper()
                affected_rows = int((orig != new_s).sum())
                df[column] = new_s
                details = f"Converted values in '{column}' to uppercase."
            else:
                new_s = orig.str.title()
                affected_rows = int((orig != new_s).sum())
                df[column] = new_s
                details = f"Normalized values in '{column}' to Title Case."

        elif operation == "trim_whitespace":
            orig = df[column].astype(str)
            new_s = orig.str.strip()
            affected_rows = int((orig != new_s).sum())
            df[column] = new_s
            details = f"Trimmed leading and trailing whitespace from '{column}'."

        elif operation == "convert_date":
            sanitized = df[column].astype(str).replace({"not available": np.nan, "invalid-date": np.nan, "N/A": np.nan, "null": np.nan, "-": np.nan})
            parsed_dt = pd.to_datetime(sanitized, errors="coerce")
            df[column] = parsed_dt.dt.strftime("%Y/%m/%d")
            affected_rows = int(parsed_dt.notna().sum())
            details = f"Formatted dates in '{column}' to YYYY/MM/DD."

        after_values = [str(v) for v in df[column].dropna().unique()[:10]]
    elif operation == "remove_duplicates":
        before_cnt = len(df)
        df = df.drop_duplicates().reset_index(drop=True)
        affected_rows = before_cnt - len(df)
        details = f"Removed {affected_rows} duplicate rows."

    return df, affected_rows, before_values, after_values, details

