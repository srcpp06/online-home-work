"""Form widgets of the design system."""

from django import forms


class UploadZone(forms.FileInput):
    """A file drop zone with a button (docs/UI.md §5). Without JavaScript it is a plain file
    picker; static/js/upload.js adds drag and drop and shows the name and size before
    anything is sent."""

    template_name = "ui/widgets/upload_zone.html"

    def __init__(
        self, attrs: dict[str, str] | None = None, prompt: str = "Zip faylni shu yerga tashlang"
    ) -> None:
        super().__init__({"accept": ".zip,application/zip", **(attrs or {})})
        self.prompt = prompt

    def get_context(
        self, name: str, value: object, attrs: dict[str, str] | None
    ) -> dict[str, object]:
        context = super().get_context(name, value, attrs)
        context["widget"]["prompt"] = self.prompt
        return context
