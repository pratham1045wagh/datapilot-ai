import io
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models.cleaning_models import (
    CleaningHistoryItem,
    BeforeAfterComparison,
    VerificationReport,
    VerificationCheck
)

logger = logging.getLogger("pdf_report_service")

class PDFReportService:
    def generate_pdf_bytes(
        self,
        dataset_id: str,
        original_filename: str,
        original_rows: int,
        final_rows: int,
        original_cols: int,
        final_cols: int,
        operations_applied: List[CleaningHistoryItem],
        operations_declined: List[CleaningHistoryItem],
        user_requested_actions: List[CleaningHistoryItem],
        before_after_comparison: List[BeforeAfterComparison],
        verification_report: Optional[VerificationReport],
        sqlite_table_name: Optional[str] = None,
        post_clean_suggestions: Optional[List[Dict[str, Any]]] = None
    ) -> bytes:
        """
        Generates a professional PDF cleaning & preprocessing report as bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()

        # Custom Palette & Typography
        primary_color = colors.HexColor("#1e293b")  # Slate 800
        secondary_color = colors.HexColor("#0284c7") # Sky 600
        accent_color = colors.HexColor("#10b981")    # Emerald 500
        text_dark = colors.HexColor("#334155")       # Slate 700
        bg_light = colors.HexColor("#f8fafc")        # Slate 50
        border_color = colors.HexColor("#e2e8f0")    # Slate 200

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=primary_color,
            fontName="Helvetica-Bold",
            spaceAfter=4
        )

        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=secondary_color,
            fontName="Helvetica-Bold",
            spaceAfter=12
        )

        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=primary_color,
            fontName="Helvetica-Bold",
            spaceBefore=14,
            spaceAfter=8
        )

        body_style = ParagraphStyle(
            "BodyDark",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=text_dark,
            fontName="Helvetica"
        )

        bold_body = ParagraphStyle(
            "BoldBody",
            parent=body_style,
            fontName="Helvetica-Bold"
        )

        story = []

        # 1. Header
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        story.append(Paragraph("DataPilot AI Platform", subtitle_style))
        story.append(Paragraph("DATA CLEANING & PREPROCESSING REPORT", title_style))
        story.append(HRFlowable(width="100%", thickness=2, color=secondary_color, spaceBefore=4, spaceAfter=12))

        # Metadata Summary Box
        meta_data = [
            [
                Paragraph("<b>Dataset File:</b> " + original_filename, body_style),
                Paragraph("<b>Dataset ID:</b> " + dataset_id[:8], body_style)
            ],
            [
                Paragraph("<b>Generated:</b> " + timestamp_str, body_style),
                Paragraph("<b>SQLite Table:</b> " + (sqlite_table_name or "N/A"), body_style)
            ]
        ]
        meta_table = Table(meta_data, colWidths=[270, 270])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_light),
            ('BOX', (0,0), (-1,-1), 1, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # 2. Dataset Overview
        story.append(Paragraph("1. Dataset Overview", section_heading))
        overview_data = [
            ["Metric", "Original Raw State", "Final Cleaned State", "Change"],
            ["Total Rows", str(original_rows), str(final_rows), f"{original_rows - final_rows} removed"],
            ["Total Columns", str(original_cols), str(final_cols), f"{original_cols - final_cols} removed"],
        ]
        overview_table = Table(overview_data, colWidths=[150, 130, 130, 130])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, border_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(overview_table)
        story.append(Spacer(1, 14))

        # 3. Before / After Data Quality Comparison
        story.append(Paragraph("2. Data Quality Analysis & Comparison", section_heading))
        comp_rows = [["Data Quality Metric", "Before Preprocessing", "After Preprocessing", "Improvement Status"]]
        for c in before_after_comparison:
            comp_rows.append([
                str(c.metric),
                str(c.before),
                str(c.after),
                str(c.improvement)
            ])
        comp_table = Table(comp_rows, colWidths=[150, 130, 130, 130])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), secondary_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, border_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 14))

        # 4. Preprocessing Verification Results (REQUIRED SECTION)
        story.append(Paragraph("3. Preprocessing Verification Results", section_heading))
        if verification_report:
            status_color = accent_color if verification_report.overall_status == "PASSED" else colors.HexColor("#f59e0b") if verification_report.overall_status == "WARNING" else colors.HexColor("#ef4444")
            verif_banner = [
                [
                    Paragraph(f"<b>FINAL PREPROCESSING STATUS:</b> {verification_report.overall_status}", ParagraphStyle("VBanner", parent=styles["Normal"], textColor=colors.white, fontName="Helvetica-Bold", fontSize=11)),
                    Paragraph(verification_report.message, ParagraphStyle("VBannerMsg", parent=styles["Normal"], textColor=colors.white, fontSize=9.5))
                ]
            ]
            verif_table = Table(verif_banner, colWidths=[200, 340])
            verif_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), status_color),
                ('PADDING', (0,0), (-1,-1), 8),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ]))
            story.append(verif_table)
            story.append(Spacer(1, 8))

            checks_data = [["Verification Rule Check", "Expected Target", "Actual Result", "Status"]]
            for check in verification_report.checks:
                chk_color = colors.HexColor("#15803d") if check.status == "PASSED" else colors.HexColor("#b45309") if check.status == "WARNING" else colors.HexColor("#b91c1c")
                checks_data.append([
                    Paragraph(check.check_name, body_style),
                    Paragraph(check.expected, body_style),
                    Paragraph(check.actual, body_style),
                    Paragraph(f"<font color='{chk_color.hexval()}'><b>{check.status}</b></font>", body_style)
                ])
            checks_table = Table(checks_data, colWidths=[160, 130, 160, 90])
            checks_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8.5),
                ('GRID', (0,0), (-1,-1), 0.5, border_color),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(checks_table)
        story.append(Spacer(1, 14))

        # 5. User Requested Actions
        story.append(Paragraph("4. User Requested Preprocessing Actions", section_heading))
        if user_requested_actions:
            user_rows = [["User Instruction / Action", "Column", "Status", "Execution Result Details"]]
            for item in user_requested_actions:
                status_txt = "Approved & Applied" if item.execution_status == "applied" else "Declined / Skipped"
                user_rows.append([
                    Paragraph(item.operation.replace("_", " ").title(), body_style),
                    item.column or "Dataset Level",
                    status_txt,
                    Paragraph(item.details, body_style)
                ])
            user_table = Table(user_rows, colWidths=[150, 90, 110, 190])
            user_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8.5),
                ('GRID', (0,0), (-1,-1), 0.5, border_color),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(user_table)
        else:
            story.append(Paragraph("<i>No custom user preprocessing suggestions were requested.</i>", body_style))
        story.append(Spacer(1, 14))

        # 6. Approved & Executed Operations
        story.append(Paragraph("5. Approved & Executed Operations", section_heading))
        if operations_applied:
            app_rows = [["Source", "Operation", "Column", "Strategy", "Execution Details"]]
            for item in operations_applied:
                src_label = "👤 User" if item.source == "user_requested" else "🤖 AI"
                app_rows.append([
                    src_label,
                    item.operation.replace("_", " ").title(),
                    item.column or "Dataset Level",
                    item.strategy,
                    Paragraph(item.details, body_style)
                ])
            app_table = Table(app_rows, colWidths=[60, 130, 90, 80, 180])
            app_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8.5),
                ('GRID', (0,0), (-1,-1), 0.5, border_color),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(app_table)
        else:
            story.append(Paragraph("<i>No operations were executed.</i>", body_style))
        story.append(Spacer(1, 14))

        # 7. Rejected Recommendations
        story.append(Paragraph("6. Rejected Operations (Preserved by User Choice)", section_heading))
        if operations_declined:
            dec_rows = [["Source", "Operation", "Target Column", "User Decision", "Reason / Impact"]]
            for item in operations_declined:
                src_label = "👤 User" if item.source == "user_requested" else "🤖 AI"
                dec_rows.append([
                    src_label,
                    item.operation.replace("_", " ").title(),
                    item.column or "Dataset Level",
                    "Explicitly Declined",
                    Paragraph(item.details, body_style)
                ])
            dec_table = Table(dec_rows, colWidths=[60, 130, 90, 100, 160])
            dec_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8.5),
                ('GRID', (0,0), (-1,-1), 0.5, border_color),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(dec_table)
        else:
            story.append(Paragraph("<i>No recommended operations were rejected by the user.</i>", body_style))

        # 8. Post-Preprocessing User Suggestions
        if post_clean_suggestions:
            story.append(Spacer(1, 14))
            story.append(Paragraph("7. Post-Preprocessing User Suggestions", section_heading))
            pcs_rows = [["User Request", "Interpretation", "Column", "Rows", "Approval", "Verification"]]
            for pcs in post_clean_suggestions:
                pcs_rows.append([
                    Paragraph(str(pcs.get("user_instruction", "")), body_style),
                    Paragraph(str(pcs.get("requested_change", "")), body_style),
                    str(pcs.get("column", "Dataset")),
                    str(pcs.get("affected_rows", 0)),
                    str(pcs.get("approval_status", "Approved")),
                    str(pcs.get("verification_status", "PASSED"))
                ])
            pcs_table = Table(pcs_rows, colWidths=[140, 130, 80, 50, 70, 70])
            pcs_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8.5),
                ('GRID', (0,0), (-1,-1), 0.5, border_color),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(pcs_table)

        # Build PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

pdf_report_service = PDFReportService()
