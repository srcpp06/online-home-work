"""Role rules (SPEC §1, §2): checked by forms and enforced by the database."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import Center, Direction, Group, Role, User
from tests.apps.world import PASSWORD, World, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def center() -> Center:
    return Center.objects.create(name="Najot", slug="najot")


def test_createsuperuser_makes_the_superadmin() -> None:
    user = User.objects.create_superuser(username="erkin", password=PASSWORD)

    assert (user.role, user.center, user.is_staff, user.is_superuser) == (
        Role.SUPERADMIN,
        None,
        True,
        True,
    )
    assert user.must_change_password is False


def test_new_users_change_their_password_first(center: Center) -> None:
    user = User.objects.create_user(username="ali", role=Role.STUDENT, center=center)

    assert user.must_change_password is True
    assert (user.is_staff, user.is_superuser) == (False, False)


def test_the_role_decides_admin_access_on_save(center: Center) -> None:
    user = make_user("ali", Role.TEACHER, center)
    user.is_staff = user.is_superuser = True

    user.save()
    user.refresh_from_db()

    assert (user.is_staff, user.is_superuser) == (False, False)


@pytest.mark.parametrize(
    ("role", "changes", "constraint"),
    [
        (Role.STUDENT, {"role": ""}, "accounts_user_role_valid"),
        (Role.STUDENT, {"role": "owner"}, "accounts_user_role_valid"),
        (Role.STUDENT, {"center": None}, "accounts_user_center_matches_role"),
        (Role.CENTER_ADMIN, {"is_staff": True}, "accounts_user_only_superadmin_is_staff"),
        (Role.TEACHER, {"is_superuser": True}, "accounts_user_only_superadmin_is_staff"),
        (Role.TEACHER, {"role": Role.STUDENT}, "accounts_user_directions_only_for_teachers"),
    ],
)
def test_the_database_refuses_a_broken_user(
    center: Center, role: Role, changes: dict[str, object], constraint: str
) -> None:
    user = make_user("ali", role, center)

    # update() skips save() and the forms: only the database stands in the way.
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        User.objects.filter(pk=user.pk).update(**changes)


def test_the_database_refuses_a_superadmin_with_a_centre(center: Center) -> None:
    superadmin = User.objects.create_superuser(username="erkin", password=PASSWORD)

    with (
        pytest.raises(IntegrityError, match="accounts_user_center_matches_role"),
        transaction.atomic(),
    ):
        User.objects.filter(pk=superadmin.pk).update(center=center)


def test_forms_get_the_rule_as_a_message() -> None:
    user = User(username="ali", role=Role.TEACHER)
    user.set_password(PASSWORD)

    with pytest.raises(ValidationError) as error:
        user.full_clean()

    assert "boshqa rollar uchun markazni tanlang" in str(error.value)


def test_unknown_direction_is_a_form_error(center: Center) -> None:
    user = User(username="ali", role=Role.TEACHER, center=center, directions=["mobile"])
    user.set_password(PASSWORD)

    with pytest.raises(ValidationError) as error:
        user.full_clean()

    assert "directions" in error.value.message_dict


def test_teacher_may_have_several_directions(center: Center) -> None:
    user = make_user("ali", Role.TEACHER, center, directions=[Direction.FLUTTER, "backend"])

    user.refresh_from_db()
    assert user.directions == ["flutter", "backend"]


def test_group_teacher_must_be_a_teacher_of_the_centre(world: World) -> None:
    for wrong in (world.b.teacher, world.a.student, world.a.admin):
        group = Group(center=world.a.center, name="Yangi", teacher=wrong)
        with pytest.raises(ValidationError) as error:
            group.full_clean()
        assert "teacher" in error.value.message_dict


def test_only_the_centres_students_join_a_group(world: World) -> None:
    group = world.a.group

    for wrong in (world.b.student, world.a.teacher):
        with pytest.raises(ValidationError, match="shu markazning oʻquvchisi emas"):
            group.add_students([world.a.other_student, wrong])

    assert set(group.students.all()) == {world.a.student}
    group.add_students([world.a.other_student])
    assert set(group.students.all()) == {world.a.student, world.a.other_student}


def test_group_names_are_unique_within_a_centre(world: World) -> None:
    # Both centres already have a "Flutter 1": names repeat across centres only.
    assert Group.objects.filter(name="Flutter 1").count() == 2

    with pytest.raises(IntegrityError), transaction.atomic():
        Group.objects.create(center=world.a.center, name="Flutter 1", teacher=world.a.teacher)


@pytest.mark.parametrize(
    ("last", "first", "shown"),
    [("Aliyev", "Vali", "Aliyev Vali"), ("", "Vali", "Vali"), ("", "", "vali01")],
)
def test_display_name_is_surname_first_or_the_login(last: str, first: str, shown: str) -> None:
    assert User(username="vali01", last_name=last, first_name=first).display_name == shown
