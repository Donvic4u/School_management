import csv
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from school.models import Student, ClassLevel, Enrollment, Term


class Command(BaseCommand):
    help = "Import students from a CSV file and create current-term enrollments."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to the CSV file"
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]

        # Find the current term
        term = Term.objects.filter(
            is_current=True
        ).select_related("session").first()

        if not term:
            self.stdout.write(
                self.style.ERROR(
                    "No current term found. Set a term as current in Django Admin."
                )
            )
            return

        self.stdout.write(
            f"Importing students into: {term.session.name} - {term.name}"
        )

        # Expected CSV columns
        required_columns = {
            "Admission No.",
            "Surname",
            "First Name",
            "Other Names",
            "Gender",
            "Class",
        }

        created = 0
        updated = 0
        enrollments_created = 0
        errors = []

        try:
            with open(csv_file, "r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)

                if not reader.fieldnames:
                    self.stdout.write(
                        self.style.ERROR("The CSV file has no header row.")
                    )
                    return

                # Normalize column names
                actual_columns = {
                    column.strip(): column
                    for column in reader.fieldnames
                    if column
                }

                missing = required_columns - set(actual_columns.keys())

                if missing:
                    self.stdout.write(
                        self.style.ERROR(
                            "Missing required columns: "
                            + ", ".join(sorted(missing))
                        )
                    )
                    return

                for row_number, row in enumerate(reader, start=2):
                    try:
                        admission_number = row["Admission No."].strip()
                        surname = row["Surname"].strip()
                        first_name = row["First Name"].strip()
                        other_names = row["Other Names"].strip()
                        gender = row["Gender"].strip().title()
                        class_name = row["Class"].strip()

                        # Basic validation
                        if not admission_number:
                            raise ValueError("Admission No. is empty.")

                        if not surname:
                            raise ValueError("Surname is empty.")

                        if not first_name:
                            raise ValueError("First Name is empty.")

                        if gender not in ("Male", "Female"):
                            raise ValueError(
                                "Gender must be Male or Female."
                            )

                        class_level = ClassLevel.objects.filter(
                            name=class_name
                        ).first()

                        if not class_level:
                            raise ValueError(
                                f"Class '{class_name}' does not exist."
                            )

                        with transaction.atomic():

                            student = Student.objects.filter(
                                admission_number=admission_number
                            ).first()

                            if student:
                                student.surname = surname
                                student.first_name = first_name
                                student.other_names = other_names
                                student.gender = gender
                                student.current_class = class_level
                                student.active = True
                                student.save()

                                updated += 1

                            else:
                                student = Student.objects.create(
                                    admission_number=admission_number,
                                    surname=surname,
                                    first_name=first_name,
                                    other_names=other_names,
                                    gender=gender,
                                    current_class=class_level,
                                    active=True,
                                )

                                created += 1

                            # Create current-term enrollment if it doesn't exist.
                            enrollment, was_created = Enrollment.objects.get_or_create(
                                student=student,
                                term=term,
                                defaults={
                                    "class_level": class_level
                                }
                            )

                            # If the enrollment already exists, update the
                            # class for the current term without affecting
                            # previous terms.
                            if not was_created and enrollment.class_level != class_level:
                                enrollment.class_level = class_level
                                enrollment.save()

                            if was_created:
                                enrollments_created += 1

                    except Exception as exc:
                        errors.append(
                            f"Row {row_number}: {exc}"
                        )

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(
                    f"File not found: {csv_file}"
                )
            )
            return

        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(
                    f"Could not read CSV file: {exc}"
                )
            )
            return

        self.stdout.write("")
        self.stdout.write("IMPORT COMPLETE")
        self.stdout.write("------------------------------")
        self.stdout.write(f"Students created: {created}")
        self.stdout.write(f"Students updated: {updated}")
        self.stdout.write(f"Enrollments created: {enrollments_created}")
        self.stdout.write(f"Errors: {len(errors)}")

        if errors:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING("IMPORT ERRORS:")
            )

            for error in errors:
                self.stdout.write(
                    self.style.WARNING(error)
                )
