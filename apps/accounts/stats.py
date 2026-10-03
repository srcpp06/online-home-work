"""The numbers on a profile, by role, counted only from what the viewer may see.

A teacher looking at a student counts that student's work in the teacher's own groups;
an admin, who sees no solutions, gets no results at all. So a profile never shows more
than the viewer could find by opening the pages one by one.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.accounts.access import visible_to
from apps.accounts.models import Group, Role, User
from apps.accounts.permissions import Action, can
from apps.submissions.models import Submission
from apps.tasks.models import Assignment, Task
from judge.core.verdict import Verdict


@dataclass(frozen=True)
class Stat:
    label: str
    value: str


def person_stats(person: User, viewer: User) -> list[Stat]:
    match person.role:
        case Role.STUDENT:
            return _student(person, viewer)
        case Role.TEACHER:
            return _teacher(person, viewer)
        case Role.CENTER_MANAGER | Role.CENTER_ADMIN:
            return _centre(person, viewer)
    return []


def recent_submissions(person: User, viewer: User, count: int = 5) -> list[Submission]:
    if person.role != Role.STUDENT or not can(viewer, Action.VIEW_CODE):
        return []
    return list(
        visible_to(Submission, viewer)
        .filter(student=person)
        .select_related("assignment__task")
        .order_by("-created_at")[:count]
    )


def _student(person: User, viewer: User) -> list[Stat]:
    stats = [
        Stat("Guruhlar", str(visible_to(Group, viewer).filter(students=person).count())),
    ]
    if not can(viewer, Action.VIEW_CODE):
        return stats
    mine = visible_to(Submission, viewer).filter(student=person)
    counted = mine.counting().filter(status=Submission.Status.FINISHED)
    accepted = counted.filter(verdict=Verdict.ACCEPTED)
    solved = accepted.values("assignment").distinct().count()
    tried = counted.count()
    rate = f"{round(100 * accepted.count() / tried)}%" if tried else "—"
    assignments = (
        visible_to(Assignment, viewer)
        .filter(group__students=person, opens_at__lte=timezone.now())
        .distinct()
        .count()
    )
    return [
        *stats,
        Stat("Topshiriqlar", str(assignments)),
        Stat("Yechilgan", str(solved)),
        Stat("Urinishlar", str(tried)),
        Stat("Qabul foizi", rate),
    ]


def _teacher(person: User, viewer: User) -> list[Stat]:
    groups = visible_to(Group, viewer).filter(teacher=person)
    students = visible_to(User, viewer).filter(study_groups__in=groups).distinct().count()
    stats = [Stat("Guruhlar", str(groups.count())), Stat("Oʻquvchilar", str(students))]
    if can(viewer, Action.VIEW_TASKS):
        tasks = visible_to(Task, viewer).filter(author=person, is_archived=False)
        stats.append(Stat("Topshiriqlar", str(tasks.count())))
    if can(viewer, Action.VIEW_CODE):
        week = timezone.now() - timedelta(days=7)
        checked = (
            visible_to(Submission, viewer)
            .filter(assignment__group__teacher=person, created_at__gte=week)
            .count()
        )
        stats.append(Stat("Yechimlar, 7 kun", str(checked)))
    return stats


def _centre(person: User, viewer: User) -> list[Stat]:
    if viewer.pk != person.pk:
        return []
    people = visible_to(User, viewer).filter(is_active=True)
    stats = [
        Stat("Oʻqituvchilar", str(people.filter(role=Role.TEACHER).count())),
        Stat("Oʻquvchilar", str(people.filter(role=Role.STUDENT).count())),
        Stat("Guruhlar", str(visible_to(Group, viewer).count())),
    ]
    if person.role == Role.CENTER_MANAGER:
        stats.insert(0, Stat("Adminlar", str(people.filter(role=Role.CENTER_ADMIN).count())))
        tasks = visible_to(Task, viewer).filter(~Q(published_version=None), is_archived=False)
        stats.append(Stat("Eʼlon qilingan topshiriqlar", str(tasks.count())))
    return stats
