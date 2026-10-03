"""The centre admin manages people; the manager and teachers only look (SPEC §1)."""

import re

import pytest
from django.test import Client

from apps.accounts.models import Direction, Group, Role, User
from tests.apps.world import World

pytestmark = pytest.mark.django_db
TEMP_PASSWORD = re.compile(r"<code class=\"text-lg\">([a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4})</code>")


def as_(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def test_admin_sees_their_centres_teachers_only(client: Client, world: World) -> None:
    html = as_(client, world.a.admin).get("/teachers/").content.decode()

    assert world.a.teacher.username in html
    assert world.a.other_teacher.username in html
    assert world.b.teacher.username not in html
    assert "Oʻqituvchi qoʻshish" in html


def test_manager_looks_without_buttons(client: Client, world: World) -> None:
    as_(client, world.a.manager)

    teachers = client.get("/teachers/").content.decode()
    person = client.get(f"/people/{world.a.student.pk}/").content.decode()

    assert world.a.teacher.username in teachers
    assert "qoʻshish" not in teachers
    for button in ("Tahrirlash", "Parolni tiklash", "Oʻchirish"):
        assert button not in person


@pytest.mark.parametrize(
    "url", ["/managers/", "/teachers/add/", "/students/add/", "/managers/add/"]
)
def test_manager_cannot_open_admin_pages(client: Client, world: World, url: str) -> None:
    assert as_(client, world.a.manager).get(url).status_code == 403


@pytest.mark.parametrize("action", ["edit", "password", "delete"])
def test_manager_cannot_change_people(client: Client, world: World, action: str) -> None:
    url = f"/people/{world.a.student.pk}/{action}/"
    as_(client, world.a.manager)

    assert client.get(url).status_code == 403
    assert (
        client.post(url, {"first_name": "X", "last_name": "X", "username": "x"}).status_code == 403
    )
    assert User.objects.filter(pk=world.a.student.pk, first_name="").exists()


def test_teacher_sees_only_their_students(client: Client, world: World) -> None:
    html = as_(client, world.a.teacher).get("/students/").content.decode()

    assert world.a.student.username in html
    assert world.a.other_student.username not in html


def test_student_sees_no_people(client: Client, world: World) -> None:
    as_(client, world.a.student)

    assert client.get("/teachers/").status_code == 403
    assert client.get(f"/people/{world.a.teacher.pk}/").status_code == 403


def test_superadmin_is_sent_to_django_admin(client: Client, world: World) -> None:
    as_(client, world.superadmin)

    assert client.get("/teachers/")["Location"] == "/admin/accounts/user/?role__exact=teacher"
    assert client.get(f"/people/{world.a.student.pk}/")["Location"] == (
        f"/admin/accounts/user/{world.a.student.pk}/change/"
    )


class TestAdding:
    def add_teacher(self, client: Client, **changes: object) -> object:
        data = {
            "last_name": "Karimov",
            "first_name": "Aziz",
            "username": "aziz",
            "directions": [Direction.FLUTTER, Direction.BACKEND],
            **changes,
        }
        return client.post("/teachers/add/", data)

    def test_new_teacher_gets_a_temporary_password_shown_once(
        self, client: Client, world: World
    ) -> None:
        as_(client, world.a.admin)

        response = self.add_teacher(client)

        aziz = User.objects.get(username="aziz")
        assert response["Location"] == f"/people/{aziz.pk}/password/new/"
        assert (aziz.role, aziz.center, aziz.directions) == (
            Role.TEACHER,
            world.a.center,
            ["flutter", "backend"],
        )
        assert aziz.must_change_password
        page = client.get(response["Location"])
        assert page["Cache-Control"] == "no-store"
        [password] = TEMP_PASSWORD.findall(page.content.decode())
        assert aziz.check_password(password)
        again = client.get(response["Location"], follow=True)
        assert password not in again.content.decode()
        assert "faqat bir marta koʻrsatiladi" in again.content.decode()

    def test_a_teacher_needs_a_direction(self, client: Client, world: World) -> None:
        as_(client, world.a.admin)

        response = self.add_teacher(client, directions=[])

        assert response.status_code == 200
        assert not User.objects.filter(username="aziz").exists()

    def test_a_taken_login_is_refused(self, client: Client, world: World) -> None:
        as_(client, world.a.admin)

        response = self.add_teacher(client, username=world.b.teacher.username)

        assert response.status_code == 200
        assert User.objects.filter(username=world.b.teacher.username).count() == 1

    def test_students_and_managers_have_no_directions(self, client: Client, world: World) -> None:
        as_(client, world.a.admin)

        for url in ("/students/add/", "/managers/add/"):
            assert 'name="directions"' not in client.get(url).content.decode()
        client.post(
            "/managers/add/",
            {"last_name": "Usmonova", "first_name": "Nodira", "username": "nodira"},
        )
        assert User.objects.get(username="nodira").role == Role.CENTER_MANAGER


class TestChanging:
    def test_admin_edits_and_deactivates(self, client: Client, world: World) -> None:
        student = world.a.student
        as_(client, world.a.admin)

        response = client.post(
            f"/people/{student.pk}/edit/",
            {"last_name": "Toshev", "first_name": "Anvar", "username": student.username},
        )

        assert response["Location"] == f"/people/{student.pk}/"
        student.refresh_from_db()
        assert (student.last_name, student.is_active) == ("Toshev", False)

    def test_admin_resets_a_password(self, client: Client, world: World) -> None:
        student = world.a.student
        as_(client, world.a.admin)

        response = client.post(f"/people/{student.pk}/password/", follow=True)

        [password] = TEMP_PASSWORD.findall(response.content.decode())
        student.refresh_from_db()
        assert student.check_password(password)
        assert student.must_change_password

    def test_admin_deletes_a_student(self, client: Client, world: World) -> None:
        as_(client, world.a.admin)

        response = client.post(f"/people/{world.a.student.pk}/delete/")

        assert response["Location"] == "/students/"
        assert not User.objects.filter(pk=world.a.student.pk).exists()
        assert Group.objects.filter(pk=world.a.group.pk).exists()

    def test_a_groups_teacher_is_not_deleted(self, client: Client, world: World) -> None:
        as_(client, world.a.admin)

        response = client.post(f"/people/{world.a.teacher.pk}/delete/", follow=True)

        assert User.objects.filter(pk=world.a.teacher.pk).exists()
        assert "guruhga oʻqituvchi qilib biriktirilgan" in response.content.decode()

    @pytest.mark.parametrize("action", ["edit", "password", "delete"])
    def test_admin_does_not_manage_themselves_here(
        self, client: Client, world: World, action: str
    ) -> None:
        assert (
            as_(client, world.a.admin).get(f"/people/{world.a.admin.pk}/{action}/").status_code
            == 403
        )
