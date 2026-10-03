"""Signing in and out, the first-login password change and the login lockout."""

from typing import Any

import pytest
from django.test import Client, RequestFactory

from apps.accounts.client_ip import client_ip
from apps.accounts.models import Role, User
from tests.apps.world import PASSWORD, World, make_user

pytestmark = pytest.mark.django_db


STAFF_DOOR, STUDENT_DOOR = "/staff/login/", "/login/"


def door_of(username: str) -> str:
    user = User.objects.filter(username=username).first()
    return STUDENT_DOOR if user is None or user.role == Role.STUDENT else STAFF_DOOR


def sign_in(
    client: Client, username: str, password: str = PASSWORD, door: str = "", **headers: Any
) -> Any:
    """Signs in at the user's own door unless another one is given."""
    data = {"username": username, "password": password}
    return client.post(door or door_of(username), data, **headers)


@pytest.mark.parametrize(
    ("url", "title"),
    [(STUDENT_DOOR, "Oʻquvchilar uchun kirish"), (STAFF_DOOR, "Xodimlar uchun kirish")],
)
def test_both_doors_are_open_and_in_uzbek(client: Client, url: str, title: str) -> None:
    html = client.get(url).content.decode()

    assert title in html
    assert ">Login<" in html
    assert ">Parol<" in html
    assert "Kirish</button>" in html


def test_the_landing_page_shows_both_doors(client: Client) -> None:
    html = client.get("/").content.decode()

    assert f'href="{STUDENT_DOOR}"' in html
    assert f'href="{STAFF_DOOR}"' in html


def test_every_other_page_sends_to_the_landing_page_and_keeps_the_address(
    client: Client, world: World
) -> None:
    for url in ("/teachers/", f"/people/{world.a.student.pk}/", "/groups/", "/password/"):
        response = client.get(url)
        assert response.status_code == 302, url
        assert response["Location"].startswith("/?next="), url

    landing = client.get("/?next=/groups/").content.decode()
    assert f'href="{STAFF_DOOR}?next=%2Fgroups%2F"' in landing
    assert f'href="{STUDENT_DOOR}?next=%2Fgroups%2F"' in landing


@pytest.mark.parametrize("who", ["a.teacher", "a.manager", "a.admin"])
def test_staff_at_the_students_door_are_sent_to_their_own(
    client: Client, world: World, who: str
) -> None:
    user = getattr(world.a, who.split(".")[1])

    response = sign_in(client, user.username, door=STUDENT_DOOR)

    html = response.content.decode()
    assert response.status_code == 200
    assert "Bu xodim hisobi" in html
    assert f'href="{STAFF_DOOR}"' in html
    assert "_auth_user_id" not in client.session


def test_a_student_at_the_staff_door_is_sent_to_theirs(client: Client, world: World) -> None:
    response = sign_in(client, world.a.student.username, door=STAFF_DOOR)

    html = response.content.decode()
    assert "Bu oʻquvchi hisobi" in html
    assert f'href="{STUDENT_DOOR}"' in html
    assert "_auth_user_id" not in client.session


@pytest.mark.parametrize("door", [STUDENT_DOOR, STAFF_DOOR])
def test_the_superadmin_never_signs_in_at_the_sites_doors(
    client: Client, world: World, door: str
) -> None:
    response = sign_in(client, world.superadmin.username, door=door)

    assert "Login yoki parol notoʻgʻri. Qayta kiriting." in response.content.decode()
    assert "_auth_user_id" not in client.session


@pytest.mark.parametrize(
    ("who", "home"),
    [
        ("a.admin", "/teachers/"),
        ("a.manager", "/teachers/"),
        ("a.teacher", "/groups/"),
        ("a.student", "/assignments/"),
    ],
)
def test_each_role_lands_on_its_page(client: Client, world: World, who: str, home: str) -> None:
    user = world.superadmin if who == "superadmin" else getattr(world.a, who.split(".")[1])

    assert sign_in(client, user.username)["Location"] == "/"
    assert client.get("/")["Location"] == home


def test_student_home_is_their_assignments(client: Client, world: World) -> None:
    sign_in(client, world.a.student.username)

    html = client.get("/", follow=True).content.decode()

    assert "<h1>Topshiriqlarim</h1>" in html
    assert world.a.task.title in html


def test_wrong_password_is_one_plain_message(client: Client, world: World) -> None:
    response = sign_in(client, world.a.student.username, "notogri-parol")

    assert response.status_code == 200
    assert "Login yoki parol notoʻgʻri. Qayta kiriting." in response.content.decode()


def test_inactive_centre_cannot_sign_in(client: Client, world: World) -> None:
    world.a.center.is_active = False
    world.a.center.save()

    response = sign_in(client, world.a.teacher.username)

    assert response.status_code == 200
    assert "Markazingiz hozir faol emas" in response.content.decode()


def test_sign_out_is_a_post(client: Client, world: World) -> None:
    client.force_login(world.a.teacher)

    assert client.get("/logout/").status_code == 405
    assert client.post("/logout/")["Location"] == "/"
    assert client.get("/groups/").status_code == 302


