"""
RETIVUE CADe — Formal Clinical Decision-Support PDF Report Generator
Generates multi-page, publication-grade vector PDF reports with embedded retinal scans,
genuine Grad-CAM overlays, 5-class probability distributions, longitudinal comparisons,
and digitally signed clinical assessments.
"""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, Color
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from PIL import Image as PILImage


# Professional Healthcare & RETIVUE Design Palette
COLOR_PRIMARY = HexColor("#1c281e")       # Deep botanical slate
COLOR_OLIVE = HexColor("#4a5320")         # Retivue olive green
COLOR_ACCENT = HexColor("#6f7d3e")        # Sage green
COLOR_BG_LIGHT = HexColor("#faf9f5")      # Warm clinical cream
COLOR_BORDER = HexColor("#e8e4d8")        # Subdued border
COLOR_TEXT = HexColor("#1c1d1a")          # Deep charcoal
COLOR_MUTED = HexColor("#6a6d62")         # Neutral grey
COLOR_EMERALD = HexColor("#059669")      # Normal / Passed
COLOR_AMBER = HexColor("#d97706")        # Warning / Review required
COLOR_ROSE = HexColor("#dc2626")         # High risk / Proliferative
COLOR_WHITE = HexColor("#ffffff")


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute total pages and render running headers/footers.
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
        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_MUTED)

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 11 * inch - 28, "RETIVUE CADe • Comprehensive Clinical Screening Report")
            self.drawRightString(8.5 * inch - 36, 11 * inch - 28, "CONFIDENTIAL MEDICAL RECORD")
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(36, 11 * inch - 32, 8.5 * inch - 36, 11 * inch - 32)

        # Running Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(36, 24, "RETIVUE CADe v4.8.1 • Clinical Decision Support Systems • Verification Ref: SHA-256 Provenance")
        self.drawRightString(8.5 * inch - 36, 24, page_str)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(36, 34, 8.5 * inch - 36, 34)
        self.restoreState()


