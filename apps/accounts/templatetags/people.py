"""{% avatar person %}: the person's picture, or their initials where there is none."""

from pathlib import PurePosixPath

from django import template
from django.urls import reverse

from apps.accounts.models import User

register = template.Library()


@register.inclusion_tag("accounts/_avatar.html")
def avatar(person: User, size: str = "md") -> dict[str, object]:
    url = ""
    if person.avatar:
        version = PurePosixPath(person.avatar.name).stem
        url = f"{reverse('accounts:person_avatar', args=[person.pk])}?v={version}"
    return {"person": person, "url": url, "size": size}
