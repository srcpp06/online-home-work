"""Sign-in and password forms, with the messages in Uzbek (docs/UI.md §8)."""

from typing import Any

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from apps.accounts.models import Group, Role, User, check_students


class LoginForm(AuthenticationForm):
    error_messages = {  # noqa: RUF012 -- Django's documented form attribute
        "invalid_login": "Login yoki parol notoʻgʻri. Qayta kiriting.",
        "inactive": "Bu hisob oʻchirilgan. Markaz administratoriga murojaat qiling.",
        "center_inactive": "Markazingiz hozir faol emas. Markaz administratoriga murojaat qiling.",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Login"
        self.fields["password"].label = "Parol"
        _style(self)

    def confirm_login_allowed(self, user: User) -> None:  # type: ignore[override]
        super().confirm_login_allowed(user)
        if user.center is not None and not user.center.is_active:
            raise forms.ValidationError(
                self.error_messages["center_inactive"], code="center_inactive"
            )


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
        _style(self)

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


def _style(form: forms.BaseForm) -> None:
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
        _style(self)


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
        _style(self)

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
