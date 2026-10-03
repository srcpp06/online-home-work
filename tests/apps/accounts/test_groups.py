"""Study groups: the centre admin manages them; the manager and teachers look."""

import pytest
from django.test import Client

from apps.accounts.models import Group, User
from tests.apps.world import World

pytestmark = pytest.mark.django_db


def as_(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def test_admin_sees_the_centres_groups(client: Client, world: World) -> None:
    html = as_(client, world.a.admin).get("/groups/").content.decode()

    assert html.count("Flutter 1") == 1  # centre b's group of the same name is not here
    assert "Flutter 2" in html
    assert "Guruh yaratish" in html


def test_teacher_sees_their_groups(client: Client, world: World) -> None:
    as_(client, world.a.teacher)

    html = client.get("/groups/").content.decode()

    assert "<h1>Guruhlarim</h1>" in html
    assert "Flutter 1" in html
    assert "Flutter 2" not in html
    assert client.get(f"/groups/{world.a.other_group.pk}/").status_code == 404


def test_manager_looks_at_every_group(client: Client, world: World) -> None:
    as_(client, world.a.manager)

    page = client.get(f"/groups/{world.a.other_group.pk}/").content.decode()

    assert world.a.other_student.username in page  # no name entered: the login is shown
    assert "Tahrirlash" not in page
    assert client.get("/groups/add/").status_code == 403
    assert client.post(f"/groups/{world.a.group.pk}/delete/").status_code == 403
    assert Group.objects.filter(pk=world.a.group.pk).exists()


def test_student_has_no_group_pages(client: Client, world: World) -> None:
    assert as_(client, world.a.student).get("/groups/").status_code == 403


def test_admin_creates_a_group(client: Client, world: World) -> None:
    a = world.a
    as_(client, a.admin)

    response = client.post(
        "/groups/add/",
        {
            "name": "Backend 1",
            "teacher": a.teacher.pk,
            "students": [a.student.pk, a.other_student.pk],
        },
    )

    group = Group.objects.get(name="Backend 1")
    assert response["Location"] == f"/groups/{group.pk}/"
    assert (group.center, group.teacher) == (a.center, a.teacher)
    assert set(group.students.all()) == {a.student, a.other_student}


@pytest.mark.parametrize(
    "wrong",
    [
        {"teacher": "b.teacher"},
        {"teacher": "a.student"},
        {"students": "b.student"},
        {"students": "a.teacher"},
    ],
)
def test_only_the_centres_teachers_and_students_are_accepted(
    client: Client, world: World, wrong: dict[str, str]
) -> None:
    def user(ref: str) -> int:
        centre, name = ref.split(".")
        return getattr(getattr(world, centre), name).pk

    data = {"name": "Backend 1", "teacher": world.a.teacher.pk, "students": [world.a.student.pk]}
    for field, ref in wrong.items():
        data[field] = user(ref) if field == "teacher" else [user(ref)]
    as_(client, world.a.admin)

    response = client.post("/groups/add/", data)

    assert response.status_code == 200
    assert not Group.objects.filter(name="Backend 1").exists()


def test_admin_edits_and_deletes_a_group(client: Client, world: World) -> None:
    a = world.a
    as_(client, a.admin)

    client.post(
        f"/groups/{a.group.pk}/edit/",
        {"name": "Flutter 1A", "teacher": a.other_teacher.pk, "students": [a.other_student.pk]},
    )
    a.group.refresh_from_db()
    assert (a.group.name, a.group.teacher) == ("Flutter 1A", a.other_teacher)
    assert list(a.group.students.all()) == [a.other_student]

    assert client.post(f"/groups/{a.group.pk}/delete/")["Location"] == "/groups/"
    assert not Group.objects.filter(pk=a.group.pk).exists()
    assert User.objects.filter(pk=a.student.pk).exists()
