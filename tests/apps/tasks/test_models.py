"""Who sees which profiles, tasks, versions and assignments (SPEC §1)."""

import io
import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.access import visible_to
from apps.accounts.models import Direction, Role
from apps.tasks.models import Assignment, RunnerProfile, Task, TaskVersion
from tests.apps.world import World, make_task, make_user

pytestmark = pytest.mark.django_db


def test_teacher_sees_only_the_profiles_of_their_directions(world: World) -> None:
    backend = make_user("bek", Role.TEACHER, world.a.center, directions=[Direction.BACKEND])

    assert set(visible_to(RunnerProfile, world.a.teacher).values_list("slug", flat=True)) == {
        "dart",
        "flutter",
    }
    assert not visible_to(RunnerProfile, backend).exists()
    assert not visible_to(RunnerProfile, world.a.student).exists()


def test_tasks_are_seen_by_their_centre_and_author(world: World) -> None:
    a, b = world.a, world.b

    assert not visible_to(Task, a.admin).exists()  # the admin works with people only
    assert set(visible_to(Task, a.manager)) == {a.task}
    assert set(visible_to(Task, a.teacher)) == {a.task}
    assert not visible_to(Task, a.other_teacher).exists()
    assert set(visible_to(Task, world.superadmin)) == {a.task, b.task}


def test_student_sees_a_task_only_through_an_open_assignment(world: World) -> None:
    a = world.a

    assert set(visible_to(Task, a.student)) == {a.task}
    assert not visible_to(Task, a.other_student).exists()

    a.assignment.opens_at = timezone.now() + timedelta(hours=1)
    a.assignment.save()
    assert not visible_to(Task, a.student).exists()
    assert not visible_to(Assignment, a.student).exists()


def test_student_never_sees_an_unpublished_or_archived_task(world: World) -> None:
    a = world.a
    draft, _ = make_task(a.teacher, "Qoralama", publish=False)
    Assignment.objects.create(task=draft, group=a.group)

    assert set(visible_to(Task, a.student)) == {a.task}
    a.task.is_archived = True
    a.task.save()
    assert not visible_to(Assignment, a.student).exists()


def test_student_sees_only_the_published_version(world: World) -> None:
    a = world.a
    newer = TaskVersion.objects.create(task=a.task, number=2, package="x.zip", sha256="2" * 64)

    assert set(visible_to(TaskVersion, a.teacher)) == {a.version, newer}
    assert set(visible_to(TaskVersion, a.student)) == {a.version}


def test_teacher_sees_assignments_of_the_groups_they_teach(world: World) -> None:
    a = world.a

    assert set(visible_to(Assignment, a.teacher)) == {a.assignment}
    assert not visible_to(Assignment, a.other_teacher).exists()
    assert set(visible_to(Assignment, a.manager)) == {a.assignment}


def test_assignment_needs_the_same_centre(world: World) -> None:
    assignment = Assignment(task=world.a.task, group=world.b.group)

    with pytest.raises(ValidationError, match="bir markazdan"):
        assignment.full_clean()


def test_assignment_deadline_comes_after_opening(world: World) -> None:
    with pytest.raises(IntegrityError, match="deadline_after_opening"), transaction.atomic():
        Assignment.objects.filter(pk=world.a.assignment.pk).update(
            deadline=world.a.assignment.opens_at - timedelta(minutes=1)
        )


def test_only_a_ready_version_of_the_task_is_published(world: World) -> None:
    a = world.a
    building = TaskVersion.objects.create(task=a.task, number=2, package="x.zip", sha256="2" * 64)
    a.task.published_version = building

    with pytest.raises(ValidationError, match="tayyor versiyasi"):
        a.task.full_clean()


class TestLoadProfiles:
    def test_profiles_come_from_their_files(self, db: None) -> None:
        call_command("load_profiles", stdout=io.StringIO())

        flutter = RunnerProfile.objects.get(slug="flutter")
        assert (flutter.title, flutter.direction, flutter.lane) == ("Flutter", "flutter", "heavy")
        assert flutter.judge_profile().memory_mb == 1536

    def test_loading_twice_changes_nothing(self, db: None) -> None:
        call_command("load_profiles", stdout=io.StringIO())
        call_command("load_profiles", stdout=io.StringIO())

        assert RunnerProfile.objects.count() == 2

    def test_a_profile_without_a_file_is_switched_off(
        self, db: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        call_command("load_profiles", stdout=io.StringIO())
        (tmp_path / "dart").mkdir()
        source = Path("profiles/dart/profile.json")
        (tmp_path / "dart" / "profile.json").write_text(source.read_text())
        monkeypatch.setattr("apps.tasks.management.commands.load_profiles.PROFILES_DIR", tmp_path)

        call_command("load_profiles", stdout=io.StringIO())

        assert RunnerProfile.objects.get(slug="dart").is_active
        assert not RunnerProfile.objects.get(slug="flutter").is_active

    def test_a_broken_file_changes_nothing(
        self, db: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "dart").mkdir()
        data = json.loads(Path("profiles/dart/profile.json").read_text())
        data["memory_mb"] = 0
        (tmp_path / "dart" / "profile.json").write_text(json.dumps(data))
        monkeypatch.setattr("apps.tasks.management.commands.load_profiles.PROFILES_DIR", tmp_path)

        with pytest.raises(ValueError, match="positive"):
            call_command("load_profiles", stdout=io.StringIO())
        assert not RunnerProfile.objects.exists()
