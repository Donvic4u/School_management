from io import BytesIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)

from .models import (
    Enrollment,
    ResultPublication,
    SchoolProfile,
    Student,
    Term,
)

from .result_views import build_class_results


def public_result_pdf(request):
    # ---------------------------------------------------------
    # SECURITY: PDF can only be downloaded after successful
    # admission-number + PIN verification in the public portal.
    # ---------------------------------------------------------
    access_data = request.session.get("public_result_access")

    if not access_data:
        return HttpResponse(
            "Please access the result portal and verify your admission number "
            "and PIN before downloading the PDF.",
            status=403,
        )

    student_id = access_data.get("student_id")
    term_id = access_data.get("term_id")
    session_id = access_data.get("session_id")

    student = get_object_or_404(Student, id=student_id)

    term = get_object_or_404(
        Term,
        id=term_id,
        session_id=session_id,
    )

    # ---------------------------------------------------------
    # FIND STUDENT ENROLLMENT
    # ---------------------------------------------------------
    enrollment = (
        Enrollment.objects
        .filter(
            student=student,
            term=term,
        )
        .select_related(
            "student",
            "class_level",
            "term",
        )
        .first()
    )

    if enrollment is None:
        return HttpResponse(
            "No result enrollment was found.",
            status=404,
        )

    # ---------------------------------------------------------
    # RESULT MUST BE PUBLISHED
    # ---------------------------------------------------------
    publication = (
        ResultPublication.objects
        .filter(
            session=term.session,
            term=term,
            class_level=enrollment.class_level,
            published=True,
        )
        .first()
    )

    if publication is None:
        return HttpResponse(
            "This result has not been published.",
            status=403,
        )

    # ---------------------------------------------------------
    # BUILD OFFICIAL RESULT
    # build_class_results() already uses approved scores.
    # ---------------------------------------------------------
    class_results = build_class_results(
        enrollment.class_level,
        term,
    )

    result = next(
        (
            item
            for item in class_results["students"]
            if item["student"].id == student.id
        ),
        None,
    )

    if result is None:
        return HttpResponse(
            "No approved result is available.",
            status=404,
        )

    # ---------------------------------------------------------
    # SCHOOL PROFILE
    # ---------------------------------------------------------
    school_profile = SchoolProfile.objects.first()

    # ---------------------------------------------------------
    # PDF DOCUMENT
    # ---------------------------------------------------------
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Report Card - {student.full_name}",
        author="School Management System",
    )

    # ---------------------------------------------------------
    # STYLES
    # ---------------------------------------------------------
    styles = getSampleStyleSheet()

    school_name_style = ParagraphStyle(
        "SchoolName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        alignment=TA_CENTER,
        spaceAfter=2,
    )

    motto_style = ParagraphStyle(
        "Motto",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        spaceAfter=2,
    )

    contact_style = ParagraphStyle(
        "Contact",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        alignment=TA_CENTER,
    )

    report_title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=4,
    )

    section_style = ParagraphStyle(
        "Section",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        alignment=TA_LEFT,
    )

    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
    )

    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8,
        alignment=TA_CENTER,
        textColor=colors.white,
    )

    subject_style = ParagraphStyle(
        "Subject",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8.5,
        alignment=TA_LEFT,
    )

    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=8,
        alignment=TA_CENTER,
    )

    small_center_style = ParagraphStyle(
        "SmallCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8,
        alignment=TA_CENTER,
    )

    # ---------------------------------------------------------
    # STORY
    # ---------------------------------------------------------
    story = []

    # =========================================================
    # SCHOOL HEADER
    # =========================================================
    header_rows = []

    if school_profile:
        school_name = school_profile.name or ""
        motto = school_profile.motto or ""
        address = school_profile.address or ""

        contact_parts = []

        if school_profile.phone:
            contact_parts.append(
                f"Tel: {school_profile.phone}"
            )

        if school_profile.email:
            contact_parts.append(
                f"Email: {school_profile.email}"
            )

        contact = " | ".join(contact_parts)

        header_content = [
            Paragraph(
                school_name.upper(),
                school_name_style,
            )
        ]

        if motto:
            header_content.append(
                Paragraph(
                    motto,
                    motto_style,
                )
            )

        if address:
            header_content.append(
                Paragraph(
                    address,
                    contact_style,
                )
            )

        if contact:
            header_content.append(
                Paragraph(
                    contact,
                    contact_style,
                )
            )

        header_table = Table(
            [[header_content]],
            colWidths=[190 * mm],
        )

        header_table.setStyle(
            TableStyle(
                [
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        1.2,
                        colors.HexColor("#1f5f3b"),
                    ),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#f5f8f6"),
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        8,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        8,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                ]
            )
        )

        story.append(header_table)

    else:
        story.append(
            Paragraph(
                "SCHOOL REPORT CARD",
                school_name_style,
            )
        )

    story.append(Spacer(1, 4))

    # =========================================================
    # REPORT TITLE
    # =========================================================
    title_table = Table(
        [
            [
                Paragraph(
                    "STUDENT REPORT CARD",
                    report_title_style,
                )
            ]
        ],
        colWidths=[190 * mm],
    )

    title_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#1f5f3b"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.white,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.8,
                    colors.HexColor("#1f5f3b"),
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.append(title_table)
    story.append(Spacer(1, 5))

    # =========================================================
    # STUDENT INFORMATION
    # =========================================================
    student_info = [
        [
            Paragraph("STUDENT NAME", label_style),
            Paragraph(student.full_name, value_style),
            Paragraph("ADMISSION NO.", label_style),
            Paragraph(student.admission_number, value_style),
        ],
        [
            Paragraph("CLASS", label_style),
            Paragraph(enrollment.class_level.name, value_style),
            Paragraph("TERM", label_style),
            Paragraph(term.name, value_style),
        ],
        [
            Paragraph("ACADEMIC SESSION", label_style),
            Paragraph(term.session.name, value_style),
            Paragraph("", label_style),
            Paragraph("", value_style),
        ],
    ]

    student_info_table = Table(
        student_info,
        colWidths=[
            31 * mm,
            64 * mm,
            31 * mm,
            64 * mm,
        ],
        repeatRows=0,
    )

    student_info_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#b8b8b8"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#edf1ee"),
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    colors.HexColor("#edf1ee"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(student_info_table)
    story.append(Spacer(1, 7))

    # =========================================================
    # SUBJECT RESULTS
    # =========================================================
    story.append(
        Paragraph(
            "ACADEMIC PERFORMANCE",
            section_style,
        )
    )

    story.append(Spacer(1, 3))

    subject_rows = [
        [
            Paragraph("S/N", table_header_style),
            Paragraph("SUBJECT", table_header_style),
            Paragraph("CA1<br/>10", table_header_style),
            Paragraph("CA2<br/>10", table_header_style),
            Paragraph("CA3<br/>10", table_header_style),
            Paragraph("EXAM<br/>70", table_header_style),
            Paragraph("TOTAL<br/>100", table_header_style),
            Paragraph("GRADE", table_header_style),
            Paragraph("REMARK", table_header_style),
            Paragraph("POS.", table_header_style),
        ]
    ]

    for index, subject_result in enumerate(
        class_results["subjects"],
        start=1,
    ):
        total = subject_result.get("total")

        if total is None:
            continue

        subject_name = (
            subject_result["subject"]["subject__name"]
        )

        subject_rows.append(
            [
                Paragraph(str(index), cell_style),
                Paragraph(subject_name, subject_style),
                Paragraph(
                    f'{subject_result["ca1"]:.2f}',
                    cell_style,
                ),
                Paragraph(
                    f'{subject_result["ca2"]:.2f}',
                    cell_style,
                ),
                Paragraph(
                    f'{subject_result["ca3"]:.2f}',
                    cell_style,
                ),
                Paragraph(
                    f'{subject_result["exam"]:.2f}',
                    cell_style,
                ),
                Paragraph(
                    f'{total:.2f}',
                    cell_style,
                ),
                Paragraph(
                    str(subject_result["grade"]),
                    cell_style,
                ),
                Paragraph(
                    str(subject_result["remark"]),
                    cell_style,
                ),
                Paragraph(
                    str(subject_result["position"]),
                    cell_style,
                ),
            ]
        )

    subject_table = Table(
        subject_rows,
        colWidths=[
            9 * mm,
            42 * mm,
            14 * mm,
            14 * mm,
            14 * mm,
            16 * mm,
            17 * mm,
            14 * mm,
            28 * mm,
            12 * mm,
        ],
        repeatRows=1,
    )

    subject_style_commands = [
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#1f5f3b"),
        ),
        (
            "TEXTCOLOR",
            (0, 0),
            (-1, 0),
            colors.white,
        ),
        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.45,
            colors.HexColor("#a8a8a8"),
        ),
        (
            "VALIGN",
            (0, 0),
            (-1, -1),
            "MIDDLE",
        ),
        (
            "ALIGN",
            (0, 0),
            (-1, -1),
            "CENTER",
        ),
        (
            "ALIGN",
            (1, 1),
            (1, -1),
            "LEFT",
        ),
        (
            "LEFTPADDING",
            (0, 0),
            (-1, -1),
            3,
        ),
        (
            "RIGHTPADDING",
            (0, 0),
            (-1, -1),
            3,
        ),
        (
            "TOPPADDING",
            (0, 0),
            (-1, -1),
            3,
        ),
        (
            "BOTTOMPADDING",
            (0, 0),
            (-1, -1),
            3,
        ),
    ]

    for row_number in range(1, len(subject_rows)):
        if row_number % 2 == 0:
            subject_style_commands.append(
                (
                    "BACKGROUND",
                    (0, row_number),
                    (-1, row_number),
                    colors.HexColor("#f7f9f7"),
                )
            )

    subject_table.setStyle(
        TableStyle(subject_style_commands)
    )

    story.append(subject_table)
    story.append(Spacer(1, 7))

    # =========================================================
    # SUMMARY
    # =========================================================
    story.append(
        Paragraph(
            "RESULT SUMMARY",
            section_style,
        )
    )

    story.append(Spacer(1, 3))

    summary_rows = [
        [
            Paragraph("TOTAL MARKS", label_style),
            Paragraph(
                f'{result["total_marks"]:.2f}',
                small_center_style,
            ),
            Paragraph("AVERAGE", label_style),
            Paragraph(
                f'{result["average"]:.2f}',
                small_center_style,
            ),
        ],
        [
            Paragraph("OVERALL POSITION", label_style),
            Paragraph(
                str(result["position"]),
                small_center_style,
            ),
            Paragraph("OVERALL GRADE", label_style),
            Paragraph(
                str(result["overall_grade"]),
                small_center_style,
            ),
        ],
        [
            Paragraph("OVERALL REMARK", label_style),
            Paragraph(
                str(result["overall_remark"]),
                small_center_style,
            ),
            Paragraph("", label_style),
            Paragraph("", small_center_style),
        ],
    ]

    summary_table = Table(
        summary_rows,
        colWidths=[
            38 * mm,
            45 * mm,
            38 * mm,
            69 * mm,
        ],
    )

    summary_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#b8b8b8"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#edf1ee"),
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    colors.HexColor("#edf1ee"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    # Span final remark value across remaining cells.
    summary_table.setStyle(
        TableStyle(
            [
                (
                    "SPAN",
                    (1, 2),
                    (3, 2),
                ),
            ]
        )
    )

    story.append(summary_table)
    story.append(Spacer(1, 8))

    # =========================================================
    # FORM TEACHER BEHAVIOUR COMMENT
    # =========================================================

    form_teacher_heading = Table(
        [
            [
                Paragraph(
                    "FORM TEACHER'S BEHAVIOUR COMMENT",
                    section_style,
                )
            ]
        ],
        colWidths=[190 * mm],
    )

    form_teacher_heading.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#edf1ee"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#b8b8b8"),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    behaviour_comment = (
        enrollment.get_form_teacher_comment_display()
        if enrollment and enrollment.form_teacher_comment
        else "No Form Teacher behaviour comment has been selected."
    )

    form_teacher_comment_table = Table(
        [
            [
                Paragraph(
                    str(behaviour_comment),
                    contact_style,
                )
            ]
        ],
        colWidths=[190 * mm],
    )

    form_teacher_comment_table.setStyle(
        TableStyle(
            [
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#b8b8b8"),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
            ]
        )
    )

    story.append(
        KeepTogether(
            [
                form_teacher_heading,
                form_teacher_comment_table,
            ]
        )
    )

    story.append(Spacer(1, 10))

    # =========================================================
    # FORM TEACHER PRINCIPAL'S OVERALL COMMENT
    # =========================================================

    academic_comment = (
        enrollment.get_academic_performance_comment_display()
        if enrollment and enrollment.academic_performance_comment
        else "No principal's overall comment has been selected."
    )

    academic_comment_heading = Table(
        [
            [
                Paragraph(
                    "FORM TEACHER'S PRINCIPAL'S OVERALL COMMENT",
                    section_style,
                )
            ]
        ],
        colWidths=[190 * mm],
    )

    academic_comment_heading.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#edf1ee"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#b8b8b8"),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    academic_comment_table = Table(
        [
            [
                Paragraph(
                    str(academic_comment),
                    contact_style,
                )
            ]
        ],
        colWidths=[190 * mm],
    )

    academic_comment_table.setStyle(
        TableStyle(
            [
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#b8b8b8"),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
            ]
        )
    )

    story.append(
        KeepTogether(
            [
                academic_comment_heading,
                academic_comment_table,
            ]
        )
    )

    story.append(Spacer(1, 10))

    # =========================================================
    # SIGNATURES
    # =========================================================
    signature_table = Table(
        [
            [
                "____________________________",
            ],
            [
                "Form Teacher's Signature",
            ],
        ],
        colWidths=[95 * mm],
    )

    signature_table.setStyle(
        TableStyle(
            [
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER",
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(signature_table)
    story.append(Spacer(1, 6))

    # =========================================================
    # FOOTER NOTE
    # =========================================================
    footer_table = Table(
        [
            [
                Paragraph(
                    "This report card is generated from the school's "
                    "official published result records.",
                    contact_style,
                )
            ]
        ],
        colWidths=[190 * mm],
    )

    footer_table.setStyle(
        TableStyle(
            [
                (
                    "LINEABOVE",
                    (0, 0),
                    (-1, 0),
                    0.5,
                    colors.HexColor("#cccccc"),
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.append(footer_table)

    # =========================================================
    # BUILD PDF
    # =========================================================
    document.build(story)

    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
    )

    response["Content-Disposition"] = (
        f'attachment; filename="'
        f'result_{student.admission_number}_'
        f'{term.name.replace(" ", "_")}.pdf"'
    )

    return response
