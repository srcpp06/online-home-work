"""Every input of our forms carries the design system's look (an unstyled input is invisible:
Tailwind's reset removes the browser border)."""

import re

import pytest

from apps.accounts.forms import GroupForm, LoginForm, NewPasswordForm, PersonForm
from apps.accounts.models import Group, Role, User
from tests.apps.world import World

INPUT = re.compile(r"<(?:input|select)\b[^>]*>")
UNSTYLED_TYPES = ('type="checkbox"', 'type="hidden"')


def unstyled_inputs(html: str) -> list[str]:
    return [
        tag
        for tag in INPUT.findall(html)
        if not any(t in tag for t in UNSTYLED_TYPES) and 'class="field' not in tag
    ]


@pytest.mark.django_db
def test_every_text_input_and_select_is_styled(world: World) -> None:
    forms = [
        LoginForm(),
        NewPasswordForm(world.a.student),
        PersonForm(instance=User(role=Role.TEACHER, center=world.a.center), creating=True),
        PersonForm(instance=world.a.student, creating=False),
        GroupForm(instance=Group(center=world.a.center)),
    ]

    for form in forms:
        assert not unstyled_inputs(form.as_div()), type(form).__name__
