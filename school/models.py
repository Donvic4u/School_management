from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


# ============================================================
# SCHOOL PROFILE
# ============================================================

class SchoolProfile(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    motto = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


# ============================================================
# ACADEMIC SESSION
# ============================================================

class AcademicSession(models.Model):
    name = models.CharField(max_length=20, unique=True)
    is_current = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicSession.objects.exclude(pk=self.pk).update(
                is_current=False
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ============================================================
# TERM
# ============================================================

class Term(models.Model):

    FIRST = "First Term"
    SECOND = "Second Term"
    THIRD = "Third Term"

    TERM_CHOICES = [
        (FIRST, "First Term"),
        (SECOND, "Second Term"),
        (THIRD, "Third Term"),
    ]

    name = models.CharField(
        max_length=20,
        choices=TERM_CHOICES
    )

    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="terms"
    )

    is_current = models.BooleanField(default=False)

    class Meta:
        unique_together = ("session", "name")
        ordering = ["session", "id"]

    def save(self, *args, **kwargs):
        if self.is_current:
            Term.objects.filter(
                session=self.session
            ).exclude(
                pk=self.pk
            ).update(
                is_current=False
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.session.name} - {self.name}"


# ============================================================
# CLASS LEVEL
# ============================================================

class ClassLevel(models.Model):

    name = models.CharField(
        max_length=50,
        unique=True
    )

    form_teacher = models.ForeignKey(
        "Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classes"
    )

    def __str__(self):
        return self.name


# ============================================================
# SUBJECT
# ============================================================

class Subject(models.Model):

    code = models.CharField(
        max_length=20,
        unique=True
    )

    name = models.CharField(
        max_length=100,
        unique=True
    )

    max_ca = models.PositiveIntegerField(
        default=30
    )

    max_exam = models.PositiveIntegerField(
        default=70
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return self.name



# ============================================================
# CLASS SUBJECT
# ============================================================

class ClassSubject(models.Model):
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        related_name="class_subjects",
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="class_subjects",
    )

    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("class_level", "subject")
        ordering = ["class_level__name", "subject__name"]

    def __str__(self):
        return f"{self.class_level.name} - {self.subject.name}"


# ============================================================
# TEACHER
# ============================================================

class Teacher(models.Model):

    staff_id = models.CharField(
        max_length=50,
        unique=True
    )

    surname = models.CharField(
        max_length=100
    )

    first_name = models.CharField(
        max_length=100
    )

    other_names = models.CharField(
        max_length=100,
        blank=True
    )

    phone = models.CharField(
        max_length=50,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    active = models.BooleanField(
        default=True
    )

    @property
    def full_name(self):
        return f"{self.surname} {self.first_name} {self.other_names}".strip()

    def __str__(self):
        return f"{self.staff_id} - {self.full_name}"


# ============================================================
# STUDENT
# ============================================================

class Student(models.Model):

    admission_number = models.CharField(
        max_length=50,
        unique=True
    )

    surname = models.CharField(
        max_length=100
    )

    first_name = models.CharField(
        max_length=100
    )

    other_names = models.CharField(
        max_length=100,
        blank=True
    )

    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
    ]

    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Student or parent/guardian mobile number for SMS results."
    )

    email = models.EmailField(
        blank=True,
        default="",
        help_text="Student or parent/guardian email address for result delivery."
    )

    login_pin = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Hashed PIN used for student portal login."
    )

    student_login_active = models.BooleanField(
        default=True,
        help_text="Whether this student can access the student portal."
    )

    passport_photo = models.ImageField(
        upload_to="student_passports/",
        blank=True,
        null=True,
        help_text="Student passport photograph.",
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True
    )

    date_admitted = models.DateField(
        null=True,
        blank=True
    )

    current_class = models.ForeignKey(
        ClassLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students"
    )

    active = models.BooleanField(
        default=True
    )

    @property
    def full_name(self):
        return f"{self.surname} {self.first_name} {self.other_names}".strip()

    def __str__(self):
        return f"{self.admission_number} - {self.full_name}"


# ============================================================
# ENROLLMENT
# ============================================================

