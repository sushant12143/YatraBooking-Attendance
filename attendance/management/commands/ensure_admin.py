import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the admin login from ADMIN_USERNAME / ADMIN_PASSWORD env vars (set ADMIN_RESET=1 to reset the password)."

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not username or not password:
            self.stdout.write("ensure_admin: ADMIN_USERNAME / ADMIN_PASSWORD not set - skipped.")
            return
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username, defaults={"is_staff": True, "is_superuser": True}
        )
        if created or os.environ.get("ADMIN_RESET") == "1":
            user.set_password(password)
            user.is_staff = user.is_superuser = True
            user.save()
            self.stdout.write("ensure_admin: admin '%s' %s." % (username, "created" if created else "password reset"))
        else:
            self.stdout.write("ensure_admin: admin '%s' already exists." % username)
