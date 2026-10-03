"""Loads profiles/<slug>/profile.json into RunnerProfile rows (SPEC §3.1).

The files are the source: run after every deploy and on `make migrate`. A profile that no
longer has a file is switched off, never deleted, because tasks keep pointing at it.
"""

import json
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tasks.models import RunnerProfile
from judge.core.profile import RunnerProfile as JudgeProfile
from judge.env import PROFILES_DIR


class Command(BaseCommand):
    help = "Create or update runner profiles from profiles/*/profile.json"

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        seen = []
        for path in sorted(PROFILES_DIR.glob("*/profile.json")):
            data = json.loads(path.read_text())
            JudgeProfile.from_json_data(data)  # a broken file stops here, before any write
            profile, created = RunnerProfile.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "title": data["title"],
                    "direction": data["direction"],
                    "lane": data["lane"],
                    "config": data,
                    "is_active": True,
                },
            )
            profile.full_clean()
            seen.append(profile.slug)
            self.stdout.write(f"{'created' if created else 'updated'} {profile.slug}")
        for slug in RunnerProfile.objects.exclude(slug__in=seen).values_list("slug", flat=True):
            RunnerProfile.objects.filter(slug=slug).update(is_active=False)
            self.stdout.write(f"switched off {slug} (no profile.json)")
