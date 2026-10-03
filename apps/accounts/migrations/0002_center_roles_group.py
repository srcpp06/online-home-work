"""Centres, roles and study groups (SPEC §2).

Users made before roles existed are the superusers from `createsuperuser`: they become the
superadmin without a first-login password change. Anyone else would need a centre, which
a migration can't choose, so the migration stops and says so.
"""

import django.db.models.deletion
from django.db import migrations, models

import apps.accounts.models


def existing_users_become_superadmins(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    others = list(User.objects.filter(is_superuser=False).values_list("username", flat=True))
    if others:
        raise RuntimeError(
            "These users were made before roles and need a centre: "
            f"{', '.join(others)}. Delete them or give them a role by hand, then migrate."
        )
    User.objects.update(role="superadmin", is_staff=True, must_change_password=False)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Center",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=200, verbose_name="nomi")),
                ("slug", models.SlugField(unique=True, verbose_name="slug")),
                ("is_active", models.BooleanField(default=True, verbose_name="faol")),
            ],
            options={
                "verbose_name": "markaz",
                "verbose_name_plural": "markazlar",
                "ordering": ("name",),
            },
        ),
        migrations.AlterModelOptions(
            name="user",
            options={"verbose_name": "foydalanuvchi", "verbose_name_plural": "foydalanuvchilar"},
        ),
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", apps.accounts.models.UserManager()),
            ],
        ),
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("superadmin", "Superadmin"),
                    ("center_admin", "Markaz admini"),
                    ("teacher", "Oʻqituvchi"),
                    ("student", "Oʻquvchi"),
                ],
                default="superadmin",
                max_length=20,
                verbose_name="rol",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="accounts.center",
                verbose_name="markaz",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="directions",
            field=apps.accounts.models.DirectionsField(
                base_field=models.CharField(
                    choices=[
                        ("flutter", "Flutter"),
                        ("backend", "Backend"),
                        ("frontend", "Frontend"),
                    ],
                    max_length=20,
                ),
                blank=True,
                default=list,
                size=None,
                verbose_name="yoʻnalishlar",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(default=True, verbose_name="parolni almashtirishi kerak"),
        ),
        migrations.RunPython(existing_users_become_superadmins, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("role__in", ["superadmin", "center_admin", "teacher", "student"])
                ),
                name="accounts_user_role_valid",
                violation_error_message="Rolni tanlang.",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("center__isnull", True), ("role", "superadmin")),
                    models.Q(
                        models.Q(("role", "superadmin"), _negated=True), ("center__isnull", False)
                    ),
                    _connector="OR",
                ),
                name="accounts_user_center_matches_role",
                violation_error_message="Superadmin markazga biriktirilmaydi, boshqa rollar uchun markazni tanlang.",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("is_staff", True), ("is_superuser", True), ("role", "superadmin")),
                    models.Q(
                        models.Q(("role", "superadmin"), _negated=True),
                        ("is_staff", False),
                        ("is_superuser", False),
                    ),
                    _connector="OR",
                ),
                name="accounts_user_only_superadmin_is_staff",
                violation_error_message="Admin panelga faqat superadmin kira oladi.",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(("role", "teacher"), ("directions", []), _connector="OR"),
                name="accounts_user_directions_only_for_teachers",
                violation_error_message="Yoʻnalishlar faqat oʻqituvchiga biriktiriladi.",
            ),
        ),
        migrations.CreateModel(
            name="Group",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=200, verbose_name="nomi")),
                (
                    "show_journal_to_students",
                    models.BooleanField(
                        default=False, verbose_name="jurnal oʻquvchilarga koʻrinadi"
                    ),
                ),
                (
                    "center",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="groups",
                        to="accounts.center",
                        verbose_name="markaz",
                    ),
                ),
                (
                    "students",
                    models.ManyToManyField(
                        blank=True,
                        related_name="study_groups",
                        to="accounts.user",
                        verbose_name="oʻquvchilar",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="teaching_groups",
                        to="accounts.user",
                        verbose_name="oʻqituvchi",
                    ),
                ),
            ],
            options={
                "verbose_name": "guruh",
                "verbose_name_plural": "guruhlar",
                "ordering": ("name",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("center", "name"),
                        name="accounts_group_name_unique_in_center",
                        violation_error_message="Bu markazda shu nomli guruh bor.",
                    )
                ],
            },
        ),
    ]
