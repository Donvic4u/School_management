from django.contrib import messages
from django.shortcuts import render

from .models import (
    AcademicSession,
    Enrollment,
    ResultAccess,
    ResultPublication,
    SchoolProfile,
    Term,
)
from .result_views import build_class_results


def public_result_portal(request):
    sessions = AcademicSession.objects.all().order_by("-name")

    school_profile = SchoolProfile.objects.first()

    selected_session_id = request.POST.get("session", "")
    selected_term_id = request.POST.get("term", "")

    selected_session = None
    selected_term = None
    result = None
    student = None
    enrollment = None
    publication = None

    if selected_session_id:
        selected_session = sessions.filter(
            id=selected_session_id
        ).first()

    if selected_session:
        terms = Term.objects.filter(
            session=selected_session
        ).order_by("id")
    else:
        terms = Term.objects.none()

    if selected_term_id:
        selected_term = terms.filter(
            id=selected_term_id
        ).first()

    if request.method == "POST":
        admission_number = request.POST.get(
            "admission_number",
            ""
        ).strip()

        pin = request.POST.get(
            "pin",
            ""
        ).strip()

        if not admission_number or not pin:
            messages.error(
                request,
                "Please enter your admission number and result PIN."
            )

        elif selected_session is None:
            messages.error(
                request,
                "Please select an academic session."
            )

        elif selected_term is None:
            messages.error(
                request,
                "Please select a term."
            )

        else:
            access = (
                ResultAccess.objects
                .select_related("student")
                .filter(
                    student__admission_number__iexact=admission_number,
                    active=True,
                )
                .first()
            )

            if access is None:
                messages.error(
                    request,
                    "Invalid admission number or result PIN."
                )

            elif access.pin != pin:
                messages.error(
                    request,
                    "Invalid admission number or result PIN."
                )

            else:
                student = access.student

                enrollment = (
                    Enrollment.objects
                    .filter(
                        student=student,
                        term=selected_term,
                    )
                    .select_related(
                        "student",
                        "class_level",
                        "term",
                    )
                    .first()
                )

                if enrollment is None:
                    messages.error(
                        request,
                        "No result is available for this student "
                        "for the selected session and term."
                    )

                else:
                    publication = (
                        ResultPublication.objects
                        .filter(
                            session=selected_term.session,
                            term=selected_term,
                            class_level=enrollment.class_level,
                            published=True,
                        )
                        .first()
                    )

                    if publication is None:
                        messages.error(
                            request,
                            "This result has not been published yet."
                        )

                    else:
                        class_results = build_class_results(
                            enrollment.class_level,
                            selected_term,
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
                            messages.error(
                                request,
                                "No approved result is available "
                                "for this student."
                            )
                        else:
                            result = student_data

                            # Store the successful public-result
                            # verification in the Django session.
                            request.session["public_result_access"] = {
                                "student_id": student.id,
                                "term_id": selected_term.id,
                                "session_id": selected_term.session.id,
                            }

    context = {
        "school_profile": school_profile,
        "sessions": sessions,
        "terms": terms,
        "selected_session": selected_session,
        "selected_term": selected_term,
        "selected_session_id": selected_session_id,
        "selected_term_id": selected_term_id,
        "result": result,
        "student": student,
        "enrollment": enrollment,
        "publication": publication,
    }

    return render(
        request,
        "school/public_result_portal.html",
        context,
    )
