"""Django admin for the superadmin (SPEC §1): only role superadmin is staff."""

from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group as PermissionGroup

from apps.accounts.forms import AdminLoginForm
from apps.accounts.models import Center, Group, User, check_students

# Django's permission groups are unused: what a user may do comes from their role.
admin.site.unregister(PermissionGroup)
admin.site.site_header = "Online Home Work — boshqaruv"
admin.site.site_title = "Online Home Work"
admin.site.index_title = "Boshqaruv"
admin.site.login_form = AdminLoginForm


@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}  # noqa: RUF012 -- Django's admin option


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "center", "is_active")
    list_filter = ("role", "center", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Shaxsiy maʼlumotlar", {"fields": ("first_name", "last_name", "email")}),
        ("Rol", {"fields": ("role", "center", "directions", "must_change_password")}),
        ("Holat", {"fields": ("is_active", "last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "usable_password", "password1", "password2"),
            },
        ),
        ("Rol", {"fields": ("role", "center", "directions")}),
    )
    readonly_fields = ("last_login", "date_joined")


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ("center", "name", "teacher", "students", "show_journal_to_students")

    def clean(self) -> dict[str, Any]:
        data = super().clean()
        center, students = data.get("center"), data.get("students")
        if center is not None and students is not None:
            try:
                check_students(center.pk, students)
            except forms.ValidationError as error:
                self.add_error("students", error)
        return data


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    form = GroupForm
    list_display = ("name", "center", "teacher")
    list_filter = ("center",)
    search_fields = ("name",)
    filter_horizontal = ("students",)
