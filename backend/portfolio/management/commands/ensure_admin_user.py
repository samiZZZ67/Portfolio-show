import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or repair a Django admin user from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")

        if not username:
            self.stdout.write(
                self.style.WARNING(
                    "Skipped admin bootstrap because DJANGO_SUPERUSER_USERNAME is not set."
                )
            )
            return

        User = get_user_model()
        user = User.objects.filter(username=username).first()

        if user is None and not password:
            self.stdout.write(
                self.style.WARNING(
                    "Skipped admin bootstrap because the user does not exist and "
                    "DJANGO_SUPERUSER_PASSWORD is not set."
                )
            )
            return

        created = False
        if user is None:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
            created = True
        else:
            changed = False
            if email and user.email != email:
                user.email = email
                changed = True
            if password:
                user.set_password(password)
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

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created admin user '{username}'.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Verified admin user '{username}'.")
        )