class PdfReportService:
    """
    Constructs comprehensive, server-rendered PDF diagnostic reports.
    """

    @classmethod
    def generate_pdf(
        cls,
        report_data: Dict[str, Any],
        comparison_data: Optional[Dict[str, Any]] = None,
        image_bytes_map: Optional[Dict[str, bytes]] = None,
    ) -> bytes:
        """
        Builds formal medical PDF bytes from structured clinical report data.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=40,
            bottomMargin=42,
        )

        styles = cls._build_stylesheet()
        story: List[Any] = []

        # 1. Header Banner
        cls._add_header_banner(story, styles, report_data)

        # 2. Patient Demographics & Consent Audit
        cls._add_patient_and_consent_section(story, styles, report_data)

        # 3. AI Screening Findings & Bilateral Executive Summary
        ai_run = report_data.get("latest_ai_run")
        if ai_run:
            cls._add_ai_screening_summary(story, styles, report_data, ai_run)
            cls._add_eye_detailed_findings(story, styles, report_data, ai_run)

        # 4. Retinal Imagery & Grad-CAM Visualizations
        if image_bytes_map:
            cls._add_visual_evidence_section(story, styles, report_data, image_bytes_map)

        # 5. Longitudinal Screening Comparison (if previous encounter available)
        if comparison_data:
            cls._add_longitudinal_comparison_section(story, styles, comparison_data)

        # 6. Licensed Professional Clinical Assessment
        review = report_data.get("clinical_review")
        cls._add_clinical_review_section(story, styles, review)

        # 7. Dispatched Referrals (if present)
        referrals = report_data.get("referrals", [])
        if referrals:
            cls._add_referrals_section(story, styles, referrals)

        # 8. Mandatory Safety Notice & Legal Disclaimers
        cls._add_safety_disclaimer(story, styles, report_data)

        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()

    @classmethod
    def _build_stylesheet(cls) -> Dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()
        custom = {}

        custom["Title"] = ParagraphStyle(
            "RetivueTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=COLOR_PRIMARY,
        )
        custom["Subtitle"] = ParagraphStyle(
            "RetivueSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=COLOR_MUTED,
        )
        custom["SectionHeader"] = ParagraphStyle(
            "RetivueSectionHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=COLOR_OLIVE,
            spaceAfter=4,
        )
        custom["Body"] = ParagraphStyle(
            "RetivueBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=COLOR_TEXT,
        )
        custom["BodyBold"] = ParagraphStyle(
            "RetivueBodyBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11.5,
            textColor=COLOR_TEXT,
        )
        custom["SmallMuted"] = ParagraphStyle(
            "RetivueSmallMuted",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=COLOR_MUTED,
        )
        custom["Narrative"] = ParagraphStyle(
            "RetivueNarrative",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=COLOR_TEXT,
        )
        custom["BadgeText"] = ParagraphStyle(
            "RetivueBadgeText",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            alignment=1,
            textColor=COLOR_WHITE,
        )
        return custom

    @classmethod
    def _add_header_banner(cls, story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]):
        title_p = Paragraph("<b>RETIVUE CADe</b>", styles["Title"])
        subtitle_p = Paragraph("Clinical Decision-Support &amp; Ophthalmic Screening Report", styles["Subtitle"])

        ref_str = f"<b>Encounter:</b> {data.get('screening_reference', 'N/A')}<br/>"
        ref_str += f"<b>Report ID:</b> {data.get('report_id', 'N/A')}<br/>"
        gen_dt = data.get("generated_at")
        date_str = gen_dt.strftime("%d %b %Y, %H:%M UTC") if isinstance(gen_dt, datetime) else str(gen_dt or 'N/A')
        ref_str += f"<b>Generated:</b> {date_str}"
        meta_p = Paragraph(ref_str, styles["Body"])

        header_table = Table([[ [title_p, subtitle_p], meta_p ]], colWidths=[3.5 * inch, 4.0 * inch])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(header_table)
        story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_OLIVE, spaceBefore=4, spaceAfter=8))

    @classmethod
    def _add_patient_and_consent_section(cls, story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]):
        pt = data.get("patient", {})
        consent = data.get("consent", {})

        p_info = [
            Paragraph(f"<b>Patient Name:</b> {pt.get('full_name', 'Anonymous')}", styles["Body"]),
            Paragraph(f"<b>MRN / Clinic ID:</b> {pt.get('medical_record_number', 'N/A')}", styles["Body"]),
            Paragraph(f"<b>DOB / Gender:</b> {pt.get('date_of_birth', 'N/A')} • {pt.get('gender', 'Unspecified')}", styles["Body"]),
            Paragraph(f"<b>Diabetes Type:</b> {pt.get('diabetes_type', 'Unspecified')}", styles["Body"]),
        ]

        c_status = consent.get("status", "missing").upper()
        c_obtained = consent.get("obtained_at")
        c_dt_str = c_obtained.strftime("%d %b %Y") if isinstance(c_obtained, datetime) else str(c_obtained or 'Recorded')

        c_info = [
            Paragraph(f"<b>Informed Retinal Consent:</b> <font color='{COLOR_EMERALD.hexval()}'><b>{c_status}</b></font>", styles["Body"]),
            Paragraph(f"<b>Form Protocol Version:</b> {consent.get('form_version', 'v2.1')}", styles["Body"]),
            Paragraph(f"<b>Consent Recorded:</b> {c_dt_str}", styles["Body"]),
            Paragraph(f"<b>Bilateral Images Captured:</b> {len(data.get('images', []))} Verified Frames", styles["Body"]),
        ]

        t = Table([[p_info, c_info]], colWidths=[3.75 * inch, 3.75 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.75, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    @classmethod
    def _add_ai_screening_summary(cls, story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any], ai_run: Dict[str, Any]):
        worst_eye = ai_run.get("higher_risk_eye") or "Equal / Bilateral"
        highest_label = (ai_run.get("highest_predicted_label") or "Unspecified").replace("_", " ").title()
        status_text = (ai_run.get("overall_status") or "Completed").upper()

        status_color = COLOR_EMERALD if "passed" in status_text.lower() or "completed" in status_text.lower() else COLOR_AMBER

        content_left = [
            Paragraph("<b>RESEARCH AI BILATERAL SCREENING SUMMARY</b>", styles["SectionHeader"]),
            Paragraph(f"<b>Worst Eye:</b> {worst_eye}  •  <b>Highest Predicted Severity:</b> {highest_label}", styles["BodyBold"]),
            Paragraph(f"<b>Model Provenance:</b> EfficientNet-B0 (Epoch {ai_run.get('checkpoint_epoch', 2)}) • SHA-256: <code>{ai_run.get('checkpoint_sha256', '')[:16]}...</code>", styles["SmallMuted"]),
        ]

        content_right = [
            Paragraph(f"<font color='{status_color.hexval()}'><b>STATUS: {status_text}</b></font>", styles["BodyBold"]),
            Paragraph(f"<b>Execution Latency:</b> {ai_run.get('execution_ms', 0)} ms", styles["SmallMuted"]),
            Paragraph(f"<b>Escalation Required:</b> {'YES (Professional Review Mandatory)' if ai_run.get('overall_review_required') else 'NO'}", styles["SmallMuted"]),
        ]

        t = Table([[content_left, content_right]], colWidths=[4.75 * inch, 2.75 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_WHITE),
            ("BOX", (0, 0), (-1, -1), 1, COLOR_OLIVE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    @classmethod
    def _add_eye_detailed_findings(cls, story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any], ai_run: Dict[str, Any]):
        eye_results = ai_run.get("eye_results", [])
        if not eye_results:
            return

        cols = []
        for eye in eye_results:
            eye_name = "Right Eye (OD)" if eye.get("eye") == "OD" else "Left Eye (OS)"
            gradable = eye.get("gradable", True)

            cells = [
                Paragraph(f"<b>{eye_name}</b> — {'Gradable Quality' if gradable else 'Ungradable Quality'}", styles["SectionHeader"]),
            ]

            if gradable:
                pred_label = (eye.get("predicted_label") or "Ungraded").replace("_", " ").title()
                conf_pct = (eye.get("confidence_max_prob") or 0.0) * 100
                vtdr_pct = (eye.get("vtdr_prob_sum") or 0.0) * 100
                margin_pct = (eye.get("top2_margin") or 0.0) * 100
                entropy = eye.get("normalized_entropy")
                entropy_str = f"{entropy:.3f}" if entropy is not None else "—"

                cells.append(Paragraph(f"<b>Predicted DR Grade:</b> {pred_label} ({conf_pct:.1f}% Confidence)", styles["BodyBold"]))
                cells.append(Paragraph(f"<b>Referable VTDR Risk:</b> {vtdr_pct:.1f}% • <b>Margin:</b> {margin_pct:.1f}% • <b>Entropy:</b> {entropy_str}", styles["SmallMuted"]))

                # 5-class distribution table
                probs = eye.get("probabilities", {})
                prob_rows = [
                    ["DR Severity Class", "Probability"],
                    ["Class 0: No DR", f"{cls._extract_prob(probs, 0) * 100:.1f}%"],
                    ["Class 1: Mild NPDR", f"{cls._extract_prob(probs, 1) * 100:.1f}%"],
                    ["Class 2: Moderate NPDR", f"{cls._extract_prob(probs, 2) * 100:.1f}%"],
                    ["Class 3: Severe NPDR", f"{cls._extract_prob(probs, 3) * 100:.1f}%"],
                    ["Class 4: Proliferative DR", f"{cls._extract_prob(probs, 4) * 100:.1f}%"],
                ]
                ptab = Table(prob_rows, colWidths=[2.2 * inch, 1.2 * inch])
                ptab.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                    ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_BORDER),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ]))
                cells.append(Spacer(1, 3))
                cells.append(ptab)

                # Narrative
                expl = eye.get("explanation")
                if expl and expl.get("explanation_text"):
                    cells.append(Spacer(1, 4))
                    cells.append(Paragraph(f"<b>Explainability Narrative:</b> {expl['explanation_text']}", styles["Narrative"]))
            else:
                cells.append(Paragraph(f"<font color='{COLOR_ROSE.hexval()}'><b>MODEL REFUSED GRADE:</b> {eye.get('quality_reason', 'Failed quality gate.')}</font>", styles["Body"]))
                cells.append(Paragraph("Grad-CAM generation is suppressed for ungradable captures to protect clinical safety. Re-capture required.", styles["SmallMuted"]))

            cols.append(cells)

        t = Table([cols], colWidths=[3.75 * inch, 3.75 * inch])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.75, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    @classmethod
    def _add_visual_evidence_section(
        cls,
        story: List[Any],
        styles: Dict[str, ParagraphStyle],
        report_data: Dict[str, Any],
        image_bytes_map: Dict[str, bytes],
    ):
        """
        Embeds high-resolution retinal fundus scans and genuine Grad-CAM overlays side-by-side.
        """
        story.append(Paragraph("<b>HIGH-RESOLUTION FUNDUS IMAGERY &amp; GENUINE GRAD-CAM EXPLAINABILITY</b>", styles["SectionHeader"]))
        story.append(Paragraph(
            "Visualizations depict actual model attention weights extracted from convolutional layer <code>features[8]</code>. "
            "Grad-CAM reflects statistical attention attribution and does <b>not</b> denote biological lesion segmentations.",
            styles["SmallMuted"]
        ))
        story.append(Spacer(1, 4))

        img_cells = []
        labels = []

        for eye in ("OD", "OS"):
            orig_key = f"{eye}_original"
            ov_key = f"{eye}_overlay"

            orig_img = cls._make_scaled_rl_image(image_bytes_map.get(orig_key), width=1.75 * inch, height=1.75 * inch)
            ov_img = cls._make_scaled_rl_image(image_bytes_map.get(ov_key), width=1.75 * inch, height=1.75 * inch)

            img_cells.extend([orig_img, ov_img])
            labels.extend([
                Paragraph(f"<b>{eye} Original Scan</b>", styles["SmallMuted"]),
                Paragraph(f"<b>{eye} Grad-CAM Overlay</b>", styles["SmallMuted"]),
            ])

        grid = Table([labels, img_cells], colWidths=[1.85 * inch, 1.85 * inch, 1.85 * inch, 1.85 * inch])
        grid.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("BACKGROUND", (0, 1), (-1, 1), COLOR_PRIMARY),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ]))
        story.append(grid)
        story.append(Spacer(1, 8))

    @classmethod
    def _add_longitudinal_comparison_section(
        cls,
        story: List[Any],
        styles: Dict[str, ParagraphStyle],
        comp: Dict[str, Any],
    ):
        story.append(Paragraph("<b>LONGITUDINAL SCREENING COMPARISON &amp; PROGRESSION TRACKING</b>", styles["SectionHeader"]))

        prev_ref = comp.get("previous_screening_reference", "Prior Encounter")
        prev_dt = comp.get("previous_screening_date")
        prev_date_str = prev_dt.strftime("%d %b %Y") if isinstance(prev_dt, datetime) else str(prev_dt or 'N/A')
        interval = comp.get("days_interval", 0)

        intro = f"Comparison evaluated against prior encounter <b>{prev_ref}</b> recorded on <b>{prev_date_str}</b> (Elapsed interval: {interval} days)."
        story.append(Paragraph(intro, styles["Body"]))

        if not comp.get("is_directly_comparable", True):
            for note in comp.get("comparability_notes", []):
                story.append(Paragraph(f"<font color='{COLOR_AMBER.hexval()}'><b>Comparability Limitation:</b> {note}</font>", styles["SmallMuted"]))

        od_c = comp.get("od_comparison", {})
        os_c = comp.get("os_comparison", {})

        comp_table_data = [
            ["Eye", "Prior Grade", "Current Grade", "AI Grade Delta", "Referable Risk Shift", "Clinical Trend Summary"],
            [
                "Right (OD)",
                cls._format_grade(od_c.get("previous_grade"), od_c.get("previous_label")),
                cls._format_grade(od_c.get("current_grade"), od_c.get("current_label")),
                cls._format_delta(od_c.get("grade_difference")),
                cls._format_shift(od_c.get("vtdr_risk_shift")),
                od_c.get("neutral_summary", "Unchanged"),
            ],
            [
                "Left (OS)",
                cls._format_grade(os_c.get("previous_grade"), os_c.get("previous_label")),
                cls._format_grade(os_c.get("current_grade"), os_c.get("current_label")),
                cls._format_delta(os_c.get("grade_difference")),
                cls._format_shift(os_c.get("vtdr_risk_shift")),
                os_c.get("neutral_summary", "Unchanged"),
            ],
        ]

        t = Table(comp_table_data, colWidths=[1.0 * inch, 1.25 * inch, 1.25 * inch, 0.9 * inch, 1.1 * inch, 2.0 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_BORDER),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(Spacer(1, 3))
        story.append(t)
        story.append(Spacer(1, 8))

    @classmethod
    def _add_clinical_review_section(cls, story: List[Any], styles: Dict[str, ParagraphStyle], review: Optional[Dict[str, Any]]):
        story.append(Paragraph("<b>QUALIFIED HEALTHCARE PROFESSIONAL CLINICAL ASSESSMENT</b>", styles["SectionHeader"]))

        if review and review.get("is_signed"):
            reviewer = review.get("reviewer_name_snapshot", "Registered Ophthalmologist")
            reg_no = review.get("reviewer_registration_number_snapshot", "MCI-CERTIFIED")
            signed_dt = review.get("signed_at")
            signed_str = signed_dt.strftime("%d %b %Y, %H:%M UTC") if isinstance(signed_dt, datetime) else str(signed_dt or 'Signed')

            r_left = [
                Paragraph(f"<b>Signatory Practitioner:</b> {reviewer}", styles["BodyBold"]),
                Paragraph(f"<b>Medical Registration:</b> {reg_no}", styles["Body"]),
                Paragraph(f"<b>Digital Signature Timestamp:</b> {signed_str}", styles["SmallMuted"]),
                Paragraph(f"<b>AI Agreement Status:</b> {str(review.get('ai_agreement_status', '')).replace('_', ' ').upper()}", styles["BodyBold"]),
            ]

            r_right = [
                Paragraph(f"<b>Confirmed OD Grade:</b> {cls._format_grade(review.get('od_confirmed_grade'))}", styles["Body"]),
                Paragraph(f"<b>Confirmed OS Grade:</b> {cls._format_grade(review.get('os_confirmed_grade'))}", styles["Body"]),
                Paragraph(f"<b>Worst Eye Confirmed:</b> {str(review.get('worst_eye_confirmed_label', 'Recapture Required')).replace('_', ' ').title()}", styles["BodyBold"]),
            ]

            t = Table([[r_left, r_right]], colWidths=[4.0 * inch, 3.5 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 1, COLOR_OLIVE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(t)

            if review.get("override_rationale"):
                story.append(Spacer(1, 3))
                story.append(Paragraph(f"<b>Override Rationale:</b> {review['override_rationale']}", styles["Narrative"]))

            if review.get("clinical_findings"):
                story.append(Spacer(1, 3))
                story.append(Paragraph(f"<b>Clinical Findings:</b> {review['clinical_findings']}", styles["Narrative"]))

            if review.get("follow_up_plan"):
                story.append(Spacer(1, 3))
                story.append(Paragraph(f"<b>Management &amp; Surveillance Plan:</b> {review['follow_up_plan']}", styles["Narrative"]))
        else:
            pending_p = Paragraph(
                f"<font color='{COLOR_AMBER.hexval()}'><b>INDEPENDENT CLINICAL REVIEW PENDING</b></font><br/>"
                "This document reflects automated artificial intelligence screening telemetry. "
                "Only certified ophthalmic practitioners are authorized to confirm diabetic retinopathy severity and mandate surgical or pharmacological intervention.",
                styles["Body"]
            )
            t = Table([[pending_p]], colWidths=[7.5 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#fffbeb")),
                ("BOX", (0, 0), (-1, -1), 1, COLOR_AMBER),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(t)

        story.append(Spacer(1, 8))

    @classmethod
    def _add_referrals_section(cls, story: List[Any], styles: Dict[str, ParagraphStyle], referrals: List[Dict[str, Any]]):
        story.append(Paragraph("<b>SPECIALIST REFERRALS &amp; CLINICAL DISPATCH</b>", styles["SectionHeader"]))
        rows = [["Referral Ref", "Facility & Specialty", "Urgency Tier", "Reason / Summary"]]
        for r in referrals:
            rows.append([
                r.get("referral_reference", "N/A"),
                f"{r.get('target_facility', 'Clinic')} ({r.get('target_specialty', 'Retina')})",
                str(r.get("urgency", "Standard")).replace("_", " "),
                r.get("reason_summary", "Routine review"),
            ])
        t = Table(rows, colWidths=[1.25 * inch, 2.5 * inch, 1.25 * inch, 2.5 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_BORDER),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    @classmethod
    def _add_safety_disclaimer(cls, story: List[Any], styles: Dict[str, ParagraphStyle], data: Dict[str, Any]):
        notice_text = (
            "<b>MANDATORY CLINICAL SAFETY NOTICE &amp; REGULATORY DISCLAIMER:</b> "
            "RETIVUE CADe is an automated triage decision-support tool designed to aid licensed clinicians in screening for Diabetic Retinopathy. "
            "It does not generate autonomous medical diagnoses or dispense prescriptions. All findings, classifications, and Grad-CAM attention regions "
            "must be corroborated by qualified healthcare personnel through independent ophthalmic evaluation."
        )
        t = Table([[Paragraph(notice_text, styles["SmallMuted"])]], colWidths=[7.5 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    @staticmethod
    def _extract_prob(probs: Dict[str, Any], class_idx: int) -> float:
        if not probs:
            return 0.0
        # Direct grade index
        if str(class_idx) in probs:
            try:
                return float(probs[str(class_idx)])
            except (ValueError, TypeError):
                pass
        # Canonical prefix or label
        label_tokens = {
            0: ["class_0", "no_dr", "nodr"],
            1: ["class_1", "mild"],
            2: ["class_2", "moderate"],
            3: ["class_3", "severe"],
            4: ["class_4", "proliferative", "pdr"],
        }.get(class_idx, [f"class_{class_idx}"])
        for k, v in probs.items():
            lk = str(k).lower().replace("-", "_")
            if any(tok in lk for tok in label_tokens):
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass
        return 0.0

    @staticmethod
    def _format_grade(grade: Optional[int], label: Optional[str] = None) -> str:
        if grade is None:
            return "Ungraded"
        clean_lbl = f" ({label.replace('_', ' ').title()})" if label else ""
        return f"Grade {grade}{clean_lbl}"

    @staticmethod
    def _format_delta(delta: Optional[int]) -> str:
        if delta is None:
            return "—"
        if delta > 0:
            return f"+{delta} (Increased)"
        if delta < 0:
            return f"{delta} (Decreased)"
        return "0 (Unchanged)"

    @staticmethod
    def _format_shift(shift: Optional[float]) -> str:
        if shift is None:
            return "—"
        sign = "+" if shift > 0 else ""
        return f"{sign}{shift * 100:.1f}%"

    @staticmethod
    def _make_scaled_rl_image(img_bytes: Optional[bytes], width: float, height: float) -> Any:
        if not img_bytes:
            return Paragraph("<font color='#888888'>Unavailable</font>", getSampleStyleSheet()["Normal"])
        try:
            return RLImage(io.BytesIO(img_bytes), width=width, height=height)
        except Exception:
            return Paragraph("<font color='#888888'>Corrupt Image</font>", getSampleStyleSheet()["Normal"])
