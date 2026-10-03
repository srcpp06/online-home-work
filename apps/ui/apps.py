from django.apps import AppConfig


class UiConfig(AppConfig):
    """The design system's code: icons, status badges and the styleguide (docs/UI.md)."""

    name = "apps.ui"
    label = "ui"
    verbose_name = "Dizayn tizimi"

    def ready(self) -> None:
        from apps.ui import checks  # noqa: F401 -- registers the system check
