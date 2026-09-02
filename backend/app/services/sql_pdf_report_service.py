import io
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
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
from reportlab.pdfgen import canvas

from app.models.query_models import QueryResponse
from app.utils.sql_formatter import format_sql_for_display

logger = logging.getLogger("sql_pdf_report_service")


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas for ReportLab that draws clean running footers
    with exact 'Page X of Y' pagination on every page.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        
        # Footer line at Y=32
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(40, 32, 572, 32)
        
        # Left footer branding
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(40, 20, "DataPilot AI Platform  •  SQL Query Session Report")
        
        # Right footer page number
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 20, page_str)
        
        self.restoreState()


class SqlPDFReportService:
    def generate_pdf_bytes(
        self,
        dataset_id: str,
        queries: List[QueryResponse],
        original_filename: Optional[str] = None,
        sqlite_table_name: Optional[str] = None
    ) -> bytes:
        """
        Generates a high-quality professional PDF report containing the complete SQL Query Session history.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=45
        )

        styles = getSampleStyleSheet()

        # Executive Palette
        c_primary = colors.HexColor("#1E293B")     # Slate 800 (Primary headers & accents)
        c_secondary = colors.HexColor("#475569")   # Slate 600 (Labels & subtitles)
        c_accent = colors.HexColor("#2563EB")      # Blue 600 (Brand line & info)
        c_success = colors.HexColor("#059669")     # Emerald 600 (Success metrics)
        c_warning = colors.HexColor("#D97706")     # Amber 600 (Self-corrections)
        c_danger = colors.HexColor("#DC2626")      # Red 600 (Failures)
        c_text_dark = colors.HexColor("#0F172A")   # Slate 900 (Body text)
        c_bg_light = colors.HexColor("#F8FAFC")    # Slate 50 (Card & row backgrounds)
        c_border = colors.HexColor("#CBD5E1")      # Slate 300 (Borders)

        # Typography Styles
        platform_style = ParagraphStyle(
            "PlatformSub",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=c_secondary,
            fontName="Helvetica-Bold",
            spaceAfter=2
        )

        doc_title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=c_primary,
            fontName="Helvetica-Bold",
            spaceAfter=8
        )

        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            textColor=c_primary,
            fontName="Helvetica-Bold",
            spaceBefore=10,
            spaceAfter=6
        )

        section_label = ParagraphStyle(
            "SectionLabel",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=c_secondary,
            fontName="Helvetica-Bold",
            spaceBefore=6,
            spaceAfter=3
        )

        body_style = ParagraphStyle(
            "BodyDark",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=c_text_dark,
            fontName="Helvetica"
        )

        meta_label_style = ParagraphStyle(
            "MetaLabel",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=c_secondary,
            fontName="Helvetica-Bold"
        )

        meta_val_style = ParagraphStyle(
            "MetaVal",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=c_text_dark,
            fontName="Helvetica"
        )

        sql_text_style = ParagraphStyle(
            "SqlCodeText",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11.5,
            textColor=c_primary,
            fontName="Courier"
        )

        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.white,
            fontName="Helvetica-Bold"
        )

        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=c_text_dark,
            fontName="Helvetica"
        )

        table_cell_code = ParagraphStyle(
            "TableCellCode",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=c_text_dark,
            fontName="Courier"
        )

        story = []
        printable_width = 532.0  # 612 - 80

        # Helper: Create SQL Code Block Flowable Table
        def build_sql_code_block(sql_str: str) -> Table:
            escaped_sql = (
                sql_str.replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;")
                       .replace("\n", "<br/>")
                       .replace(" ", "&nbsp;")
            )
            para = Paragraph(escaped_sql, sql_text_style)
            tbl = Table([[para]], colWidths=[printable_width])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
                ('BOX', (0,0), (-1,-1), 1, c_border),
                ('PADDING', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            return tbl

        # Helper: Format numeric floats nicely for presentation without altering raw data
        def format_presentation_val(val: Any) -> str:
            if val is None:
                return "null"
            val_str = str(val)
            if isinstance(val, float):
                try:
                    return f"{val:,.2f}"
                except Exception:
                    return val_str
            if re.match(r'^-?\d+\.\d{3,}$', val_str):
                try:
                    flt = float(val_str)
                    return f"{flt:,.2f}"
                except Exception:
                    pass
            return val_str

        # 1. Report Header
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        story.append(Paragraph("DATAPILOT AI PLATFORM", platform_style))
        story.append(Paragraph("SQL QUERY SESSION REPORT", doc_title_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceBefore=0, spaceAfter=10))

        # 2. Metadata Box Table
        first_time = queries[0].timestamp if queries and queries[0].timestamp else now_str
        tbl_name = sqlite_table_name or (queries[0].table_name if queries else "N/A")
        ds_name = original_filename or dataset_id

        total_q = len(queries)
        successful_q = sum(1 for q in queries if q.executed)
        failed_q = total_q - successful_q
        retries_q = sum(1 for q in queries if q.retries > 0)
        viz_q = sum(1 for q in queries if q.visualization_type and q.visualization_type != "none")

        meta_data = [
            [
                Paragraph("Dataset:", meta_label_style),
                Paragraph(ds_name, meta_val_style),
                Paragraph("Dataset ID:", meta_label_style),
                Paragraph(dataset_id[:8], meta_val_style)
            ],
            [
                Paragraph("SQLite Table:", meta_label_style),
                Paragraph(tbl_name, meta_val_style),
                Paragraph("Session Started:", meta_label_style),
                Paragraph(first_time, meta_val_style)
            ],
            [
                Paragraph("Report Generated:", meta_label_style),
                Paragraph(now_str, meta_val_style),
                Paragraph("Total Queries:", meta_label_style),
                Paragraph(str(total_q), meta_val_style)
            ]
        ]
        meta_table = Table(meta_data, colWidths=[100, 166, 100, 166])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
            ('BOX', (0,0), (-1,-1), 1, c_border),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # 3. Session Summary Section
        story.append(Paragraph("SQL SESSION SUMMARY", section_heading))
        
        sum_headers = ["Total Queries", "Successful", "Failed", "Self-Corrected (Retried)", "Visualizations Generated"]
        sum_vals = [
            Paragraph(f"<b>{total_q}</b>", ParagraphStyle("SH1", parent=styles["Normal"], alignment=1, textColor=c_primary, fontName="Helvetica-Bold", fontSize=9.5)),
            Paragraph(f"<b>{successful_q}</b>", ParagraphStyle("SH2", parent=styles["Normal"], alignment=1, textColor=c_success, fontName="Helvetica-Bold", fontSize=9.5)),
            Paragraph(f"<b>{failed_q}</b>", ParagraphStyle("SH3", parent=styles["Normal"], alignment=1, textColor=c_danger if failed_q > 0 else c_primary, fontName="Helvetica-Bold", fontSize=9.5)),
            Paragraph(f"<b>{retries_q}</b>", ParagraphStyle("SH4", parent=styles["Normal"], alignment=1, textColor=c_warning if retries_q > 0 else c_primary, fontName="Helvetica-Bold", fontSize=9.5)),
            Paragraph(f"<b>{viz_q}</b>", ParagraphStyle("SH5", parent=styles["Normal"], alignment=1, textColor=c_accent, fontName="Helvetica-Bold", fontSize=9.5))
        ]

        sum_data = [
            [Paragraph(h, ParagraphStyle("SH", parent=table_header_style, alignment=1)) for h in sum_headers],
            sum_vals
        ]
        sum_table = Table(sum_data, colWidths=[106.4] * 5)
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), c_primary),
            ('BOX', (0,0), (-1,-1), 1, c_border),
            ('GRID', (0,0), (-1,-1), 0.5, c_border),
            ('BACKGROUND', (0,1), (-1,1), c_bg_light),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=0.5, color=c_border, spaceBefore=2, spaceAfter=10))

        # 4. Query History Section
        story.append(Paragraph("QUERY HISTORY", section_heading))

        if not queries:
            story.append(Paragraph("<i>No SQL queries have been executed in this session.</i>", body_style))
        else:
            for idx, q in enumerate(queries, start=1):
                query_flowables = []

                # A) Query Header Bar
                q_status_bg = colors.HexColor("#ECFDF5") if q.executed else colors.HexColor("#FEF2F2")
                q_status_border = colors.HexColor("#A7F3D0") if q.executed else colors.HexColor("#FCA5A5")
                q_status_text_color = colors.HexColor("#065F46") if q.executed else colors.HexColor("#991B1B")
                q_status_str = "SUCCESS" if q.executed else "FAILED"
                q_time = q.timestamp or "N/A"

                header_left = Paragraph(
                    f"QUERY #{idx} &nbsp;&nbsp;&bull;&nbsp;&nbsp; Time: {q_time}",
                    ParagraphStyle("QHLeft", parent=styles["Normal"], textColor=colors.white, fontSize=9.5, fontName="Helvetica-Bold")
                )
                
                badge_para = Paragraph(
                    f"<b>{q_status_str}</b>",
                    ParagraphStyle("QHBadge", parent=styles["Normal"], textColor=q_status_text_color, fontSize=8, fontName="Helvetica-Bold", alignment=1)
                )
                
                badge_table = Table([[badge_para]], colWidths=[80])
                badge_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), q_status_bg),
                    ('BOX', (0,0), (-1,-1), 1, q_status_border),
                    ('PADDING', (0,0), (-1,-1), 3),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ]))

                header_table = Table([
                    [header_left, badge_table]
                ], colWidths=[420, 112])
                header_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), c_primary),
                    ('PADDING', (0,0), (-1,-1), 5),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ]))

                query_flowables.append(header_table)
                query_flowables.append(Spacer(1, 4))

                # B) User Question
                query_flowables.append(Paragraph("USER QUESTION", section_label))
                query_flowables.append(Paragraph(q.user_question, body_style))
                query_flowables.append(Spacer(1, 4))

                # C) Executed SQL
                query_flowables.append(Paragraph("EXECUTED SQL", section_label))
                raw_exec_sql = q.executed_sql or q.generated_sql
                executed_sql_val = q.formatted_sql or format_sql_for_display(raw_exec_sql)
                query_flowables.append(build_sql_code_block(executed_sql_val))
                query_flowables.append(Spacer(1, 6))

                # D) Optional Initial SQL (if retried)
                raw_init_sql = q.initial_sql or q.generated_sql
                if q.retries > 0 or (raw_init_sql and raw_init_sql != raw_exec_sql):
                    initial_sql_val = format_sql_for_display(raw_init_sql)
                    query_flowables.append(Paragraph("INITIAL GENERATED SQL", section_label))
                    query_flowables.append(build_sql_code_block(initial_sql_val))
                    query_flowables.append(Spacer(1, 6))

                # E) Optional Self-Correction History Table
                if q.self_correction_logs:
                    query_flowables.append(Paragraph("SELF-CORRECTION / RETRY HISTORY", section_label))
                    sc_rows = [[
                        Paragraph("Attempt", table_header_style),
                        Paragraph("SQL Attempted", table_header_style),
                        Paragraph("Error / Reason", table_header_style)
                    ]]
                    for scl in q.self_correction_logs:
                        sc_rows.append([
                            Paragraph(str(scl.attempt), ParagraphStyle("SCAtt", parent=table_cell_style, alignment=1)),
                            Paragraph(scl.sql_attempted.replace("<", "&lt;").replace(">", "&gt;"), table_cell_code),
                            Paragraph(scl.error_message.replace("<", "&lt;").replace(">", "&gt;"), table_cell_style)
                        ])
                    sc_table = Table(sc_rows, colWidths=[50, 230, 252])
                    sc_table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), c_warning),
                        ('GRID', (0,0), (-1,-1), 0.5, c_border),
                        ('ROWBACKGROUNDS', (0,1), (-1,-1), [c_bg_light]),
                        ('PADDING', (0,0), (-1,-1), 5),
                        ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ]))
                    query_flowables.append(sc_table)
                    query_flowables.append(Spacer(1, 6))

                # F) Execution Error Box (if failed)
                if not q.executed and q.execution_error:
                    err_para = Paragraph(
                        f"<b>EXECUTION ERROR:</b> {q.execution_error}",
                        ParagraphStyle("ErrText", parent=styles["Normal"], textColor=c_danger, fontSize=8.5, leading=11)
                    )
                    err_box = Table([[err_para]], colWidths=[printable_width])
                    err_box.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF2F2")),
                        ('BOX', (0,0), (-1,-1), 1, c_danger),
                        ('PADDING', (0,0), (-1,-1), 6),
                    ]))
                    query_flowables.append(err_box)
                    query_flowables.append(Spacer(1, 6))

                # G) Database Result Section
                if q.executed and q.columns:
                    res_label_str = f"DATABASE RESULT <font color='#64748B'>({q.row_count} rows returned)</font>"
                    query_flowables.append(Paragraph(res_label_str, section_label))

                    max_display_rows = 25
                    display_rows = q.rows[:max_display_rows]

                    header_row = [Paragraph(str(col), table_header_style) for col in q.columns]
                    res_table_data = [header_row]

                    for r in display_rows:
                        row_cells = []
                        for col in q.columns:
                            val = r.get(col)
                            formatted_val = format_presentation_val(val)
                            cell_align = 2 if isinstance(val, (int, float)) or re.match(r'^-?[\d,]+\.\d+$', formatted_val) else 0
                            c_style = ParagraphStyle("TCell", parent=table_cell_style, alignment=cell_align)
                            row_cells.append(Paragraph(formatted_val.replace("<", "&lt;").replace(">", "&gt;"), c_style))
                        res_table_data.append(row_cells)

                    col_cnt = len(q.columns)
                    col_w = max(50.0, float(printable_width / max(1, col_cnt)))
                    col_widths = [col_w] * col_cnt

                    res_table = Table(res_table_data, colWidths=col_widths)
                    res_table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), c_primary),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
                        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
                        ('PADDING', (0,0), (-1,-1), 4.5),
                        ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ]))
                    query_flowables.append(res_table)

                    if q.row_count > max_display_rows:
                        query_flowables.append(Spacer(1, 2))
                        query_flowables.append(Paragraph(f"<i>... showing top {max_display_rows} rows out of {q.row_count} total returned rows.</i>", ParagraphStyle("Trunc", parent=body_style, fontSize=8, textColor=colors.HexColor("#64748B"))))

                    query_flowables.append(Spacer(1, 6))

                # H) Visualization Information Box (if applicable)
                if q.visualization_type and q.visualization_type != "none":
                    viz_label_p = Paragraph("VISUALIZATION GENERATED", section_label)
                    viz_str = f"<b>{q.visualization_type.upper()} Chart</b>"
                    if q.x_axis or q.y_axis:
                        viz_str += f" &nbsp;&nbsp;&bull;&nbsp;&nbsp; X-Axis: <b>{q.x_axis or 'N/A'}</b> &nbsp;&bull;&nbsp; Y-Axis: <b>{q.y_axis or 'N/A'}</b>"

                    viz_para = Paragraph(viz_str, ParagraphStyle("VizText", parent=styles["Normal"], textColor=colors.HexColor("#1E40AF"), fontSize=8.5, leading=11))
                    viz_box = Table([[viz_para]], colWidths=[printable_width])
                    viz_box.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
                        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BFDBFE")),
                        ('PADDING', (0,0), (-1,-1), 6),
                    ]))
                    query_flowables.append(viz_label_p)
                    query_flowables.append(viz_box)
                    query_flowables.append(Spacer(1, 6))

                # I) Answer Box Section
                if q.explanation:
                    ans_label_p = Paragraph("ANSWER", section_label)
                    ans_para = Paragraph(
                        q.explanation,
                        ParagraphStyle("AnsText", parent=styles["Normal"], textColor=colors.HexColor("#065F46"), fontSize=9, leading=13)
                    )
                    ans_box = Table([[ans_para]], colWidths=[printable_width])
                    ans_box.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ECFDF5")),
                        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#A7F3D0")),
                        ('PADDING', (0,0), (-1,-1), 8),
                    ]))
                    query_flowables.append(ans_label_p)
                    query_flowables.append(ans_box)

                query_flowables.append(Spacer(1, 10))

                # Page break / KeepTogether logic:
                # If query section is concise (e.g. <= 5 result rows), keep the ENTIRE query section together!
                # If query section has large result table (> 5 rows), keep Header + Question + Executed SQL block together.
                if len(q.rows) <= 5:
                    story.append(KeepTogether(query_flowables))
                else:
                    head_part = query_flowables[:7]
                    tail_part = query_flowables[7:]
                    story.append(KeepTogether(head_part))
                    for f in tail_part:
                        story.append(f)

                if idx < len(queries):
                    story.append(HRFlowable(width="100%", thickness=0.5, color=c_border, spaceBefore=4, spaceAfter=10))

        # 5. End Footer Banner
        story.append(Spacer(1, 12))
        end_text = "END OF SQL SESSION REPORT &nbsp;&bull;&nbsp; Generated by DataPilot AI Platform"
        story.append(Paragraph(end_text, ParagraphStyle("EndFooter", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#94A3B8"), alignment=1)))

        # Build PDF with NumberedCanvas page number generator
        doc.build(story, canvasmaker=NumberedCanvas)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes


sql_pdf_report_service = SqlPDFReportService()