class Enrollment(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="enrollments"
    )

    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.PROTECT,
        related_name="enrollments"
    )

    term = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        related_name="enrollments"
    )

    FORM_TEACHER_COMMENT_CHOICES = [
        (
            "Excellent Conduct",
            "Excellent Conduct — Consistently well-behaved, respectful and responsible.",
        ),
        (
            "Good Conduct",
            "Good Conduct — Generally well-behaved, respectful and cooperative.",
        ),
        (
            "Fair Conduct",
            "Fair Conduct — Usually well-behaved but requires occasional guidance and correction.",
        ),
        (
            "Needs Improvement",
            "Needs Improvement — Requires closer guidance to improve conduct, discipline and cooperation.",
        ),
    ]

    form_teacher_comment = models.CharField(
        max_length=30,
        choices=FORM_TEACHER_COMMENT_CHOICES,
        blank=True,
        default="",
        help_text="Behaviour-only comment selected by the Form Teacher.",
    )

    ACADEMIC_PERFORMANCE_COMMENT_CHOICES = [
        (
            "A",
            "Excellent academic performance. The student has demonstrated outstanding understanding, effort and achievement. Keep up the excellent work.",
        ),
        (
            "B",
            "Very good academic performance. The student has shown strong understanding and consistent effort. Greater focus can lead to even better achievement.",
        ),
        (
            "C",
            "Satisfactory academic performance. The student shows reasonable understanding, but more effort, concentration and consistent study are needed for better results.",
        ),
        (
            "D",
            "Fair academic performance. The student needs to put in more effort, study more regularly and improve concentration in order to achieve better results.",
        ),
        (
            "E_F",
            "Academic performance needs significant improvement. The student should work harder, develop better study habits and seek guidance where necessary.",
        ),
    ]

    academic_performance_comment = models.CharField(
        max_length=10,
        choices=ACADEMIC_PERFORMANCE_COMMENT_CHOICES,
        blank=True,
        default="",
        help_text="Academic performance comment selected by the Form Teacher based on the student's overall grade.",
    )

    class Meta:
        unique_together = ("student", "term")

    def __str__(self):
        return (
            f"{self.student.full_name} - "
            f"{self.class_level.name} - "
            f"{self.term}"
        )


# ============================================================
# SCORE
# ============================================================

class Score(models.Model):

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="scores"
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="scores"
    )

    # --------------------------------------------------------
    # CONTINUOUS ASSESSMENT
    # CA 1 = 10 marks
    # CA 2 = 10 marks
    # CA 3 = 10 marks
    # Total CA = 30 marks
    # --------------------------------------------------------

    ca1_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(10)
        ]
    )

    ca2_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(10)
        ]
    )

    ca3_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(10)
        ]
    )

    # --------------------------------------------------------
    # EXAMINATION
    # Maximum = 70
    # --------------------------------------------------------

    exam_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(70)
        ]
    )

    submitted = models.BooleanField(
        default=False
    )

    approved = models.BooleanField(
        default=False
    )

    class Meta:
        unique_together = ("enrollment", "subject")

    @property
    def ca_total(self):
        return (
            self.ca1_score
            + self.ca2_score
            + self.ca3_score
        )

    @property
    def total(self):
        return self.ca_total + self.exam_score

    def __str__(self):
        return (
            f"{self.enrollment.student.full_name} - "
            f"{self.subject.name}"
        )


# ============================================================
# GRADE SCALE
# ============================================================

class GradeScale(models.Model):

    minimum_score = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    maximum_score = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    grade = models.CharField(
        max_length=5
    )

    remark = models.CharField(
        max_length=100
    )

    class Meta:
        ordering = ["-minimum_score"]

    def __str__(self):
        return (
            f"{self.minimum_score}-"
            f"{self.maximum_score}: "
            f"{self.grade}"
        )



class Attendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),
        ("EXCUSED", "Excused"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendance_records"
    )

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="attendance_records"
    )

    date = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PRESENT"
    )

    marked_by = models.ForeignKey(
        "TeacherAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_marked"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"],
                name="unique_student_attendance_date"
            )
        ]
        ordering = ["student__surname", "student__first_name"]

    def __str__(self):
        return f"{self.student.full_name} - {self.date} - {self.status}"

class TeacherAccount(models.Model):
    teacher = models.OneToOneField(
        Teacher,
        on_delete=models.CASCADE,
        related_name="account"
    )
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="teacher_account"
    )
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.teacher.full_name} - {self.user.username}"


class TeachingAssignment(models.Model):
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="teaching_assignments"
    )
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        related_name="teaching_assignments"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="teaching_assignments"
    )
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("teacher", "class_level", "subject")
        ordering = [
            "teacher__surname",
            "teacher__first_name",
            "class_level__name",
            "subject__name",
        ]

    def __str__(self):
        return (
            f"{self.teacher.full_name} - "
            f"{self.class_level.name} - "
            f"{self.subject.name}"
        )

# ============================================================
# RESULT PUBLICATION
# ============================================================

class ResultPublication(models.Model):

    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="result_publications"
    )

    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name="result_publications"
    )

    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        related_name="result_publications"
    )

    published = models.BooleanField(default=False)

    published_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        unique_together = (
            "session",
            "term",
            "class_level",
        )
        ordering = [
            "session__name",
            "term__id",
            "class_level__name",
        ]

    def __str__(self):
        status = "Published" if self.published else "Unpublished"
        return (
            f"{self.session.name} - "
            f"{self.term.name} - "
            f"{self.class_level.name} - "
            f"{status}"
        )



class ResultAccess(models.Model):
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name="result_access",
    )

    pin = models.CharField(
        max_length=20,
        help_text="PIN used by the student/parent to access published results.",
    )

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "Active" if self.active else "Inactive"
        return f"{self.student.admission_number} - {status}"
