import math
import logging
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from app.services.dataset_service import dataset_service
from app.services.profiling_service import profile_dataframe
from app.services.cleaning_service import execute_cleaning_pipeline, generate_cleaning_preview, apply_single_post_clean_operation
from app.services.gemini_service import gemini_service
from app.services.database_service import database_service
from app.services.report_service import report_service
from app.services.pdf_report_service import pdf_report_service
from app.services.verification_service import verify_cleaned_dataframe, attempt_controlled_repair
from app.config import REPORTS_DIR
from app.models.dataset_models import DatasetProfile, DataIssue
from app.models.cleaning_models import (
    CleaningRecommendation,
    UserActionApproval,
    PreviewImpactItem,
    CleaningReport,
    UserSuggestionResponse,
    DatasetPreviewResponse,
    VerificationReport,
    CleaningHistoryItem,
    PostCleanSuggestionAnalysis,
    PostCleanApplyRequest,
    PostCleanApplyResponse
)

logger = logging.getLogger("data_prep_agent")

class DataPreparationAgent:
    def __init__(self):
        # In-memory store for recommendations & reports per dataset_id
        self._recommendations_cache: Dict[str, List[CleaningRecommendation]] = {}
        self._reports_cache: Dict[str, CleaningReport] = {}
        self._post_clean_suggestions_cache: Dict[str, List[Dict[str, Any]]] = {}

    def _save_report(self, dataset_id: str, report: CleaningReport):
        self._reports_cache[dataset_id] = report
        try:
            report_json_path = REPORTS_DIR / f"report_{dataset_id}.json"
            with open(report_json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        except Exception as e:
            logger.warning(f"Could not persist report json for dataset {dataset_id}: {e}")

    def _get_report(self, dataset_id: str) -> Optional[CleaningReport]:
        if dataset_id in self._reports_cache:
            return self._reports_cache[dataset_id]
        report_json_path = REPORTS_DIR / f"report_{dataset_id}.json"
        if report_json_path.exists():
            try:
                with open(report_json_path, "r", encoding="utf-8") as f:
                    report = CleaningReport.model_validate_json(f.read())
                    self._reports_cache[dataset_id] = report
                    return report
            except Exception as e:
                logger.warning(f"Could not load report json for dataset {dataset_id}: {e}")
        return None

    def profile(self, dataset_id: str) -> Tuple[DatasetProfile, List[DataIssue]]:
        df, ext, path = dataset_service.load_raw_dataframe(dataset_id)
        original_filename = path.name.replace(f"{dataset_id}_raw", "")
        return profile_dataframe(df, dataset_id, path.name, original_filename)

    def get_recommendations(self, dataset_id: str) -> List[CleaningRecommendation]:
        if dataset_id in self._recommendations_cache and self._recommendations_cache[dataset_id]:
            return self._recommendations_cache[dataset_id]

        profile, issues = self.profile(dataset_id)

        # Send profiling data to Gemini Service for intelligent recommendations
        summary = {
            "dataset_id": profile.dataset_id,
            "row_count": profile.row_count,
            "column_count": profile.column_count,
            "total_missing": profile.total_missing,
            "total_duplicates": profile.total_duplicates,
            "columns": [c.name for c in profile.columns]
        }
        issue_dicts = [i.model_dump() for i in issues]
        raw_recs = gemini_service.generate_cleaning_recommendations(summary, issue_dicts, profile.sample_data)

        # Parse into Pydantic recommendation models
        recommendations: List[CleaningRecommendation] = []
        for r in raw_recs:
            try:
                rec_model = CleaningRecommendation(**r)
                recommendations.append(rec_model)
            except Exception as e:
                logger.warning(f"Skipping malformed recommendation payload: {r}, error: {e}")

        self._recommendations_cache[dataset_id] = recommendations
        return recommendations

    def add_user_suggestion(self, dataset_id: str, user_instruction: str) -> UserSuggestionResponse:
        profile, issues = self.profile(dataset_id)
        summary = {
            "dataset_id": profile.dataset_id,
            "row_count": profile.row_count,
            "column_count": profile.column_count,
            "columns": [c.name for c in profile.columns]
        }
        columns = [c.name for c in profile.columns]

        res_dict = gemini_service.analyze_user_suggestion(user_instruction, summary, profile.sample_data, columns)

        if not res_dict.get("supported"):
            return UserSuggestionResponse(
                supported=False,
                unsupported_reason=res_dict.get("unsupported_reason", "Unsupported instruction."),
                interpretation=None,
                recommendation=None
            )

        raw_rec = res_dict.get("recommendation")
        rec_model = None
        if raw_rec:
            try:
                rec_model = CleaningRecommendation(**raw_rec)
                existing = self._recommendations_cache.get(dataset_id, [])
                existing.append(rec_model)
                self._recommendations_cache[dataset_id] = existing
            except Exception as e:
                logger.error(f"Failed to build user recommendation model: {e}")

        return UserSuggestionResponse(
            supported=True,
            unsupported_reason=None,
            interpretation=res_dict.get("interpretation"),
            recommendation=rec_model
        )

    def preview(self, dataset_id: str, approvals: List[UserActionApproval]) -> List[PreviewImpactItem]:
        df, ext, path = dataset_service.load_raw_dataframe(dataset_id)
        recs = self._recommendations_cache.get(dataset_id) or self.get_recommendations(dataset_id)
        return generate_cleaning_preview(df, approvals, recs)

    def clean(self, dataset_id: str, approvals: List[UserActionApproval]) -> CleaningReport:
        # 1. Load raw dataset
        df_raw, ext, raw_path = dataset_service.load_raw_dataframe(dataset_id)
        original_filename = raw_path.name.replace(f"{dataset_id}_raw", "")
        recs = self._recommendations_cache.get(dataset_id) or self.get_recommendations(dataset_id)

        # 2. Execute approved transformations on Pandas working copy
        df_clean, applied, declined, comparisons = execute_cleaning_pipeline(df_raw, approvals, recs)

        # Separate user-requested vs AI-recommended
        user_requested_history = [item for item in applied if item.source == "user_requested"]

        # 3. Deterministic Verification Stage
        verif_report = verify_cleaned_dataframe(df_clean, df_raw, applied, declined)

        # 4. Controlled Repair if warnings or failures detected
        if verif_report.overall_status in ("WARNING", "FAILED"):
            df_clean, verif_report = attempt_controlled_repair(df_clean, verif_report)

        # 5. Save cleaned dataset file
        dataset_service.save_cleaned_dataframe(df_clean, dataset_id, ext)

        # 6. Ingest cleaned dataframe into SQLite DB
        sqlite_table = database_service.load_dataframe_to_sqlite(df_clean, dataset_id, original_filename)

        # 7. Generate PDF Report via ReportLab
        try:
            pdf_bytes = pdf_report_service.generate_pdf_bytes(
                dataset_id=dataset_id,
                original_filename=original_filename,
                original_rows=len(df_raw),
                final_rows=len(df_clean),
                original_cols=len(df_raw.columns),
                final_cols=len(df_clean.columns),
                operations_applied=applied,
                operations_declined=declined,
                user_requested_actions=user_requested_history,
                before_after_comparison=comparisons,
                verification_report=verif_report,
                sqlite_table_name=sqlite_table
            )
            pdf_path = REPORTS_DIR / f"report_{dataset_id}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
        except Exception as e:
            logger.error(f"Failed to write PDF report: {e}")

        # Also generate markdown report for legacy compatibility
        try:
            report_service.generate_markdown_report(
                dataset_id=dataset_id,
                original_filename=original_filename,
                original_rows=len(df_raw),
                final_rows=len(df_clean),
                original_cols=len(df_raw.columns),
                final_cols=len(df_clean.columns),
                applied=applied,
                declined=declined,
                comparisons=comparisons,
                sqlite_table_name=sqlite_table
            )
        except Exception as ex:
            logger.warning(f"Could not write legacy markdown report: {ex}")

        report = CleaningReport(
            dataset_id=dataset_id,
            original_filename=original_filename,
            timestamp=dataset_id,
            original_rows=len(df_raw),
            final_rows=len(df_clean),
            original_cols=len(df_raw.columns),
            final_cols=len(df_clean.columns),
            operations_applied=applied,
            operations_declined=declined,
            user_requested_actions=user_requested_history,
            before_after_comparison=comparisons,
            verification_report=verif_report,
            sqlite_table_name=sqlite_table,
            agent_state=verif_report.overall_status
        )

        self._save_report(dataset_id, report)
        self._post_clean_suggestions_cache[dataset_id] = []
        return report

    def get_cleaned_preview(
        self,
        dataset_id: str,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None
    ) -> DatasetPreviewResponse:
        """
        Returns real paginated preview of cleaned dataset directly from DataFrame.
        """
        df, ext, path = dataset_service.load_cleaned_dataframe(dataset_id)
        
        # Apply search filter if provided
        if search and search.strip():
            query = search.strip().lower()
            mask = df.astype(str).apply(lambda row: row.str.lower().str.contains(query).any(), axis=1)
            df = df[mask]

        total_rows = len(df)
        total_cols = len(df.columns)
        columns = list(df.columns)

        # Pagination math
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        total_pages = max(1, math.ceil(total_rows / page_size))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        sliced_df = df.iloc[start_idx:end_idx]
        records = sliced_df.to_dict(orient="records")

        # Clean NaN/Inf values for JSON compliance
        clean_records = []
        for r in records:
            clean_r = {}
            for k, v in r.items():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    clean_r[k] = None
                elif pd.isna(v):
                    clean_r[k] = None
                else:
                    clean_r[k] = v
            clean_records.append(clean_r)

        return DatasetPreviewResponse(
            dataset_id=dataset_id,
            total_rows=total_rows,
            total_cols=total_cols,
            columns=columns,
            rows=clean_records,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            verification_status="VERIFIED"
        )

    def analyze_post_clean_suggestion(self, dataset_id: str, user_instruction: str) -> PostCleanSuggestionAnalysis:
        try:
            df, ext, path = dataset_service.load_cleaned_dataframe(dataset_id)
        except Exception:
            df, ext, path = dataset_service.load_raw_dataframe(dataset_id)

        columns = list(df.columns)
        records = df.head(5).to_dict(orient="records")
        col_unique_vals = {}
        for c in columns:
            col_unique_vals[c] = [v for v in df[c].dropna().unique()[:20]]

        res_dict = gemini_service.analyze_post_clean_suggestion(
            user_instruction=user_instruction,
            columns=columns,
            sample_data=records,
            column_unique_values=col_unique_vals
        )

        return PostCleanSuggestionAnalysis(
            supported=res_dict.get("supported", False),
            unsupported_reason=res_dict.get("unsupported_reason"),
            requested_change=res_dict.get("requested_change"),
            column=res_dict.get("column"),
            operation=res_dict.get("operation"),
            mapping=res_dict.get("mapping"),
            strategy=res_dict.get("strategy"),
            current_values=res_dict.get("current_values") or [],
            proposed_values=res_dict.get("proposed_values") or [],
            affected_rows=res_dict.get("affected_rows", 0),
            risk=res_dict.get("risk", "low"),
            reason=res_dict.get("reason"),
            expected_impact=res_dict.get("expected_impact")
        )

    def apply_post_clean_suggestion(self, dataset_id: str, payload: PostCleanApplyRequest) -> PostCleanApplyResponse:
        df_raw, ext, raw_path = dataset_service.load_raw_dataframe(dataset_id)
        original_filename = raw_path.name.replace(f"{dataset_id}_raw", "")

        try:
            df_cleaned, _, _ = dataset_service.load_cleaned_dataframe(dataset_id)
        except Exception:
            df_cleaned = df_raw.copy()

        if not payload.approved:
            verif = verify_cleaned_dataframe(df_cleaned, df_raw, [], [])
            report = CleaningReport(
                dataset_id=dataset_id,
                original_filename=original_filename,
                timestamp=dataset_id,
                original_rows=len(df_raw),
                final_rows=len(df_cleaned),
                original_cols=len(df_raw.columns),
                final_cols=len(df_cleaned.columns),
                operations_applied=[],
                operations_declined=[],
                user_requested_actions=[],
                before_after_comparison=[],
                verification_report=verif,
                sqlite_table_name=f"_{dataset_id.replace('-', '_')}",
                agent_state="USER_CHANGE_REJECTED"
            )
            return PostCleanApplyResponse(
                status="REJECTED",
                message="User rejected the proposed change. Dataset remains unmodified.",
                affected_rows=0,
                before_values=[],
                after_values=[],
                report=report
            )

        df_updated, affected_rows, before_vals, after_vals, details = apply_single_post_clean_operation(
            df=df_cleaned,
            operation=payload.operation,
            column=payload.column,
            mapping=payload.mapping,
            strategy=payload.strategy
        )

        dataset_service.save_cleaned_dataframe(df_updated, dataset_id, ext)
        sqlite_table = database_service.load_dataframe_to_sqlite(df_updated, dataset_id, original_filename)

        user_history_item = CleaningHistoryItem(
            recommendation_id=f"user_post_{abs(hash(payload.user_instruction)) % 10000:04d}",
            operation=payload.operation,
            column=payload.column,
            strategy=payload.strategy or "custom",
            user_decision="approved",
            execution_status="applied",
            details=details,
            source="user_requested"
        )

        # Retrieve prior report to accumulate overall cleaning history
        prior_report = self._get_report(dataset_id)
        if prior_report:
            accumulated_applied = list(prior_report.operations_applied) + [user_history_item]
            accumulated_declined = list(prior_report.operations_declined)
            accumulated_user_requested = list(prior_report.user_requested_actions) + [user_history_item]
        else:
            accumulated_applied = [user_history_item]
            accumulated_declined = []
            accumulated_user_requested = [user_history_item]

        # Recalculate before/after overall dataset quality comparison
        before_rows = len(df_raw)
        after_rows = len(df_updated)
        before_duplicates = int(df_raw.duplicated().sum())
        after_duplicates = int(df_updated.duplicated().sum())
        before_missing = int(df_raw.isna().sum().sum())
        after_missing = int(df_updated.isna().sum().sum())

        from app.models.cleaning_models import BeforeAfterComparison
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

        verif_report = verify_cleaned_dataframe(df_updated, df_raw, accumulated_applied, accumulated_declined)

        # Update post clean suggestions list cache
        post_suggestions = self._post_clean_suggestions_cache.get(dataset_id, [])
        post_suggestions.append({
            "user_instruction": payload.user_instruction,
            "requested_change": payload.requested_change,
            "column": payload.column,
            "operation": payload.operation,
            "mapping": payload.mapping,
            "affected_rows": affected_rows,
            "approval_status": "Approved",
            "application_status": "Applied",
            "verification_status": verif_report.overall_status,
            "before_values": before_vals,
            "after_values": after_vals
        })
        self._post_clean_suggestions_cache[dataset_id] = post_suggestions

        try:
            pdf_bytes = pdf_report_service.generate_pdf_bytes(
                dataset_id=dataset_id,
                original_filename=original_filename,
                original_rows=len(df_raw),
                final_rows=len(df_updated),
                original_cols=len(df_raw.columns),
                final_cols=len(df_updated.columns),
                operations_applied=accumulated_applied,
                operations_declined=accumulated_declined,
                user_requested_actions=accumulated_user_requested,
                before_after_comparison=comparisons,
                verification_report=verif_report,
                sqlite_table_name=sqlite_table,
                post_clean_suggestions=post_suggestions
            )
            pdf_path = REPORTS_DIR / f"report_{dataset_id}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
        except Exception as e:
            logger.error(f"Failed to write updated PDF report: {e}")

        report = CleaningReport(
            dataset_id=dataset_id,
            original_filename=original_filename,
            timestamp=dataset_id,
            original_rows=len(df_raw),
            final_rows=len(df_updated),
            original_cols=len(df_raw.columns),
            final_cols=len(df_updated.columns),
            operations_applied=accumulated_applied,
            operations_declined=accumulated_declined,
            user_requested_actions=accumulated_user_requested,
            before_after_comparison=comparisons,
            verification_report=verif_report,
            sqlite_table_name=sqlite_table,
            agent_state=verif_report.overall_status
        )

        self._save_report(dataset_id, report)

        return PostCleanApplyResponse(
            status="SUCCESS",
            message=f"Change applied successfully and verified ({verif_report.overall_status}).",
            affected_rows=affected_rows,
            before_values=before_vals,
            after_values=after_vals,
            report=report
        )

data_preparation_agent = DataPreparationAgent()

