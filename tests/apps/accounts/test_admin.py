"""The superadmin's Django admin: pages open, and a wrong form is a message, never a 500."""

import pytest
from django.test import Client

from apps.accounts.models import Center, Group, Role, User
from tests.apps.world import PASSWORD, World


@pytest.fixture
def admin_client(client: Client, world: World) -> Client:
    client.force_login(world.superadmin)
    return client


@pytest.mark.parametrize(
    "url",
    [
        "/admin/",
        "/admin/accounts/center/",
        "/admin/accounts/center/add/",
        "/admin/accounts/user/",
        "/admin/accounts/user/add/",
        "/admin/accounts/group/",
        "/admin/accounts/group/add/",
    ],
)
def test_admin_pages_open(admin_client: Client, url: str) -> None:
    assert admin_client.get(url).status_code == 200


def test_user_and_group_edit_pages_open(admin_client: Client, world: World) -> None:
    assert admin_client.get(f"/admin/accounts/user/{world.a.teacher.pk}/change/").status_code == 200
    assert admin_client.get(f"/admin/accounts/group/{world.a.group.pk}/change/").status_code == 200


def test_permission_groups_are_hidden(admin_client: Client) -> None:
    assert admin_client.get("/admin/auth/group/").status_code == 404


def test_superadmin_adds_a_teacher(admin_client: Client, world: World) -> None:
    response = admin_client.post(
        "/admin/accounts/user/add/",
        {
            "username": "vali",
            "usable_password": "true",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "role": Role.TEACHER,
            "center": world.a.center.pk,
            "directions": ["flutter", "backend"],
        },
    )

    assert response.status_code == 302, response.context["adminform"].form.errors
    vali = User.objects.get(username="vali")
    assert (vali.role, vali.center, vali.directions) == (
        Role.TEACHER,
        world.a.center,
        ["flutter", "backend"],
    )
    assert (vali.must_change_password, vali.is_staff) == (True, False)


def test_teacher_without_a_centre_is_a_form_error(admin_client: Client) -> None:
    response = admin_client.post(
        "/admin/accounts/user/add/",
        {
            "username": "vali",
            "usable_password": "true",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "role": Role.TEACHER,
        },
    )

    assert response.status_code == 200
    assert "boshqa rollar uchun markazni tanlang" in response.content.decode()
    assert not User.objects.filter(username="vali").exists()


def test_group_with_another_centres_student_is_a_form_error(
    admin_client: Client, world: World
) -> None:
    response = admin_client.post(
        "/admin/accounts/group/add/",
        {
            "center": world.a.center.pk,
            "name": "Backend 1",
            "teacher": world.a.teacher.pk,
            "students": [world.a.student.pk, world.b.student.pk],
        },
    )

    assert response.status_code == 200
    assert "shu markazning oʻquvchisi emas: b-student" in response.content.decode()
    assert not Group.objects.filter(name="Backend 1").exists()


def test_superadmin_adds_a_center_manager(admin_client: Client, world: World) -> None:
    response = admin_client.post(
        "/admin/accounts/user/add/",
        {
            "username": "nodira",
            "usable_password": "true",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "role": Role.CENTER_MANAGER,
            "center": world.a.center.pk,
        },
    )

    assert response.status_code == 302, response.context["adminform"].form.errors
    manager = User.objects.get(username="nodira")
    assert (manager.role, manager.center, manager.is_staff) == (
        Role.CENTER_MANAGER,
        world.a.center,
        False,
    )


def test_center_manager_gets_no_directions(admin_client: Client, world: World) -> None:
    response = admin_client.post(
        "/admin/accounts/user/add/",
        {
            "username": "nodira",
            "usable_password": "true",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "role": Role.CENTER_MANAGER,
            "center": world.a.center.pk,
            "directions": ["flutter"],
        },
    )

    assert response.status_code == 200
    assert "Yoʻnalishlar faqat oʻqituvchiga biriktiriladi" in response.content.decode()
    assert not User.objects.filter(username="nodira").exists()


@pytest.mark.parametrize("role", ["admin", "manager", "teacher", "student"])
def test_only_the_superadmin_gets_into_admin(client: Client, world: World, role: str) -> None:
    client.force_login(getattr(world.a, role))

    response = client.get("/admin/")

    assert response.status_code == 302
    assert response["Location"].startswith("/admin/login/")


def test_center_list_is_for_the_superadmin_only(admin_client: Client, world: World) -> None:
    assert Center.objects.count() == 2
    assert "Markaz a" in admin_client.get("/admin/accounts/center/").content.decode()
