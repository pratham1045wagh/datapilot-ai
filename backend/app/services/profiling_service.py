import pandas as pd
import numpy as np
import math
from typing import List, Dict, Any, Tuple
from app.models.dataset_models import DatasetProfile, ColumnProfile, DataIssue

INVALID_STRINGS = {"not available", "invalid-date", "n/a", "na", "-", "null", "none", "unknown", "undefined", "invalid"}

def profile_dataframe(df: pd.DataFrame, dataset_id: str, filename: str, original_filename: str) -> Tuple[DatasetProfile, List[DataIssue]]:
    """
    Profiles a pandas DataFrame without mutating it.
    Returns (DatasetProfile, List[DataIssue]).
    """
    row_count, col_count = df.shape
    total_duplicates = int(df.duplicated().sum())
    total_missing = int(df.isna().sum().sum())
    memory_kb = float(df.memory_usage(deep=True).sum() / 1024.0)

    column_profiles: List[ColumnProfile] = []
    issues: List[DataIssue] = []

    # 1. Check dataset-level duplicates issue
    if total_duplicates > 0:
        dup_pct = round((total_duplicates / max(1, row_count)) * 100, 2)
        issues.append(DataIssue(
            issue_type="duplicates",
            column=None,
            affected_count=total_duplicates,
            affected_pct=dup_pct,
            severity="Low" if dup_pct < 5.0 else "Medium",
            explanation=f"Found {total_duplicates} exact duplicate rows ({dup_pct}% of dataset).",
            recommended_action="Remove exact duplicate rows.",
            risk_level="low"
        ))

    # 2. Inspect each column
    for col in df.columns:
        series = df[col]
        dtype_str = str(series.dtype)
        col_total = len(series)
        col_missing = int(series.isna().sum())
        missing_pct = round((col_missing / max(1, col_total)) * 100, 2)
        unique_cnt = int(series.nunique(dropna=True))
        sample_vals = series.dropna().unique()[:5].tolist()
        # Clean samples for JSON compliance
        sample_vals_clean = [v if not (isinstance(v, float) and math.isnan(v)) else None for v in sample_vals]

        num_stats = None
        outlier_cnt = 0
        inconsistent_vars = None

        # Check missing values issue
        if col_missing > 0:
            severity = "High" if missing_pct > 20.0 else "Medium" if missing_pct > 2.0 else "Low"
            issues.append(DataIssue(
                issue_type="missing_values",
                column=col,
                affected_count=col_missing,
                affected_pct=missing_pct,
                severity=severity,
                explanation=f"Column '{col}' contains {col_missing} missing values ({missing_pct}%).",
                recommended_action="Impute missing values or remove missing rows.",
                risk_level="medium"
            ))

        # Check if numeric
        if pd.api.types.is_numeric_dtype(series):
            non_nulls = series.dropna()
            if len(non_nulls) > 0:
                num_stats = {
                    "min": float(non_nulls.min()),
                    "max": float(non_nulls.max()),
                    "mean": round(float(non_nulls.mean()), 2),
                    "median": round(float(non_nulls.median()), 2),
                    "std": round(float(non_nulls.std()), 2) if len(non_nulls) > 1 else 0.0
                }
                # IQR outlier check
                q25, q75 = np.percentile(non_nulls, 25), np.percentile(non_nulls, 75)
                iqr = q75 - q25
                if iqr > 0:
                    lower_bound = q25 - 1.5 * iqr
                    upper_bound = q75 + 1.5 * iqr
                    outliers = non_nulls[(non_nulls < lower_bound) | (non_nulls > upper_bound)]
                    outlier_cnt = len(outliers)
                    if outlier_cnt > 0:
                        outlier_pct = round((outlier_cnt / len(non_nulls)) * 100, 2)
                        issues.append(DataIssue(
                            issue_type="outliers",
                            column=col,
                            affected_count=outlier_cnt,
                            affected_pct=outlier_pct,
                            severity="Medium" if outlier_pct < 5.0 else "High",
                            explanation=f"Column '{col}' has {outlier_cnt} potential outliers outside IQR range [{round(lower_bound, 2)}, {round(upper_bound, 2)}].",
                            recommended_action="Review before removal. Outliers must never be deleted silently.",
                            risk_level="high"
                        ))
        else:
            # Check string columns for text-encoded numbers, invalid strings, or casing inconsistencies
            non_nulls_str = series.dropna().astype(str).str.strip()
            if len(non_nulls_str) > 0:
                # Check for explicit invalid placeholders ("not available", "invalid-date", etc.)
                invalid_matches = non_nulls_str[non_nulls_str.str.lower().isin(INVALID_STRINGS)]
                invalid_cnt = len(invalid_matches)
                if invalid_cnt > 0:
                    invalid_pct = round((invalid_cnt / len(non_nulls_str)) * 100, 2)
                    issues.append(DataIssue(
                        issue_type="invalid_values",
                        column=col,
                        affected_count=invalid_cnt,
                        affected_pct=invalid_pct,
                        severity="High" if invalid_pct > 10.0 else "Medium",
                        explanation=f"Column '{col}' contains {invalid_cnt} invalid/placeholder string values (e.g., '{invalid_matches.iloc[0]}').",
                        recommended_action="Convert invalid strings to missing/null or parse correctly.",
                        risk_level="medium"
                    ))

                # Test numeric conversion
                cleaned_numeric = non_nulls_str.str.replace(r"[\$,]", "", regex=True)
                numeric_converted = pd.to_numeric(cleaned_numeric, errors="coerce")
                valid_num_cnt = numeric_converted.notna().sum()
                if valid_num_cnt > 0 and valid_num_cnt / len(non_nulls_str) > 0.6:
                    num_pct = round((valid_num_cnt / len(non_nulls_str)) * 100, 2)
                    issues.append(DataIssue(
                        issue_type="text_as_numeric",
                        column=col,
                        affected_count=int(valid_num_cnt),
                        affected_pct=num_pct,
                        severity="Low",
                        explanation=f"Column '{col}' is stored as string but {valid_num_cnt} values appear to be numeric.",
                        recommended_action="Convert string column to numeric float/int data type.",
                        risk_level="low"
                    ))

                # Test capitalization variants (e.g. mumbai vs MUMBAI vs Mumbai)
                lower_map = {}
                for val in non_nulls_str.unique():
                    low = val.lower()
                    if low not in lower_map:
                        lower_map[low] = []
                    lower_map[low].append(val)
                
                variants = [vals for vals in lower_map.values() if len(vals) > 1]
                if len(variants) > 0:
                    flattened_variants = [v for grp in variants for v in grp]
                    inconsistent_vars = flattened_variants[:6]
                    var_cnt = len(flattened_variants)
                    issues.append(DataIssue(
                        issue_type="casing_inconsistency",
                        column=col,
                        affected_count=var_cnt,
                        affected_pct=round((var_cnt / len(non_nulls_str)) * 100, 2),
                        severity="Low",
                        explanation=f"Column '{col}' contains inconsistent capitalization variants: {', '.join(inconsistent_vars[:4])}.",
                        recommended_action="Normalize capitalization variants (Title Case / Lowercase).",
                        risk_level="low"
                    ))

        column_profiles.append(ColumnProfile(
            name=col,
            data_type=dtype_str,
            total_count=col_total,
            missing_count=col_missing,
            missing_pct=missing_pct,
            unique_count=unique_cnt,
            sample_values=sample_vals_clean,
            numeric_stats=num_stats,
            outlier_count=outlier_cnt,
            inconsistent_variants=inconsistent_vars
        ))

    # Sample rows formatted as dictionary list
    records = df.head(10).to_dict(orient="records")
    # Clean NaNs in records
    clean_records = []
    for r in records:
        clean_r = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
        clean_records.append(clean_r)

    profile = DatasetProfile(
        dataset_id=dataset_id,
        filename=filename,
        original_filename=original_filename,
        row_count=row_count,
        column_count=col_count,
        total_missing=total_missing,
        total_duplicates=total_duplicates,
        memory_kb=round(memory_kb, 2),
        columns=column_profiles,
        sample_data=clean_records
    )

    return profile, issues
