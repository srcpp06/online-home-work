"""Who manages whom (SPEC §1): the manager its admins, the admin teachers and students;
the manager watches everyone, teachers see their students."""

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


def test_manager_watches_teachers_and_students_without_buttons(
    client: Client, world: World
) -> None:
    as_(client, world.a.manager)

    teachers = client.get("/teachers/").content.decode()
    person = client.get(f"/people/{world.a.student.pk}/").content.decode()

    assert world.a.teacher.username in teachers
    assert "qoʻshish" not in teachers
    for button in ("Tahrirlash", "Parolni tiklash", "Oʻchirish"):
        assert button not in person


def test_manager_manages_the_centres_admins(client: Client, world: World) -> None:
    as_(client, world.a.manager)

    admins = client.get("/admins/").content.decode()
    person = client.get(f"/people/{world.a.admin.pk}/").content.decode()

    assert world.a.admin.username in admins
    assert world.b.admin.username not in admins
    assert "Admin qoʻshish" in admins
    assert "Tahrirlash" in person
    client.post(
        "/admins/add/", {"last_name": "Usmonova", "first_name": "Nodira", "username": "nodira"}
    )
    nodira = User.objects.get(username="nodira")
    assert (nodira.role, nodira.center) == (Role.CENTER_ADMIN, world.a.center)


@pytest.mark.parametrize("url", ["/teachers/add/", "/students/add/"])
def test_manager_does_not_add_teachers_or_students(client: Client, world: World, url: str) -> None:
    assert as_(client, world.a.manager).get(url).status_code == 403


@pytest.mark.parametrize("action", ["edit", "password", "delete"])
def test_manager_cannot_change_teachers_or_students(
    client: Client, world: World, action: str
) -> None:
    url = f"/people/{world.a.student.pk}/{action}/"
    as_(client, world.a.manager)

    assert client.get(url).status_code == 403
    assert (
        client.post(url, {"first_name": "X", "last_name": "X", "username": "x"}).status_code == 403
    )
    assert User.objects.filter(pk=world.a.student.pk, first_name="").exists()


@pytest.mark.parametrize("url", ["/admins/", "/admins/add/"])
def test_admin_does_not_manage_admins(client: Client, world: World, url: str) -> None:
    assert as_(client, world.a.admin).get(url).status_code == 403


def test_admin_does_not_see_the_manager(client: Client, world: World) -> None:
    assert as_(client, world.a.admin).get(f"/people/{world.a.manager.pk}/").status_code == 404


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

    def test_students_and_admins_have_no_directions(self, client: Client, world: World) -> None:
        as_(client, world.a.admin)
        assert 'name="directions"' not in client.get("/students/add/").content.decode()
        as_(client, world.a.manager)
        assert 'name="directions"' not in client.get("/admins/add/").content.decode()


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

        response = client.post(f"/people/{world.a.other_student.pk}/delete/")

        assert response["Location"] == "/students/"
        assert not User.objects.filter(pk=world.a.other_student.pk).exists()
        assert Group.objects.filter(pk=world.a.other_group.pk).exists()

    def test_a_student_with_submissions_is_kept(self, client: Client, world: World) -> None:
        as_(client, world.a.admin)

        response = client.post(f"/people/{world.a.student.pk}/delete/", follow=True)

        assert User.objects.filter(pk=world.a.student.pk).exists()
        assert "nofaol qiling" in response.content.decode()

    def test_a_groups_teacher_is_not_deleted(self, client: Client, world: World) -> None:
        as_(client, world.a.admin)

        response = client.post(f"/people/{world.a.teacher.pk}/delete/", follow=True)

        assert User.objects.filter(pk=world.a.teacher.pk).exists()
        assert "bilan bogʻliq maʼlumotlar bor" in response.content.decode()

    @pytest.mark.parametrize("action", ["edit", "password", "delete"])
    def test_admin_does_not_manage_themselves_here(
        self, client: Client, world: World, action: str
    ) -> None:
        assert (
            as_(client, world.a.admin).get(f"/people/{world.a.admin.pk}/{action}/").status_code
            == 403
        )
