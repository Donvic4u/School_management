from io import BytesIO
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .models import ClassLevel, ClassSubject, SchoolProfile
from .result_views import build_class_results, get_current_term


@login_required(login_url="/teacher-login/")
def class_master_result_pdf(request, class_id):
    class_level = get_object_or_404(ClassLevel, id=class_id)
    term = get_current_term()

    if term is None:
        return HttpResponse(
            "No academic term has been configured.",
            status=400,
        )

    result = build_class_results(class_level, term)
    students = result.get("students", [])

    # Master Result must show every subject assigned to the class,
    # not only subjects that already have approved scores.
    class_subjects = (
        ClassSubject.objects
        .filter(
            class_level=class_level,
            active=True,
        )
        .select_related("subject")
        .order_by("subject__name")
    )

    subjects = [
        {
            "subject_id": class_subject.subject_id,
            "subject__code": class_subject.subject.code,
            "subject__name": class_subject.subject.name,
        }
        for class_subject in class_subjects
    ]

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=7 * mm,
        leftMargin=7 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
        title=f"Master Result - {class_level.name}",
        author="School Management System",
    )

    styles = getSampleStyleSheet()

    school_profile = (
        SchoolProfile.objects.first()
    )

    school_name = (
        school_profile.name
        if school_profile
        else "SCHOOL NAME"
    )

    school_address = (
        school_profile.address
        if school_profile
        else ""
    )

    school_contact = ""

    if school_profile:
        contact_parts = []

        if school_profile.phone:
            contact_parts.append(
                f"Tel: {school_profile.phone}"
            )

        if school_profile.email:
            contact_parts.append(
                f"Email: {school_profile.email}"
            )

        school_contact = " | ".join(contact_parts)

    school_motto = (
        school_profile.motto
        if school_profile
        else ""
    )

    school_name_style = ParagraphStyle(
        "MasterSchoolName",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=17,
        leading=20,
        spaceAfter=2,
    )

    school_address_style = ParagraphStyle(
        "MasterSchoolAddress",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=8,
        leading=10,
        spaceAfter=1,
    )

    motto_style = ParagraphStyle(
        "MasterMotto",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=8,
        leading=10,
        italic=True,
        spaceAfter=5,
    )

    title_style = ParagraphStyle(
        "MasterTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=14,
        leading=17,
        spaceAfter=3,
    )

    subtitle_style = ParagraphStyle(
        "MasterSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        leading=12,
        spaceAfter=8,
    )

    cell_style = ParagraphStyle(
        "MasterCell",
        parent=styles["Normal"],
        fontSize=5.8,
        leading=7,
        alignment=TA_CENTER,
    )

    subject_cell_style = ParagraphStyle(
        "MasterSubjectCell",
        parent=cell_style,
        fontSize=5.5,
        leading=6.5,
        alignment=TA_CENTER,
    )

    left_cell_style = ParagraphStyle(
        "MasterLeftCell",
        parent=cell_style,
        alignment=0,
    )

    story = []

    story.append(
        Paragraph(
            f"<b>{school_name}</b>",
            school_name_style,
        )
    )

    if school_address:
        story.append(
            Paragraph(
                school_address,
                school_address_style,
            )
        )

    if school_contact:
        story.append(
            Paragraph(
                school_contact,
                school_address_style,
            )
        )

    if school_motto:
        story.append(
            Paragraph(
                f"<i>{school_motto}</i>",
                motto_style,
            )
        )

    story.append(
        Paragraph(
            "<b>MASTER RESULT</b>",
            title_style,
        )
    )

    story.append(
        Paragraph(
            f"<b>CLASS:</b> {class_level.name}"
            f" &nbsp;&nbsp;&nbsp; "
            f"<b>SESSION:</b> {term.session.name}"
            f" &nbsp;&nbsp;&nbsp; "
            f"<b>TERM:</b> {term.name}",
            subtitle_style,
        )
    )

    # ---------------------------------------------------------
    # TABLE HEADERS
    # ---------------------------------------------------------

    header_row_1 = [
        Paragraph("<b>Position</b>", cell_style),
        Paragraph("<b>Admission No.</b>", cell_style),
        Paragraph("<b>Student Name</b>", cell_style),
    ]

    header_row_2 = [
        "",
        "",
        "",
    ]

    for subject in subjects:
        name = subject.get(
            "subject__name",
            subject.get("name", ""),
        )

        header_row_1.append(
            Paragraph(
                f"<b>{name}</b>",
                cell_style,
            )
        )

        header_row_2.append(
            Paragraph(
                "<b>CA1&nbsp;&nbsp;CA2&nbsp;&nbsp;CA3&nbsp;&nbsp;EXAM&nbsp;&nbsp;TOTAL</b>",
                subject_cell_style,
            )
        )

    header_row_1.extend(
        [
            Paragraph("<b>Total Marks</b>", cell_style),
            Paragraph("<b>Average</b>", cell_style),
            Paragraph("<b>Grade</b>", cell_style),
            Paragraph("<b>Remark</b>", cell_style),
        ]
    )

    header_row_2.extend(
        [
            "",
            "",
            "",
            "",
        ]
    )

    data = [
        header_row_1,
        header_row_2,
    ]

    # ---------------------------------------------------------
    # STUDENT ROWS
    # ---------------------------------------------------------

    for student in students:

        row = [
            Paragraph(
                str(student.get("position", "")),
                cell_style,
            ),
            Paragraph(
                str(student["student"].admission_number),
                cell_style,
            ),
            Paragraph(
                student["student"].full_name,
                left_cell_style,
            ),
        ]

        subject_rows = student.get(
            "subjects",
            [],
        )

        for subject in subjects:

            subject_id = subject.get(
                "subject_id"
            )

            matching = next(
                (
                    subject_row
                    for subject_row in subject_rows
                    if isinstance(
                        subject_row.get("subject"),
                        dict,
                    )
                    and subject_row["subject"].get(
                        "subject_id"
                    ) == subject_id
                ),
                None,
            )

            if matching is None:
                row.append(
                    Paragraph(
                        "-",
                        subject_cell_style,
                    )
                )
                continue

            def score_text(value):
                if value is None:
                    return "-"
                return f"{Decimal(str(value)):.2f}"

            ca1 = score_text(
                matching.get("ca1")
            )

            ca2 = score_text(
                matching.get("ca2")
            )

            ca3 = score_text(
                matching.get("ca3")
            )

            exam = score_text(
                matching.get("exam")
            )

            total = score_text(
                matching.get("total")
            )

            subject_text = (
                f"<b>CA1:</b> {ca1}<br/>"
                f"<b>CA2:</b> {ca2}<br/>"
                f"<b>CA3:</b> {ca3}<br/>"
                f"<b>Exam:</b> {exam}<br/>"
                f"<b>Total:</b> {total}"
            )

            row.append(
                Paragraph(
                    subject_text,
                    subject_cell_style,
                )
            )

        total_marks = student.get(
            "total_marks",
            "",
        )

        average = student.get(
            "average",
            "",
        )

        if total_marks not in ("", None):
            total_marks = f"{Decimal(str(total_marks)):.2f}"

        if average not in ("", None):
            average = f"{Decimal(str(average)):.2f}"

        row.extend(
            [
                Paragraph(
                    str(total_marks),
                    cell_style,
                ),
                Paragraph(
                    str(average),
                    cell_style,
                ),
                Paragraph(
                    str(
                        student.get(
                            "overall_grade",
                            "",
                        )
                    ),
                    cell_style,
                ),
                Paragraph(
                    str(
                        student.get(
                            "overall_remark",
                            "",
                        )
                    ),
                    left_cell_style,
                ),
            ]
        )

        data.append(row)

    # ---------------------------------------------------------
    # EMPTY CLASS
    # ---------------------------------------------------------

    if not students:

        empty_row = [
            Paragraph(
                "No students found for this class and term.",
                cell_style,
            )
        ]

        while len(empty_row) < len(header_row_1):
            empty_row.append("")

        data.append(empty_row)

    # ---------------------------------------------------------
    # COLUMN WIDTHS
    # ---------------------------------------------------------

    page_width = (
        landscape(A4)[0]
        - 14 * mm
    )

    fixed_widths = [
        14 * mm,
        24 * mm,
        40 * mm,
    ]

    final_widths = [
        18 * mm,   # Total Marks
        18 * mm,   # Average
        12 * mm,   # Grade
        31 * mm,   # Remark
    ]

    available_for_subjects = (
        page_width
        - sum(fixed_widths)
        - sum(final_widths)
    )

    if subjects:
        subject_width = (
            available_for_subjects
            / len(subjects)
        )

        subject_width = max(
            18 * mm,
            subject_width,
        )
    else:
        subject_width = 20 * mm

    col_widths = (
        fixed_widths
        + [
            subject_width
            for _ in subjects
        ]
        + final_widths
    )

    # ---------------------------------------------------------
    # TABLE
    # ---------------------------------------------------------

    table = Table(
        data,
        colWidths=col_widths,
        repeatRows=2,
        repeatCols=3,
        hAlign="LEFT",
    )

    table_style = [
        (
            "BACKGROUND",
            (0, 0),
            (-1, 1),
            colors.HexColor("#0b6b3a"),
        ),
        (
            "TEXTCOLOR",
            (0, 0),
            (-1, 1),
            colors.white,
        ),
        (
            "FONTNAME",
            (0, 0),
            (-1, 1),
            "Helvetica-Bold",
        ),
        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.35,
            colors.grey,
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
            "LEFTPADDING",
            (0, 0),
            (-1, -1),
            2,
        ),
        (
            "RIGHTPADDING",
            (0, 0),
            (-1, -1),
            2,
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
        (
            "ALIGN",
            (2, 2),
            (2, -1),
            "LEFT",
        ),
        (
            "ALIGN",
            (-1, 2),
            (-1, -1),
            "LEFT",
        ),
    ]

    table.setStyle(
        TableStyle(table_style)
    )

    story.append(table)

    document.build(story)

    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
    )

    response["Content-Disposition"] = (
        f'inline; filename="master_result_{class_level.name}.pdf"'
    )

    response["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response