class TestFirstSignIn:
    @pytest.fixture
    def newcomer(self, world: World) -> User:
        return make_user("yangi", Role.STUDENT, world.a.center, must_change_password=True)

    def test_every_page_leads_to_the_password_change(self, client: Client, newcomer: User) -> None:
        sign_in(client, "yangi")

        for url in ("/", "/groups/", "/admin/"):
            assert client.get(url)["Location"] == "/password/", url
        html = client.get("/password/").content.decode()
        assert "Bu birinchi kirishingiz." in html

    def test_signing_out_still_works(self, client: Client, newcomer: User) -> None:
        sign_in(client, "yangi")

        assert client.post("/logout/")["Location"] == "/"

    def test_new_password_must_differ(self, client: Client, newcomer: User) -> None:
        sign_in(client, "yangi")

        response = client.post(
            "/password/",
            {"old_password": PASSWORD, "new_password1": PASSWORD, "new_password2": PASSWORD},
        )

        assert "Yangi parol hozirgisidan farq qilishi kerak." in response.content.decode()
        newcomer.refresh_from_db()
        assert newcomer.must_change_password

    def test_changing_it_opens_the_site(self, client: Client, newcomer: User) -> None:
        sign_in(client, "yangi")
        new = "Daftar-2026-qalam"

        response = client.post(
            "/password/", {"old_password": PASSWORD, "new_password1": new, "new_password2": new}
        )

        assert response["Location"] == "/"
        newcomer.refresh_from_db()
        assert not newcomer.must_change_password
        assert newcomer.check_password(new)
        page = client.get("/", follow=True)  # still signed in, with the confirmation
        assert "Parol almashtirildi." in page.content.decode()


class TestLockout:
    def fail(self, client: Client, username: str, ip: str, times: int) -> None:
        for _ in range(times):
            sign_in(client, username, "notogri", HTTP_X_FORWARDED_FOR=ip)

    def test_ten_failures_lock_the_login_on_that_address(
        self, client: Client, world: World
    ) -> None:
        self.fail(client, world.a.student.username, "10.0.0.7", 10)

        response = sign_in(client, world.a.student.username, HTTP_X_FORWARDED_FOR="10.0.0.7")

        assert response.status_code == 429
        assert "Kirish vaqtincha yopiq" in response.content.decode()

    def test_classmates_behind_the_same_address_still_sign_in(
        self, client: Client, world: World
    ) -> None:
        self.fail(client, world.a.student.username, "10.0.0.7", 10)

        response = sign_in(client, world.a.other_student.username, HTTP_X_FORWARDED_FOR="10.0.0.7")

        assert response.status_code == 302

    def test_the_same_login_from_another_address_still_signs_in(
        self, client: Client, world: World
    ) -> None:
        self.fail(client, world.a.student.username, "10.0.0.7", 10)

        response = sign_in(client, world.a.student.username, HTTP_X_FORWARDED_FOR="10.0.0.8")

        assert response.status_code == 302


@pytest.mark.parametrize(
    ("meta", "ip"),
    [
        ({"REMOTE_ADDR": "172.18.0.5", "HTTP_X_FORWARDED_FOR": "203.0.113.9"}, "203.0.113.9"),
        (
            {"REMOTE_ADDR": "172.18.0.5", "HTTP_X_FORWARDED_FOR": "1.2.3.4, 203.0.113.9"},
            "203.0.113.9",
        ),
        ({"REMOTE_ADDR": "127.0.0.1"}, "127.0.0.1"),
    ],
)
def test_client_ip_is_the_last_forwarded_address(meta: dict[str, str], ip: str) -> None:
    assert client_ip(RequestFactory().get("/", **meta)) == ip


@pytest.mark.parametrize(
    ("who", "labels"),
    [
        ("superadmin", ["Admin panel"]),
        ("a.admin", ["Oʻqituvchilar", "Oʻquvchilar", "Guruhlar"]),
        ("a.manager", ["Adminlar", "Oʻqituvchilar", "Oʻquvchilar", "Guruhlar", "Topshiriqlar"]),
        ("a.teacher", ["Guruhlarim", "Topshiriqlar"]),
        ("a.student", ["Topshiriqlarim"]),
    ],
)
def test_menu_follows_the_role(client: Client, world: World, who: str, labels: list[str]) -> None:
    user = world.superadmin if who == "superadmin" else getattr(world.a, who.split(".")[1])
    client.force_login(user)

    response = client.get("/password/")

    assert [item.label for item in response.context["nav_items"]] == labels


class TestAlreadySignedIn:
    """Erkin, signed in to /admin/ as the superadmin, opened /login/ and was sent straight
    back to the admin: the sign-in form never showed."""

    def test_the_login_page_still_shows_and_says_who_is_signed_in(
        self, client: Client, world: World
    ) -> None:
        client.force_login(world.superadmin)

        response = client.get("/login/")

        assert response.status_code == 200
        assert f"Hozir {world.superadmin.display_name} sifatida kirgansiz" in (
            response.content.decode()
        )

    def test_signing_in_as_someone_else_switches_the_account(
        self, client: Client, world: World
    ) -> None:
        client.force_login(world.superadmin)

        sign_in(client, world.a.teacher.username)

        assert client.get("/")["Location"] == "/groups/"


def test_admin_login_sends_other_roles_to_the_site_login(client: Client, world: World) -> None:
    response = client.post(
        "/admin/login/", {"username": world.a.teacher.username, "password": PASSWORD}
    )

    html = response.content.decode()
    assert response.status_code == 200
    assert "Admin panelga faqat superadmin kiradi" in html
    assert 'href="/"' in html
