"""Signing in and out, the first-login password change and the login lockout."""

from typing import Any

import pytest
from django.test import Client, RequestFactory

from apps.accounts.client_ip import client_ip
from apps.accounts.models import Role, User
from tests.apps.world import PASSWORD, World, make_user

pytestmark = pytest.mark.django_db


def sign_in(client: Client, username: str, password: str = PASSWORD, **headers: Any) -> Any:
    return client.post("/login/", {"username": username, "password": password}, **headers)


def test_login_page_is_open_and_in_uzbek(client: Client) -> None:
    html = client.get("/login/").content.decode()

    assert ">Login<" in html
    assert ">Parol<" in html
    assert "Kirish</button>" in html


def test_every_other_page_needs_a_login(client: Client, world: World) -> None:
    for url in ("/", "/teachers/", f"/people/{world.a.student.pk}/", "/groups/", "/password/"):
        response = client.get(url)
        assert response.status_code == 302, url
        assert response["Location"].startswith("/login/?next="), url


@pytest.mark.parametrize(
    ("who", "home"),
    [
        ("superadmin", "/admin/"),
        ("a.admin", "/teachers/"),
        ("a.manager", "/teachers/"),
        ("a.teacher", "/groups/"),
    ],
)
def test_each_role_lands_on_its_page(client: Client, world: World, who: str, home: str) -> None:
    user = world.superadmin if who == "superadmin" else getattr(world.a, who.split(".")[1])

    assert sign_in(client, user.username)["Location"] == "/"
    assert client.get("/")["Location"] == home


def test_student_home_is_their_assignments(client: Client, world: World) -> None:
    sign_in(client, world.a.student.username)

    html = client.get("/").content.decode()

    assert "<h1>Topshiriqlarim</h1>" in html
    assert "Hali topshiriq yoʻq." in html


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
    assert client.post("/logout/")["Location"] == "/login/"
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

        assert client.post("/logout/")["Location"] == "/login/"

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
        ("a.admin", ["Oʻqituvchilar", "Oʻquvchilar", "Menejerlar", "Guruhlar"]),
        ("a.manager", ["Oʻqituvchilar", "Oʻquvchilar", "Guruhlar"]),
        ("a.teacher", ["Guruhlarim"]),
        ("a.student", ["Topshiriqlarim"]),
    ],
)
def test_menu_follows_the_role(client: Client, world: World, who: str, labels: list[str]) -> None:
    user = world.superadmin if who == "superadmin" else getattr(world.a, who.split(".")[1])
    client.force_login(user)

    response = client.get("/password/")

    assert [item.label for item in response.context["nav_items"]] == labels
