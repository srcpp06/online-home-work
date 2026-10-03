"""Teacher forms: a task with its package, a new version, publishing and assigning."""

from typing import Any

from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import MaxValueValidator, MinValueValidator

from apps.accounts.forms import style_fields
from apps.accounts.models import Group, User
from apps.tasks.models import Assignment, RunnerProfile, Task, TaskVersion
from apps.ui.widgets import UploadZone
from judge.packaging.starter import CheckItem, package_checklist
from judge.packaging.task_package import PackageInvalid, TaskPackage, read_task_package
from judge.packaging.zip_validator import ArchiveFile, ZipRejected, validate_zip

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


class PackageField(forms.FileField):
    widget = UploadZone


class _PackageMixin:
    """Reads and checks the uploaded package; the form keeps what it found for the page."""

    archive_files: list[ArchiveFile]  # not `files`: Django forms use that name for uploads
    package: TaskPackage
    checklist: list[CheckItem]

    def clean_package(self) -> UploadedFile:
        upload: UploadedFile = self.cleaned_data["package"]  # type: ignore[attr-defined]
        self.checklist = []
        try:
            self.archive_files = validate_zip(upload, settings.TASK_ZIP_LIMITS).read()
            self.checklist = package_checklist(self.archive_files)
            self.package = read_task_package(self.archive_files)
        except ZipRejected as error:
            raise forms.ValidationError(str(error)) from None
        except PackageInvalid as error:
            raise forms.ValidationError(error.errors) from None
        return upload


class TaskForm(_PackageMixin, forms.ModelForm):
    package = PackageField(
        label="Paket (zip)",
        help_text="pubspec.yaml, solution/lib, test/public va test/hidden bilan; "
        "starter/ ixtiyoriy.",
    )

    class Meta:
        model = Task
        fields = ("profile", "title", "statement_md")
        labels = {  # noqa: RUF012 -- Django's documented form attribute
            "profile": "Profil",
            "title": "Nomi",
            "statement_md": "Shart",
        }
        help_texts = {  # noqa: RUF012
            "statement_md": "Markdown: **qalin**, `kod`, roʻyxatlar, jadvallar, "
            "```dart kod bloklari```.",
        }
        widgets = {  # noqa: RUF012
            "profile": forms.RadioSelect,
            "statement_md": forms.Textarea(attrs={"rows": 14}),
        }

    def __init__(self, *args: Any, teacher: User, creating: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["profile"].queryset = RunnerProfile.objects.for_user(teacher)
        self.fields["profile"].empty_label = None
        if not creating:
            del self.fields["profile"]
            del self.fields["package"]
        style_fields(self)
        self.fields["statement_md"].widget.attrs["class"] = "field mt-1 font-mono text-sm"


class VersionForm(_PackageMixin, forms.Form):
    package = PackageField(label="Yangi paket (zip)")


class PublishForm(forms.Form):
    time_limit_s = forms.IntegerField(label="Vaqt limiti, soniya")

    def __init__(self, *args: Any, version: TaskVersion, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        profile = version.task.profile.judge_profile()
        field = self.fields["time_limit_s"]
        field.min_value, field.max_value = profile.min_time_s, profile.max_time_s
        field.validators += [
            MinValueValidator(profile.min_time_s),
            MaxValueValidator(profile.max_time_s),
        ]
        field.widget.attrs.update(min=profile.min_time_s, max=profile.max_time_s)
        field.help_text = (
            f"Tavsiya: {version.time_limit_s} s (oʻqituvchi yechimi vaqtidan hisoblangan). "
            f"Ruxsat: {profile.min_time_s} dan {profile.max_time_s} gacha."
        )
        field.initial = version.time_limit_s
        style_fields(self)
        field.widget.attrs["class"] = "field mt-1 max-w-40"


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ("group", "opens_at", "deadline", "allow_late", "max_attempts")
        labels = {  # noqa: RUF012
            "group": "Guruh",
            "opens_at": "Ochilish vaqti",
            "deadline": "Muddat",
            "allow_late": "Muddatdan keyin ham yuborish mumkin (kechikkan deb belgilanadi)",
            "max_attempts": "Urinishlar limiti",
        }
        help_texts = {  # noqa: RUF012
            "deadline": "Boʻsh qolsa, muddatsiz.",
            "max_attempts": "Boʻsh qolsa, cheksiz. Rad etilgan va tizim xatosi bergan "
            "yechimlar hisoblanmaydi.",
        }
        widgets = {  # noqa: RUF012
            "opens_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=_DATETIME_FORMAT
            ),
            "deadline": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=_DATETIME_FORMAT
            ),
        }

    def __init__(self, *args: Any, teacher: User, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        task = self.instance.task
        self.fields["group"].queryset = (
            Group.objects.for_user(teacher)
            .filter(center_id=task.center_id)
            .exclude(assignments__task=task)
            .order_by("name")
        )
        self.fields["group"].empty_label = "Guruhni tanlang"
        for name in ("opens_at", "deadline"):
            self.fields[name].input_formats = [_DATETIME_FORMAT]
        style_fields(self)
        for name in ("opens_at", "deadline"):
            self.fields[name].widget.attrs["class"] = "field mt-1 max-w-64"
