import datetime
from pathlib import Path
from typing import List
from app.config import REPORTS_DIR
from app.models.cleaning_models import CleaningReport, CleaningHistoryItem, BeforeAfterComparison

class ReportService:
    def generate_markdown_report(
        self,
        dataset_id: str,
        original_filename: str,
        original_rows: int,
        final_rows: int,
        original_cols: int,
        final_cols: int,
        applied: List[CleaningHistoryItem],
        declined: List[CleaningHistoryItem],
        comparisons: List[BeforeAfterComparison],
        sqlite_table_name: str
    ) -> CleaningReport:
        """
        Generates structured Markdown report and saves it to REPORTS_DIR.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_md = f"""# DATASET CLEANING & VALIDATION REPORT

**Dataset ID:** `{dataset_id}`  
**Original Filename:** `{original_filename}`  
**Date Processed:** `{timestamp}`  
**SQLite Table:** `{sqlite_table_name}`  

---

## 1. DATASET METRICS SUMMARY

| Metric | Original State | Final Cleaned State | Change |
| :--- | :--- | :--- | :--- |
| **Row Count** | {original_rows} | {final_rows} | {final_rows - original_rows} rows |
| **Column Count** | {original_cols} | {final_cols} | {final_cols - original_cols} cols |

---

## 2. BEFORE vs AFTER QUALITY COMPARISON

| Quality Metric | Before Cleaning | After Cleaning | Status / Improvement |
| :--- | :--- | :--- | :--- |
"""
        for comp in comparisons:
            report_md += f"| **{comp.metric}** | {comp.before} | {comp.after} | {comp.improvement} |\n"

        report_md += """
---

## 3. HUMAN-APPROVED OPERATIONS PERFORMED

"""
        if applied:
            for item in applied:
                status_icon = "🟢" if item.execution_status == "applied" else "🔴"
                report_md += f"- **{status_icon} [{item.operation.upper()}]** on Column `{item.column or 'Entire Dataset'}` (Strategy: `{item.strategy}`)\n"
                report_md += f"  - *Outcome*: {item.details}\n"
        else:
            report_md += "*No operations were approved or applied.*\n"

        report_md += """
---

## 4. OPERATIONS DECLINED BY USER

"""
        if declined:
            for item in declined:
                report_md += f"- **🟡 [{item.operation.upper()}]** on Column `{item.column or 'Entire Dataset'}` (Strategy: `{item.strategy}`)\n"
                report_md += f"  - *Reason*: {item.details}\n"
        else:
            report_md += "*No recommendations were declined.*\n"

        report_md += f"""
---

## 5. NEXT STEPS & SQL QUERY ACCESS

The dataset has been cleaned, validated, and loaded into SQLite table `{sqlite_table_name}`.
You may now query this clean dataset using natural language via the SQL Agent.
"""

        # Write report file to REPORTS_DIR
        report_file_path = REPORTS_DIR / f"report_{dataset_id}.md"
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(report_md)

        return CleaningReport(
            dataset_id=dataset_id,
            original_filename=original_filename,
            timestamp=timestamp,
            original_rows=original_rows,
            final_rows=final_rows,
            original_cols=original_cols,
            final_cols=final_cols,
            operations_applied=applied,
            operations_declined=declined,
            before_after_comparison=comparisons,
            sqlite_table_name=sqlite_table_name
        )

report_service = ReportService()
