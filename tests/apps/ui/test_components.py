"""Icons and status badges (docs/UI.md §5, §9): a status is never colour alone."""

import re

import pytest
from django.template import Context, Template

from apps.ui.status import STATUSES, Tone, status_look
from apps.ui.templatetags.ui import ICONS_DIR, icon
from judge.core.verdict import Verdict
from judge.env import REPO_ROOT

GLOSSARY_ROW = re.compile(r"^\| (?P<name>[a-z_]+) \| (?P<label>[^|]+) \|$", re.MULTILINE)


def render(source: str) -> str:
    return Template("{% load ui %}" + source).render(Context())


def test_every_verdict_and_queue_state_has_a_look() -> None:
    assert set(STATUSES) == {*Verdict, "queued", "running"}


def test_labels_are_the_ui_md_glossary() -> None:
    glossary = {
        m["name"]: m["label"].strip()
        for m in GLOSSARY_ROW.finditer((REPO_ROOT / "docs" / "UI.md").read_text())
    }

    assert {status: look.label for status, look in STATUSES.items()} == {
        status: glossary[status] for status in STATUSES
    }


def test_every_status_icon_exists() -> None:
    assert all((ICONS_DIR / f"{look.icon}.svg").is_file() for look in STATUSES.values())
    assert (ICONS_DIR / "LICENSE.txt").is_file()


@pytest.mark.parametrize(("failed_test", "label"), [(3, "3-testda xato"), (None, "Testda xato")])
def test_wrong_answer_names_the_test(failed_test: int | None, label: str) -> None:
    assert status_look("wrong_answer", failed_test).label == label


def test_badge_has_icon_words_and_tone() -> None:
    html = render('{% status_badge "time_limit" %}')

    assert 'class="status tone-warn"' in html
    assert '<svg class="size-5"' in html
    assert 'width="20" height="20"' in html  # icon-sized even when the CSS is missing
    assert 'aria-hidden="true"' in html
    assert "<span>Vaqt limiti oshdi</span>" in html


def test_badge_for_a_failed_test() -> None:
    html = render('{% status_badge "wrong_answer" 3 %}')

    assert f"tone-{Tone.FAIL}" in html
    assert "3-testda xato" in html


def test_icon_escapes_its_class() -> None:
    assert '<svg class="size-4 &quot;&gt;"' in str(icon("check", 'size-4 ">'))


@pytest.mark.parametrize("name", ["no-such-icon", "../apps", "Check", ""])
def test_unknown_or_bad_icon_names_fail_loudly(name: str) -> None:
    with pytest.raises(ValueError, match="icon"):
        icon(name)


def test_upload_zone_works_without_javascript() -> None:
    from django import forms

    from apps.ui.widgets import UploadZone

    class Form(forms.Form):
        package = forms.FileField(widget=UploadZone)

    html = Form().as_div()

    assert 'type="file"' in html
    assert 'name="package"' in html
    assert 'accept=".zip,application/zip"' in html
    assert "<label" in html and "data-upload" in html  # clicking the zone opens the picker
    assert "kompyuterdan tanlang" in html
