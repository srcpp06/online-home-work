"""Sign-in and password forms, with the messages in Uzbek (docs/UI.md §8)."""

import re
from typing import Any

from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils.html import format_html

from apps.accounts.avatars import avatar_from_upload
from apps.accounts.models import Group, Role, User, check_students
from apps.ui.widgets import UploadZone

STAFF_ROLES = frozenset({Role.TEACHER, Role.CENTER_MANAGER, Role.CENTER_ADMIN})


class LoginForm(AuthenticationForm):
    """One of the site's two doors: students sign in at theirs, staff at theirs.

    Someone at the wrong door is told which one is theirs, but only after a correct
    password. The superadmin has no door here (only /admin/) and gets the plain refusal.
    """

    error_messages = {  # noqa: RUF012 -- Django's documented form attribute
        "invalid_login": "Login yoki parol notoʻgʻri. Qayta kiriting.",
        "inactive": "Bu hisob oʻchirilgan. Markaz administratoriga murojaat qiling.",
        "center_inactive": "Markazingiz hozir faol emas. Markaz administratoriga murojaat qiling.",
    }

    def __init__(self, *args: Any, for_staff: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.for_staff = for_staff
        self.fields["username"].label = "Login"
        self.fields["password"].label = "Parol"
        style_fields(self)

    def confirm_login_allowed(self, user: User) -> None:  # type: ignore[override]
        super().confirm_login_allowed(user)
        if user.role == Role.SUPERADMIN:
            raise self.get_invalid_login_error()
        if (user.role in STAFF_ROLES) != self.for_staff:
            raise forms.ValidationError(self._wrong_door(user), code="wrong_door")
        if user.center is not None and not user.center.is_active:
            raise forms.ValidationError(
                self.error_messages["center_inactive"], code="center_inactive"
            )

    def _wrong_door(self, user: User) -> str:
        if user.role in STAFF_ROLES:
            return format_html(
                'Bu xodim hisobi. <a href="{}">Xodimlar uchun kirish</a> sahifasidan kiring.',
                reverse("accounts:staff_login"),
            )
        return format_html(
            'Bu oʻquvchi hisobi. <a href="{}">Oʻquvchilar uchun kirish</a> sahifasidan kiring.',
            reverse("accounts:login"),
        )


class AdminLoginForm(AdminAuthenticationForm):
    """/admin/ is the superadmin's; everyone else is pointed to the site's sign-in."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.error_messages = {
            **self.error_messages,
            "invalid_login": format_html(
                "Login yoki parol notoʻgʻri. Admin panelga faqat superadmin kiradi; markaz "
                'xodimlari, oʻqituvchi va oʻquvchilar <a href="{}">saytning kirish '
                "sahifalaridan</a> kiradi.",
                reverse("accounts:home"),
            ),
        }


class NewPasswordForm(PasswordChangeForm):
    """Changing the password; on first sign-in the old one is the temporary password."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Hozirgi parol"
        self.fields["new_password1"].label = "Yangi parol"
        self.fields["new_password2"].label = "Yangi parol (yana bir marta)"
        rules = "Kamida 8 belgi; faqat raqamdan iborat, oddiy yoki loginga oʻxshash boʻlmasin."
        self.fields["new_password1"].help_text = rules
        self.fields["new_password2"].help_text = "Yangi parolni takrorlang."
        style_fields(self)

    def clean_new_password1(self) -> str:
        new = self.cleaned_data["new_password1"]
        if new and new == self.data.get("old_password"):
            raise forms.ValidationError(
                "Yangi parol hozirgisidan farq qilishi kerak.", code="password_unchanged"
            )
        return new

    def save(self, commit: bool = True) -> User:
        user: User = self.user  # type: ignore[assignment]
        user.must_change_password = False
        return super().save(commit)  # type: ignore[return-value]


_TEXT_INPUT_CLASS = "field mt-1"


def style_fields(form: forms.BaseForm) -> None:
    """Text inputs get the design system's look; checkboxes keep the browser's."""
    for field in form.fields.values():
        if isinstance(field.widget, forms.TextInput | forms.Select | forms.PasswordInput):
            field.widget.attrs.setdefault("class", _TEXT_INPUT_CLASS)


class PersonForm(forms.ModelForm):
    """A centre's teacher, student or manager. The role and the centre come from the page."""

    class Meta:
        model = User
        fields = ("last_name", "first_name", "username", "directions", "is_active")
        labels = {  # noqa: RUF012 -- Django's documented form attribute
            "last_name": "Familiya",
            "first_name": "Ism",
            "username": "Login",
            "directions": "Yoʻnalishlar",
            "is_active": "Faol (oʻchirilsa, tizimga kira olmaydi)",
        }
        help_texts = {  # noqa: RUF012 -- Django's documented form attribute
            "username": "Kirish uchun. Harflar, raqamlar va @ . + - _ belgilari, 150 tagacha.",
            "directions": "Oʻqituvchi faqat shu yoʻnalishlarning topshiriqlarini yarata oladi.",
        }

    def __init__(self, *args: Any, creating: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        if self.instance.role != Role.TEACHER:
            del self.fields["directions"]
        else:
            self.fields["directions"].required = True
        if creating:
            del self.fields["is_active"]
        style_fields(self)


class GroupForm(forms.ModelForm):
    """A study group of the user's centre: only its teachers and students are offered."""

    class Meta:
        model = Group
        fields = ("name", "teacher", "students", "show_journal_to_students")
        labels = {  # noqa: RUF012 -- Django's documented form attribute
            "name": "Nomi",
            "teacher": "Oʻqituvchi",
            "students": "Oʻquvchilar",
            "show_journal_to_students": "Jurnal oʻquvchilarga koʻrinadi",
        }
        widgets = {"students": forms.CheckboxSelectMultiple}  # noqa: RUF012

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        center = self.instance.center
        people = User.objects.filter(center=center, is_active=True).order_by(
            "last_name", "first_name", "username"
        )
        self.fields["teacher"].queryset = people.filter(role=Role.TEACHER)
        self.fields["teacher"].empty_label = "Oʻqituvchini tanlang"
        self.fields["students"].queryset = people.filter(role=Role.STUDENT)
        self.fields["students"].required = False
        for name in ("teacher", "students"):
            self.fields[name].label_from_instance = _person_label
        style_fields(self)

    def clean_students(self) -> Any:
        students = self.cleaned_data["students"]
        check_students(self.instance.center_id, students)
        return students


def _person_label(user: User) -> str:
    return (
        f"{user.display_name} ({user.username})"
        if user.last_name or user.first_name
        else user.username
    )


class ProfileForm(forms.ModelForm):
    """What a person says about themselves; the name, login and role are the admin's."""

    picture = forms.FileField(
        label="Rasm",
        required=False,
        widget=UploadZone(
            attrs={"accept": "image/png,image/jpeg,image/webp,image/gif"},
            prompt="Rasmni shu yerga tashlang",
        ),
        help_text="JPG, PNG yoki WebP, 5 MB gacha. Kvadrat qilib qirqiladi.",
    )
    remove_picture = forms.BooleanField(label="Rasmni olib tashlash", required=False)

    class Meta:
        model = User
        fields = ("phone", "telegram", "bio")
        labels = {  # noqa: RUF012 -- Django's documented form attribute
            "phone": "Telefon",
            "telegram": "Telegram",
            "bio": "Oʻzim haqimda",
        }
        help_texts = {  # noqa: RUF012
            "phone": "Masalan: +998 90 123 45 67",
            "telegram": "Foydalanuvchi nomi, masalan: @erkin_dev",
            "bio": "500 belgigacha: nimani oʻrganyapsiz yoki oʻrgatasiz, qiziqishlaringiz.",
        }
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}  # noqa: RUF012

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.picture_data: bytes | None = None
        if not self.instance.avatar:
            del self.fields["remove_picture"]
        style_fields(self)
        self.fields["bio"].widget.attrs["class"] = "field mt-1"

    def clean_phone(self) -> str:
        phone = self.cleaned_data["phone"].strip()
        if phone and not _PHONE.fullmatch(phone):
            raise forms.ValidationError(
                "Telefon raqamini raqamlar bilan yozing, masalan: +998 90 123 45 67."
            )
        return phone

    def clean_telegram(self) -> str:
        name = self.cleaned_data["telegram"].strip().removeprefix("@")
        if name and not _TELEGRAM.fullmatch(name):
            raise forms.ValidationError(
                "Telegram nomi 5 dan 32 belgigacha: lotin harflari, raqamlar va _, "
                "harf bilan boshlanadi."
            )
        return name

    def clean_picture(self) -> Any:
        upload = self.cleaned_data.get("picture")
        if upload:
            self.picture_data = avatar_from_upload(upload)
        return upload

    def save(self, commit: bool = True) -> User:
        user: User = super().save(commit=False)
        if self.picture_data is not None or self.cleaned_data.get("remove_picture"):
            user.avatar.delete(save=False)
        if self.picture_data is not None:
            user.avatar.save("avatar.webp", ContentFile(self.picture_data), save=False)
        if commit:
            user.save()
        return user


_PHONE = re.compile(r"\+?[0-9][0-9 ()-]{6,19}")
_TELEGRAM = re.compile(r"[A-Za-z][A-Za-z0-9_]{4,31}")
