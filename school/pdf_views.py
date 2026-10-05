from io import BytesIO
from decimal import Decimal

from .api_student_auth import get_authenticated_student
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle,
)
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
    Student,
    Enrollment,
    ResultPublication,
    SchoolProfile,
)
from .result_views import (
    get_current_term,
    build_class_results,
)


def student_result_pdf(request, student_id):
    # Preserve normal browser-login access while also allowing
    # an authenticated student to download their own result.
    authenticated_student = get_authenticated_student(request)

    if not request.user.is_authenticated and authenticated_student is None:
        from django.shortcuts import redirect
        return redirect("/teacher-login/?next=" + request.path)

    if authenticated_student is not None and authenticated_student.id != student_id:
        return HttpResponse(
            "You can only download your own result.",
            status=403,
        )
    """
    Generate the official private student result PDF.

    The PDF uses build_class_results() so that:
    - only approved scores are used;
    - grades are taken from GradeScale;
    - subject positions use the official ranking;
    - overall position uses the official ranking;
    - the PDF matches the on-screen result.

    CA Total is intentionally NOT displayed.
    """

    student = get_object_or_404(
        Student,
        id=student_id,
    )

    term = get_current_term()

    if term is None:
        return HttpResponse(
            "No academic term has been configured.",
            status=400,
        )

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
            "term__session",
        )
        .first()
    )

    if enrollment is None:
        return HttpResponse(
            "This student has no enrollment for the current term.",
            status=404,
        )

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
            "This result has not been published yet.",
            status=403,
        )

    class_results = build_class_results(
        enrollment.class_level,
        term,
    )

    student_data = next(
        (
            item
            for item in class_results["students"]
            if item["student"].id == student.id
        ),
        None,
    )

    if student_data is None:
        return HttpResponse(
            "No approved result is available for this student.",
            status=404,
        )

    school = SchoolProfile.objects.first()

    session_name = term.session.name
    term_name = term.name
    class_name = enrollment.class_level.name

    subjects = student_data.get(
        "subjects",
        [],
    )

    total_marks = student_data.get(
        "total_marks",
        Decimal("0"),
    )

    average = student_data.get(
        "average",
        Decimal("0"),
    )

    overall_grade = student_data.get(
        "overall_grade",
        "",
    )

    overall_remark = student_data.get(
        "overall_remark",
        "",
    )

    overall_position = student_data.get(
        "position",
        "",
    )

    completed_subjects = student_data.get(
        "completed_subjects",
        0,
    )

    total_subjects = student_data.get(
        "total_subjects",
        0,
    )

    session_code = str(session_name).replace(
        "/",
        "",
    )

    term_code = (
        str(term_name)
        .strip()
        .upper()
        .replace(" ", "")[:3]
    )

    result_reference = (
        f"{student.admission_number}-"
        f"{session_code}-"
        f"{term_code}"
    )

    # Use the exact comments stored on this student's enrollment.
    # get_*_display() converts the stored choice code into the
    # complete human-readable comment.
    form_teacher_remark = (
        enrollment.get_form_teacher_comment_display()
        if enrollment.form_teacher_comment
        else "No behaviour comment entered."
    )

    academic_comment = (
        enrollment.get_academic_performance_comment_display()
        if enrollment.academic_performance_comment
        else "No principal's overall comment entered."
    )

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=15 * mm,
        title=(
            f"Student Result - "
            f"{student.full_name}"
        ),
        author=(
            school.name
            if school
            else "School Management System"
        ),
    )

    styles = getSampleStyleSheet()

    school_name_style = ParagraphStyle(
        "PDFSchoolName",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        spaceAfter=2,
    )

    school_detail_style = ParagraphStyle(
        "PDFSchoolDetail",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        spaceAfter=1,
    )

    result_title_style = ParagraphStyle(
        "PDFResultTitle",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=5,
        spaceAfter=7,
    )

    section_style = ParagraphStyle(
        "PDFSection",
        parent=styles["Heading3"],
        alignment=TA_LEFT,
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#0b6b3a"),
        spaceBefore=6,
        spaceAfter=4,
    )

    normal_style = ParagraphStyle(
        "PDFNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
    )

    small_style = ParagraphStyle(
        "PDFSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
    )

    table_header_style = ParagraphStyle(
        "PDFTableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        alignment=TA_CENTER,
        textColor=colors.white,
    )

    table_subject_style = ParagraphStyle(
        "PDFSubject",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=colors.black,
        alignment=TA_LEFT,
    )

    story = []

    # ---------------------------------------------------------
    # SCHOOL HEADER
    # ---------------------------------------------------------

    school_name = (
        school.name
        if school
        else "ROCK FOUNDATION ACADEMY AND COLLEGE"
    )

    story.append(
        Paragraph(
            school_name,
            school_name_style,
        )
    )

    if school:
        if school.address:
            story.append(
                Paragraph(
                    school.address,
                    school_detail_style,
                )
            )

        contact_parts = []

        if school.phone:
            contact_parts.append(
                f"Tel: {school.phone}"
            )

        if school.email:
            contact_parts.append(
                f"Email: {school.email}"
            )

        if contact_parts:
            story.append(
                Paragraph(
                    " | ".join(contact_parts),
                    school_detail_style,
                )
            )

        if school.motto:
            story.append(
                Paragraph(
                    f"<i>{school.motto}</i>",
                    school_detail_style,
                )
            )

    story.append(
        Spacer(
            1,
            4,
        )
    )

    story.append(
        Paragraph(
            "STUDENT ACADEMIC RESULT",
            result_title_style,
        )
    )

    # ---------------------------------------------------------
    # STUDENT INFORMATION
    # ---------------------------------------------------------

    student_info = [
        [
            Paragraph(
                "<b>Student Name</b>",
                normal_style,
            ),
            Paragraph(
                student.full_name,
                normal_style,
            ),
            Paragraph(
                "<b>Admission No.</b>",
                normal_style,
            ),
            Paragraph(
                student.admission_number,
                normal_style,
            ),
        ],
        [
            Paragraph(
                "<b>Class</b>",
                normal_style,
            ),
            Paragraph(
                class_name,
                normal_style,
            ),
            Paragraph(
                "<b>Gender</b>",
                normal_style,
            ),
            Paragraph(
                student.gender,
                normal_style,
            ),
        ],
        [
            Paragraph(
                "<b>Academic Session</b>",
                normal_style,
            ),
            Paragraph(
                session_name,
                normal_style,
            ),
            Paragraph(
                "<b>Term</b>",
                normal_style,
            ),
            Paragraph(
                term_name,
                normal_style,
            ),
        ],
    ]

    info_table = Table(
        student_info,
        colWidths=[
            29 * mm,
            67 * mm,
            29 * mm,
            59 * mm,
        ],
    )

    info_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.45,
                    colors.grey,
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#eef4f0"),
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    colors.HexColor("#eef4f0"),
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

    story.append(info_table)
    story.append(
        Spacer(
            1,
            6,
        )
    )

    # ---------------------------------------------------------
    # RESULT TABLE
    #
    # IMPORTANT:
    # CA Total is deliberately omitted.
    # ---------------------------------------------------------

    data = [
        [
            Paragraph(
                "Subject",
                table_header_style,
            ),
            Paragraph(
                "CA1<br/>(10)",
                table_header_style,
            ),
            Paragraph(
                "CA2<br/>(10)",
                table_header_style,
            ),
            Paragraph(
                "CA3<br/>(10)",
                table_header_style,
            ),
            Paragraph(
                "Exam<br/>(70)",
                table_header_style,
            ),
            Paragraph(
                "Total<br/>(100)",
                table_header_style,
            ),
            Paragraph(
                "Grade",
                table_header_style,
            ),
            Paragraph(
                "Pos.",
                table_header_style,
            ),
        ]
    ]

    for item in subjects:
        subject = item.get(
            "subject",
            {},
        )

        subject_name = subject.get(
            "subject__name",
            subject.get("name", ""),
        )

        def format_score(value):
            if value is None:
                return "—"
            return f"{Decimal(str(value)):.2f}"

        data.append(
            [
                Paragraph(
                    subject_name,
                    table_subject_style,
                ),
                format_score(
                    item.get("ca1")
                ),
                format_score(
                    item.get("ca2")
                ),
                format_score(
                    item.get("ca3")
                ),
                format_score(
                    item.get("exam")
                ),
                format_score(
                    item.get("total")
                ),
                item.get(
                    "grade",
                    "",
                ) or "—",
                str(
                    item.get(
                        "position",
                        "",
                    )
                ) or "—",
            ]
        )

    if not subjects:
        data.append(
            [
                Paragraph(
                    "No approved results available.",
                    table_subject_style,
                ),
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )

    result_table = Table(
        data,
        colWidths=[
            58 * mm,
            15 * mm,
            15 * mm,
            15 * mm,
            17 * mm,
            19 * mm,
            13 * mm,
            12 * mm,
        ],
        repeatRows=1,
    )

    result_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#0b6b3a"),
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
                    0.4,
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
                    (1, 1),
                    (-1, -1),
                    "CENTER",
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
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "FONTNAME",
                    (1, 1),
                    (-1, -1),
                    "Helvetica",
                ),
                (
                    "FONTSIZE",
                    (1, 1),
                    (-1, -1),
                    7.5,
                ),
            ]
        )
    )

    story.append(
        Paragraph(
            "ACADEMIC PERFORMANCE",
            section_style,
        )
    )

    story.append(result_table)

    story.append(
        Spacer(
            1,
            6,
        )
    )

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    summary_data = [
        [
            Paragraph(
                "<b>Total Marks</b>",
                normal_style,
            ),
            Paragraph(
                f"{Decimal(str(total_marks)):.2f}",
                normal_style,
            ),
            Paragraph(
                "<b>Average</b>",
                normal_style,
            ),
            Paragraph(
                f"{Decimal(str(average)):.2f}%",
                normal_style,
            ),
        ],
        [
            Paragraph(
                "<b>Overall Grade</b>",
                normal_style,
            ),
            Paragraph(
                overall_grade or "—",
                normal_style,
            ),
            Paragraph(
                "<b>Overall Position</b>",
                normal_style,
            ),
            Paragraph(
                str(overall_position)
                if overall_position
                else "—",
                normal_style,
            ),
        ],
        [
            Paragraph(
                "<b>Subjects Completed</b>",
                normal_style,
            ),
            Paragraph(
                f"{completed_subjects} / {total_subjects}",
                normal_style,
            ),
            Paragraph(
                "<b>Overall Remark</b>",
                normal_style,
            ),
            Paragraph(
                overall_remark or "—",
                normal_style,
            ),
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[
            34 * mm,
            35 * mm,
            38 * mm,
            58 * mm,
        ],
    )

    summary_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.45,
                    colors.grey,
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#eef4f0"),
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    colors.HexColor("#eef4f0"),
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

    story.append(summary_table)

    # ---------------------------------------------------------
    # FORM TEACHER COMMENTS
    # ---------------------------------------------------------

    comment_text_style = ParagraphStyle(
        "PDFCommentTextFinal",
        parent=normal_style,
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.black,
        alignment=TA_LEFT,
    )

    comment_heading_style = ParagraphStyle(
        "PDFCommentHeadingFinal",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.black,
        alignment=TA_LEFT,
    )

    behaviour_comment = (
        enrollment.get_form_teacher_comment_display()
        if enrollment.form_teacher_comment
        else "No behaviour comment entered."
    )

    academic_performance_comment = (
        enrollment.get_academic_performance_comment_display()
        if enrollment.academic_performance_comment
        else "No principal's overall comment entered."
    )

    # ReportLab Paragraph requires XML-safe text.
    from xml.sax.saxutils import escape

    behaviour_comment = escape(str(behaviour_comment))
    academic_performance_comment = escape(
        str(academic_performance_comment)
    )

    comments_table = Table(
        [
            [
                Paragraph(
                    "Conduct / Behaviour",
                    comment_heading_style,
                ),
                Paragraph(
                    behaviour_comment,
                    comment_text_style,
                ),
            ],
            [
                Paragraph(
                    "Academic Performance",
                    comment_heading_style,
                ),
                Paragraph(
                    academic_performance_comment,
                    comment_text_style,
                ),
            ],
        ],
        colWidths=[
            48 * mm,
            117 * mm,
        ],
        hAlign="LEFT",
    )

    comments_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#777777"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#eef4f0"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.black,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
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
            ]
        )
    )

    story.append(
        Paragraph(
            "FORM TEACHER'S COMMENTS",
            section_style,
        )
    )

    story.append(
        Spacer(
            1,
            4,
        )
    )

    story.append(comments_table)

    # RESULT REFERENCE
    # ---------------------------------------------------------

    story.append(
        Spacer(
            1,
            7,
        )
    )

    reference_table = Table(
        [
            [
                Paragraph(
                    "<b>Result Reference</b>",
                    normal_style,
                ),
                Paragraph(
                    result_reference,
                    normal_style,
                ),
            ]
        ],
        colWidths=[
            40 * mm,
            125 * mm,
        ],
    )

    reference_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.grey,
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, 0),
                    colors.HexColor("#eef4f0"),
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

    story.append(reference_table)

    # ---------------------------------------------------------
    # SIGNATURES
    # ---------------------------------------------------------

    story.append(
        Spacer(
            1,
            12,
        )
    )

    signature_data = [
        [
            Paragraph(
                "____________________________",
                normal_style,
            ),
            Paragraph(
                "____________________________",
                normal_style,
            ),
        ],
        [
            Paragraph(
                "Form Teacher",
                normal_style,
            ),
            Paragraph(
                "Principal / Head of School",
                normal_style,
            ),
        ],
    ]

    signature_table = Table(
        signature_data,
        colWidths=[
            82 * mm,
            82 * mm,
        ],
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
                    3,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
            ]
        )
    )

    story.append(signature_table)

    # ---------------------------------------------------------
    # FOOTER
    # ---------------------------------------------------------

    story.append(
        Spacer(
            1,
            6,
        )
    )

    story.append(
        Paragraph(
            "This result is generated from approved academic records "
            "in the School Management System.",
            small_style,
        )
    )

    def add_page_footer(canvas, doc):
        canvas.saveState()

        width, height = A4

        canvas.setStrokeColor(
            colors.HexColor("#0b6b3a")
        )
        canvas.setLineWidth(0.5)

        canvas.line(
            12 * mm,
            10 * mm,
            width - 12 * mm,
            10 * mm,
        )

        canvas.setFont(
            "Helvetica",
            7,
        )

        canvas.setFillColor(
            colors.grey
        )

        canvas.drawString(
            12 * mm,
            6 * mm,
            "Rock Foundation Academy and College",
        )

        canvas.drawRightString(
            width - 12 * mm,
            6 * mm,
            f"Page {doc.page}",
        )

        canvas.restoreState()

    document.build(
        story,
        onFirstPage=add_page_footer,
        onLaterPages=add_page_footer,
    )

    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
    )

    response["Content-Disposition"] = (
        f'inline; filename='
        f'"result_{student.admission_number}_'
        f'{session_code}_{term_code}.pdf"'
    )

    # Prevent the browser from displaying an older cached PDF.
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response
