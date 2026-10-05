from django import forms

from .models import (
    Student,
    Teacher,
    Subject,
    ClassLevel,
    Enrollment,
)


# ============================================================
# STUDENT FORM
# ============================================================

class StudentForm(forms.ModelForm):

    class Meta:
        model = Student

        fields = [
            "admission_number",
            "surname",
            "first_name",
            "other_names",
            "gender",
            "phone_number",
            "email",
            "date_of_birth",
            "date_admitted",
            "current_class",
            "active",
        ]

        widgets = {
            "admission_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Admission Number",
                }
            ),

            "surname": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Surname",
                }
            ),

            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "First Name",
                }
            ),

            "other_names": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Other Names",
                }
            ),

            "gender": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Student or Parent/Guardian Phone Number",
                    "type": "tel",
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Student or Parent/Guardian Email Address",
                    "type": "email",
                }
            ),

            "date_of_birth": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "date_admitted": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "current_class": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }


# ============================================================
# STUDENT SEARCH FORM
# ============================================================

class StudentSearchForm(forms.Form):

    search = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Admission No. or student name",
            }
        ),
    )

    class_level = forms.ModelChoiceField(
        queryset=ClassLevel.objects.all().order_by("name"),
        required=False,
        empty_label="All Classes",
        label="Class",
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )

    gender = forms.ChoiceField(
        choices=[
            ("", "All Genders"),
            ("Male", "Male"),
            ("Female", "Female"),
        ],
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )

    active = forms.BooleanField(
        required=False,
        label="Active Students Only",
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )


# ============================================================
# TEACHER FORM
# ============================================================

class TeacherForm(forms.ModelForm):

    class Meta:
        model = Teacher

        fields = [
            "staff_id",
            "surname",
            "first_name",
            "other_names",
            "phone",
            "email",
            "active",
        ]

        widgets = {
            "staff_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Staff ID",
                }
            ),

            "surname": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Surname",
                }
            ),

            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "First Name",
                }
            ),

            "other_names": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Other Names",
                }
            ),

            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Phone Number",
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Email Address",
                }
            ),

            "active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }


# ============================================================
# SUBJECT FORM
# ============================================================

class SubjectForm(forms.ModelForm):

    class Meta:
        model = Subject

        fields = [
            "code",
            "name",
            "max_ca",
            "max_exam",
            "active",
        ]

        widgets = {
            "code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Subject Code",
                }
            ),

            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Subject Name",
                }
            ),

            "max_ca": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "max": 100,
                }
            ),

            "max_exam": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "max": 100,
                }
            ),

            "active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        max_ca = cleaned_data.get("max_ca")
        max_exam = cleaned_data.get("max_exam")

        if max_ca is not None and max_exam is not None:
            if max_ca + max_exam != 100:
                raise forms.ValidationError(
                    "CA and Exam maximum scores must add up to 100."
                )

        return cleaned_data


# ============================================================
# CLASS TEACHER FORM
# ============================================================

class ClassTeacherForm(forms.ModelForm):

    class Meta:
        model = ClassLevel

        fields = [
            "form_teacher",
        ]

        widgets = {
            "form_teacher": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["form_teacher"].queryset = (
            Teacher.objects
            .filter(active=True)
            .order_by("surname", "first_name")
        )

        self.fields["form_teacher"].required = False
        self.fields["form_teacher"].empty_label = "Not Assigned"

    def clean_form_teacher(self):
        teacher = self.cleaned_data.get("form_teacher")

        if teacher is None:
            return teacher

        existing_class = (
            ClassLevel.objects
            .filter(form_teacher=teacher)
            .exclude(pk=self.instance.pk)
            .first()
        )

        if existing_class:
            raise forms.ValidationError(
                f"{teacher.full_name} is already assigned as Form Teacher "
                f"for {existing_class.name}."
            )

        return teacher


# ============================================================
# ENROLLMENT FORM
# ============================================================

class EnrollmentForm(forms.ModelForm):

    class Meta:
        model = Enrollment
        fields = [
            "student",
            "class_level",
            "term",
        ]

        widgets = {
            "student": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "class_level": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "term": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        student = cleaned_data.get("student")
        term = cleaned_data.get("term")

        if student and term:
            existing = Enrollment.objects.filter(
                student=student,
                term=term,
            )

            if self.instance.pk:
                existing = existing.exclude(
                    pk=self.instance.pk
                )

            if existing.exists():
                self.add_error(
                    "term",
                    "This student is already enrolled for the selected academic term."
                )

        return cleaned_data
