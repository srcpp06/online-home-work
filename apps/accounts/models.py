from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """The platform's user (SPEC §2). Roles, centre and groups come with the next task.

    A custom model from the first migration: Django can't switch AUTH_USER_MODEL later
    without rebuilding the database.
    """
