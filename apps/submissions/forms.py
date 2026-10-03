"""The student's upload form."""

from typing import Any

from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.ui.widgets import UploadZone
from judge.packaging.zip_validator import ZipRejected, check_size


class SubmitForm(forms.Form):
    archive = forms.FileField(label="Yechim (zip)", widget=UploadZone)

    def __init__(self, *args: Any, student_paths: tuple[str, ...], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        folders = ", ".join(f"{path}/" for path in student_paths)
        self.fields["archive"].help_text = (
            f"Loyihangizni zip qiling. Faqat {folders} tekshiriladi: "
            "kutubxonalar va testlarni oʻqituvchi belgilaydi."
        )

    def clean_archive(self) -> UploadedFile:
        upload: UploadedFile = self.cleaned_data["archive"]
        try:
            check_size(upload.size or 0, settings.SUBMISSION_ZIP_LIMITS)
        except ZipRejected as error:
            raise forms.ValidationError(str(error)) from None
        return upload
