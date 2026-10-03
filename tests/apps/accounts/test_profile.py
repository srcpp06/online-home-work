"""Each person's profile: their picture, contacts and numbers (Phase 1.5)."""

import io

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from apps.accounts.models import User
from tests.apps.world import World

pytestmark = pytest.mark.django_db


def as_(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def png() -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), (200, 40, 40)).save(buffer, "PNG")
    return SimpleUploadedFile("me.png", buffer.getvalue(), content_type="image/png")


def with_picture(user: User) -> User:
    buffer = io.BytesIO()
    Image.new("RGB", (256, 256)).save(buffer, "WEBP")
    user.avatar.save("avatar.webp", ContentFile(buffer.getvalue()))
    return user


def test_the_profile_shows_who_and_what(client: Client, world: World) -> None:
    page = as_(client, world.a.student).get("/profile/").content.decode()

    assert world.a.student.display_name in page
    assert "Oʻquvchi" in page
    assert "Yechilgan" in page  # the world's student has one accepted solution
    assert world.a.group.name in page
    assert world.a.task.title in page  # recent solutions


def test_contacts_and_about_are_saved_and_cleaned(client: Client, world: World) -> None:
    as_(client, world.a.teacher)

    response = client.post(
        "/profile/", {"phone": "+998 90 123 45 67", "telegram": "@aziz_dev", "bio": "Flutter"}
    )

    teacher = User.objects.get(pk=world.a.teacher.pk)
    assert response["Location"] == "/profile/"
    assert (teacher.phone, teacher.telegram, teacher.bio) == (
        "+998 90 123 45 67",
        "aziz_dev",
        "Flutter",
    )
    assert "https://t.me/aziz_dev" in client.get("/profile/").content.decode()


@pytest.mark.parametrize(
    ("field", "value", "says"),
    [("phone", "qoʻngʻiroq qiling", "raqamlar bilan"), ("telegram", "@a", "5 dan 32")],
)
def test_bad_contacts_are_explained(
    client: Client, world: World, field: str, value: str, says: str
) -> None:
    response = as_(client, world.a.student).post("/profile/", {field: value})

    assert response.status_code == 400
    assert says in response.content.decode()


def test_the_profile_never_changes_the_name_login_or_role(client: Client, world: World) -> None:
    student = world.a.student
    as_(client, student)

    client.post(
        "/profile/",
        {"first_name": "Hacker", "username": "root", "role": "superadmin", "phone": ""},
    )

    student.refresh_from_db()
    assert (student.first_name, student.username, student.role) == ("", "a-student", "student")


def test_a_picture_is_stored_as_webp_and_served_privately(client: Client, world: World) -> None:
    as_(client, world.a.student)

    client.post("/profile/", {"picture": png()})

    student = User.objects.get(pk=world.a.student.pk)
    assert student.avatar.name.startswith(f"avatars/{student.center_id}/{student.pk}/")
    assert student.avatar.name.endswith(".webp")
    response = client.get(f"/people/{student.pk}/avatar/")
    assert response["Content-Type"] == "image/webp"
    assert response["Cache-Control"] == "private, max-age=86400"
    assert f"/people/{student.pk}/avatar/?v=" in client.get("/profile/").content.decode()


def test_a_new_picture_replaces_the_old_file(client: Client, world: World) -> None:
    student = with_picture(world.a.student)
    old = student.avatar.name
    as_(client, student)

    client.post("/profile/", {"picture": png()})

    student.refresh_from_db()
    assert student.avatar.name != old
    assert not student.avatar.storage.exists(old)


def test_the_picture_can_be_removed(client: Client, world: World) -> None:
    student = with_picture(world.a.student)
    name = student.avatar.name
    as_(client, student)

    client.post("/profile/", {"remove_picture": "on"})

    student.refresh_from_db()
    assert not student.avatar
    assert not student.avatar.storage.exists(name)


def test_a_non_picture_is_refused(client: Client, world: World) -> None:
    as_(client, world.a.student)

    response = client.post("/profile/", {"picture": SimpleUploadedFile("me.png", b"MZ\x90")})

    assert response.status_code == 400
    assert "rasm emas" in response.content.decode()
    assert not User.objects.get(pk=world.a.student.pk).avatar


@pytest.mark.parametrize(
    ("viewer", "status"),
    [("teacher", 200), ("admin", 200), ("manager", 200), ("other_student", 404)],
)
def test_who_sees_a_students_picture(
    client: Client, world: World, viewer: str, status: int
) -> None:
    student = with_picture(world.a.student)

    response = as_(client, getattr(world.a, viewer)).get(f"/people/{student.pk}/avatar/")

    assert response.status_code == status


def test_another_centres_picture_is_out_of_reach(client: Client, world: World) -> None:
    student = with_picture(world.b.student)

    assert as_(client, world.a.manager).get(f"/people/{student.pk}/avatar/").status_code == 404


def test_the_admin_sees_a_student_without_results(client: Client, world: World) -> None:
    page = as_(client, world.a.admin).get(f"/people/{world.a.student.pk}/").content.decode()

    assert "Guruhlar" in page
    assert "Yechilgan" not in page
    assert world.a.task.title not in page


def test_the_teacher_sees_their_students_numbers(client: Client, world: World) -> None:
    page = as_(client, world.a.teacher).get(f"/people/{world.a.student.pk}/").content.decode()

    assert "Yechilgan" in page
    assert "Oxirgi yechimlar" in page


def test_the_sidebar_links_to_the_profile(client: Client, world: World) -> None:
    page = as_(client, world.a.teacher).get("/groups/").content.decode()

    assert 'href="/profile/"' in page
