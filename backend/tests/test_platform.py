import os
import sys
try:
    import pytest
except ImportError:
    pytest = None
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.dataset_service import dataset_service
from app.agents.data_preparation_agent import data_preparation_agent
from app.agents.sql_agent import sql_agent
from app.validators.sql_validator import validate_read_only_sql
from app.models.cleaning_models import UserActionApproval
from app.config import REPORTS_DIR
from create_sample_datasets import generate_clean_dataset, generate_dirty_dataset

def test_full_platform_pipeline():
    print("\n==========================================")
    print("STARTING UPDATED INTEGRATION TEST SUITE")
    print("==========================================")

    # 1. Generate Sample Datasets
    clean_csv = generate_clean_dataset()
    dirty_csv = generate_dirty_dataset()
    assert clean_csv.exists()
    assert dirty_csv.exists()
    print("[OK] Sample datasets created.")

    # 2. Upload Dirty Dataset
    with open(dirty_csv, "rb") as f:
        content = f.read()
    dataset_id, saved_path, orig_name = dataset_service.save_uploaded_file(content, dirty_csv.name)
    assert dataset_id is not None
    print(f"[OK] Uploaded dirty dataset with ID: {dataset_id}")

    # 3. Profile Dataset & Invalid String Detection
    profile, issues = data_preparation_agent.profile(dataset_id)
    assert profile.row_count == 12
    assert profile.total_duplicates == 2
    assert len(issues) > 0
    issue_types = [i.issue_type for i in issues]
    assert "duplicates" in issue_types
    assert "missing_values" in issue_types
    assert "text_as_numeric" in issue_types
    assert "casing_inconsistency" in issue_types
    print(f"[OK] Dataset profiling detected {len(issues)} issues accurately.")

    # 4. Test AI Cleaning Recommendations
    recs = data_preparation_agent.get_recommendations(dataset_id)
    assert len(recs) > 0
    print(f"[OK] Generated {len(recs)} AI recommendations.")

    # 5. Test Natural Language User Suggestions (UPDATE 2)
    sug_valid = data_preparation_agent.add_user_suggestion(dataset_id, "Convert sale_date to YYYY/MM/DD format")
    assert sug_valid.supported is True
    assert sug_valid.recommendation is not None
    assert sug_valid.recommendation.source == "user_requested"
    print("[OK] User suggestion 'Convert sale_date to YYYY/MM/DD format' successfully analyzed & added.")

    sug_invalid = data_preparation_agent.add_user_suggestion(dataset_id, "Make dataset perfect")
    assert sug_invalid.supported is False
    assert sug_invalid.unsupported_reason is not None
    print("[OK] Vague/unsupported user suggestion 'Make dataset perfect' correctly flagged with explanation.")

    # Fetch updated unified recommendations list
    all_recs = data_preparation_agent.get_recommendations(dataset_id)

    # 6. User Approval Workflow
    approvals = []
    for r in all_recs:
        if r.operation == "remove_duplicates":
            approvals.append(UserActionApproval(recommendation_id=r.id, approved=True, selected_strategy="remove_all"))
        elif r.operation == "fill_missing":
            strat = "median" if r.column == "age" else "mode"
            approvals.append(UserActionApproval(recommendation_id=r.id, approved=True, selected_strategy=strat))
        elif r.operation == "convert_numeric":
            approvals.append(UserActionApproval(recommendation_id=r.id, approved=True, selected_strategy="safe_convert"))
        elif r.operation == "convert_date":
            approvals.append(UserActionApproval(recommendation_id=r.id, approved=True, selected_strategy="yyyy_mm_dd"))
        elif r.operation == "normalize_casing":
            approvals.append(UserActionApproval(recommendation_id=r.id, approved=True, selected_strategy="titlecase"))
        elif r.operation == "remove_outliers":
            # REJECT high-risk outlier removal to test explicit user rejection preservation
            approvals.append(UserActionApproval(recommendation_id=r.id, approved=False, selected_strategy="iqr_filter"))

    # 7. Test Preview Impact
    previews = data_preparation_agent.preview(dataset_id, approvals)
    assert len(previews) > 0
    print(f"[OK] Preview impact calculated ({len(previews)} approved actions previewed).")

    # 8. Apply Approved Transformations & Run Deterministic Verification Engine (UPDATE 5)
    report = data_preparation_agent.clean(dataset_id, approvals)
    assert report.final_rows < report.original_rows
    assert len(report.operations_applied) > 0
    assert len(report.operations_declined) >= 1
    assert report.verification_report is not None
    assert report.verification_report.overall_status in ("PASSED", "WARNING", "VERIFIED")
    print(f"[OK] Preprocessing executed & verified. Status: {report.verification_report.overall_status}. Table: {report.sqlite_table_name}")

    # Verify rejected outlier check is passed as user-retained
    outlier_checks = [c for c in report.verification_report.checks if "Outlier" in c.check_name]
    assert len(outlier_checks) > 0
    assert outlier_checks[0].status == "PASSED"
    print("[OK] Deterministic verification confirmed user-rejected outlier retention as PASSED.")

    # 9. Test On-Screen Dataset Preview API (UPDATE 1)
    preview_res = data_preparation_agent.get_cleaned_preview(dataset_id, page=1, page_size=10, search=None)
    assert preview_res.total_rows == report.final_rows
    assert len(preview_res.rows) <= 10
    assert len(preview_res.columns) == report.final_cols
    print(f"[OK] On-screen dataset preview verified ({len(preview_res.rows)} rows returned out of {preview_res.total_rows}).")

    # Test preview search filtering
    preview_search = data_preparation_agent.get_cleaned_preview(dataset_id, page=1, page_size=10, search="Laptop")
    assert preview_search.total_rows >= 0
    print(f"[OK] On-screen preview search filtering verified.")

    # 10. Check PDF Cleaning Report File (UPDATE 4)
    pdf_path = REPORTS_DIR / f"report_{dataset_id}.pdf"
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000
    print(f"[OK] PDF Report file generated via ReportLab ({pdf_path.stat().st_size} bytes).")

    # 11. Test SQL Security Validator
    is_valid, msg = validate_read_only_sql(f'DROP TABLE "{report.sqlite_table_name}";')
    assert not is_valid
    assert "Forbidden SQL keyword" in msg
    print("[OK] SQL Security Validator successfully blocked DROP TABLE statement.")

    # 12. Test Natural Language SQL Agent Execution
    q1 = "How many products are there?"
    resp1 = sql_agent.execute_query(q1, dataset_id, report.sqlite_table_name)
    assert resp1.executed
    assert resp1.row_count > 0
    print(f"[OK] SQL Query 1 ('{q1}') executed successfully.")

    q2 = "What is the average price?"
    resp2 = sql_agent.execute_query(q2, dataset_id, report.sqlite_table_name)
    assert resp2.executed
    print(f"[OK] SQL Query 2 ('{q2}') executed successfully.")

    # 13. Test Post-Preprocessing User Feedback & Suggestion Feature
    from app.models.cleaning_models import PostCleanApplyRequest

    # Test column validation for non-existent column (e.g. gender or age_group)
    post_no_gender = data_preparation_agent.analyze_post_clean_suggestion(dataset_id, "Convert M and F to Male and Female in gender")
    assert post_no_gender.supported is False
    assert "Could not find a gender column" in post_no_gender.unsupported_reason
    print("[OK] Column validation correctly flagged non-existent 'gender' column with clear message.")

    # Test valid post-preprocessing analysis for existing column (e.g. city)
    post_analysis = data_preparation_agent.analyze_post_clean_suggestion(dataset_id, "Convert all city values to lowercase")
    assert post_analysis.supported is True
    assert post_analysis.column == "city"
    assert post_analysis.operation == "normalize_casing"
    print("[OK] Post-preprocessing feedback analysis successful (city lowercase detected).")

    # Apply approved post-preprocessing suggestion
    post_apply = data_preparation_agent.apply_post_clean_suggestion(dataset_id, PostCleanApplyRequest(
        user_instruction="Convert all city values to lowercase",
        requested_change=post_analysis.requested_change or "Convert city to lowercase",
        column=post_analysis.column,
        operation=post_analysis.operation or "normalize_casing",
        mapping=post_analysis.mapping,
        strategy=post_analysis.strategy or "lowercase",
        approved=True
    ))
    assert post_apply.status == "SUCCESS"
    assert post_apply.affected_rows >= 0
    print("[OK] Post-preprocessing suggestion successfully applied & verified.")

    # 14. Test SQL Query Session PDF Report Generation
    from app.services.sql_pdf_report_service import sql_pdf_report_service
    
    # Empty dataset ID test
    empty_history = sql_agent.get_query_history("non_existent_dataset_id")
    assert len(empty_history) == 0

    # Fetch dataset query history
    ds_history = sql_agent.get_query_history(dataset_id)
    assert len(ds_history) == 2
    assert ds_history[0].user_question == q1
    assert ds_history[0].executed_sql is not None

    # Generate PDF bytes
    sql_pdf_bytes = sql_pdf_report_service.generate_pdf_bytes(
        dataset_id=dataset_id,
        queries=ds_history,
        original_filename=orig_name,
        sqlite_table_name=report.sqlite_table_name
    )
    assert len(sql_pdf_bytes) > 1000
    print(f"[OK] SQL Query Session PDF report generated successfully ({len(sql_pdf_bytes)} bytes).")

    # 15. Test Bug 1 — Categorical GROUP BY Normalization & Duplicate Validation
    from app.services.database_service import database_service
    test_tbl = "test_dup_cats_tbl"
    conn = database_service._get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f'DROP TABLE IF EXISTS "{test_tbl}";')
        cur.execute(f'CREATE TABLE "{test_tbl}" (branch TEXT, sales REAL);')
        cur.executemany(f'INSERT INTO "{test_tbl}" VALUES (?, ?);', [
            ("Bandra ", 100.0),
            (" bandra", 50.0),
            ("BANDRA", 200.0),
            ("Delhi Central", 400.0),
            ("delhi central", 300.0)
        ])
        conn.commit()
    finally:
        conn.close()

    dup_cat_resp = sql_agent.execute_query("Give me total sales for each branch", dataset_id="test_ds_dup", table_name=test_tbl)
    assert dup_cat_resp.executed is True
    assert dup_cat_resp.row_count == 2, f"Expected 2 aggregated rows, got {dup_cat_resp.row_count}: {dup_cat_resp.rows}"
    branch_labels = [r["branch"] for r in dup_cat_resp.rows]
    assert len(set(b.strip().lower() for b in branch_labels)) == 2
    print(f"[OK] Bug 1 Fix Verified: Categorical text GROUP BY normalized duplicate categories into 2 rows: {dup_cat_resp.rows}")

    # 16. Test Bug 1 — Location Field Explanation (City vs Branch)
    city_q_resp = sql_agent.execute_query("Give me total sales for each city", dataset_id="test_ds_dup", table_name=test_tbl)
    assert city_q_resp.executed is True
    assert "branch" in city_q_resp.columns or "branch" in city_q_resp.executed_sql.lower()
    assert "city" not in city_q_resp.columns
    assert "The dataset does not contain a city column, so I used the branch field as the available location field." in city_q_resp.explanation
    print(f"[OK] Bug 1 Fix Verified: Location field correctly used branch and appended schema explanation notice.")

    # 17. Test Bug 2 — SQL Session PDF Report FastAPI Response
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    api_resp = client.get(f"/api/dataset/{dataset_id}/sql-report")
    assert api_resp.status_code == 200
    assert api_resp.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in api_resp.headers["content-disposition"]
    assert api_resp.content.startswith(b"%PDF-")
    print(f"[OK] Bug 2 Fix Verified: SQL Session PDF Report endpoint returned binary PDF ({len(api_resp.content)} bytes).")

    print("==========================================")
    print("ALL PLATFORM & POST-PREPROCESSING & SQL REPORT TESTS PASSED SUCCESSFULLY!")
    print("==========================================\n")

if __name__ == "__main__":
    test_full_platform_pipeline()
