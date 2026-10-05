import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the initial production superuser from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME")
        email = os.environ.get("DJANGO_ADMIN_EMAIL")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_ADMIN_USERNAME or DJANGO_ADMIN_PASSWORD not set. "
                    "Skipping initial admin creation."
                )
            )
            return

        User = get_user_model()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email or "",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Initial administrator '{username}' created successfully."
                )
            )
        else:
            changed = False

            if email and user.email != email:
                user.email = email
                changed = True

            if not user.is_staff:
                user.is_staff = True
                changed = True

            if not user.is_superuser:
                user.is_superuser = True
                changed = True

            if not user.is_active:
                user.is_active = True
                changed = True

            if changed:
                user.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrator '{username}' already exists. "
                    "Permissions verified."
                )
            )
