"""Teacher task pages: create, follow the build, publish, assign (docs/UI.md §6)."""

import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.accounts.models import Direction, Group, Role, User
from apps.system.models import Job
from apps.tasks.models import Assignment, Task, TaskVersion
from judge.env import REPO_ROOT
from tests.apps.world import World, make_task, make_user, zip_folder

pytestmark = pytest.mark.django_db
CART = REPO_ROOT / "examples" / "dart-cart" / "task"


def as_(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def package(data: bytes | None = None) -> SimpleUploadedFile:
    return SimpleUploadedFile("cart.zip", zip_folder(CART) if data is None else data)


def create(client: Client, **changes: object) -> object:
    data = {
        "profile": "",
        "title": "Savat",
        "statement_md": "# Savat\n\nJami narxni hisoblang.",
        "package": package(),
        **changes,
    }
    return client.post("/tasks/add/", data)


@pytest.fixture
def dart_id(world: World) -> int:
    from apps.tasks.models import RunnerProfile

    return RunnerProfile.objects.get(slug="dart").pk


class TestCreating:
    def test_a_good_package_makes_a_task_a_version_and_a_build_job(
        self, client: Client, world: World, dart_id: int
    ) -> None:
        as_(client, world.a.teacher)

        response = create(client, profile=dart_id)

        task = Task.objects.get(title="Savat")
        version = task.versions.get()
        assert response["Location"] == f"/tasks/{task.pk}/versions/1/"
        assert (task.center, task.author, version.status) == (
            world.a.center,
            world.a.teacher,
            TaskVersion.Status.BUILDING,
        )
        job = Job.objects.get(task_version=version)
        assert (job.kind, job.lane, job.status) == ("build", "fast", "queued")
        with zipfile.ZipFile(version.starter.open("rb")) as starter:
            names = starter.namelist()
        assert "cart/lib/cart.dart" in names
        assert not any("solution" in n or "hidden" in n or "ohw.yaml" in n for n in names)

    def test_not_a_zip_is_an_error_and_nothing_is_made(
        self, client: Client, world: World, dart_id: int
    ) -> None:
        as_(client, world.a.teacher)

        response = create(client, profile=dart_id, package=package(b"not a zip"))

        assert response.status_code == 200
        assert not Task.objects.filter(title="Savat").exists()
        assert not Job.objects.exists()

    def test_missing_hidden_tests_are_listed(
        self, client: Client, world: World, dart_id: int
    ) -> None:
        as_(client, world.a.teacher)

        response = create(
            client, profile=dart_id, package=package(zip_folder(CART, leave_out="test/hidden"))
        )

        html = response.content.decode()
        assert "test/hidden papkasida test fayli" in html
        assert "<code>test/hidden</code> — topilmadi" in html
        assert not Task.objects.filter(title="Savat").exists()

    def test_teacher_picks_only_profiles_of_their_directions(
        self, client: Client, world: World, dart_id: int
    ) -> None:
        backend = make_user("bek", Role.TEACHER, world.a.center, directions=[Direction.BACKEND])
        as_(client, backend)

        response = create(client, profile=dart_id)

        assert response.status_code == 200
        assert not Task.objects.filter(title="Savat").exists()


class TestBuildPage:
    def test_polling_stops_once_the_build_is_over(self, client: Client, world: World) -> None:
        a = world.a
        url = f"/tasks/{a.task.pk}/versions/1/status/"
        as_(client, a.teacher)

        assert client.get(url).status_code == 286
        TaskVersion.objects.filter(pk=a.version.pk).update(status="building")
        building = client.get(url)
        assert building.status_code == 200
        assert 'hx-trigger="every 1s"' in building.content.decode()

    def test_build_log_is_for_the_author_only(self, client: Client, world: World) -> None:
        a = world.a
        TaskVersion.objects.filter(pk=a.version.pk).update(build_log="hidden test source")

        assert (
            "hidden test source"
            in as_(client, a.teacher).get(f"/tasks/{a.task.pk}/versions/1/").content.decode()
        )
        for viewer in (a.manager, a.admin):
            page = as_(client, viewer).get(f"/tasks/{a.task.pk}/versions/1/").content.decode()
            assert "hidden test source" not in page
            assert "Savat boʻsh" in page  # test names are fine to see


class TestPublishing:
    def test_author_publishes_with_a_time_limit(self, client: Client, world: World) -> None:
        a = world.a
        task, version = make_task(a.teacher, "Yangi", publish=False)
        as_(client, a.teacher)

        response = client.post(f"/tasks/{task.pk}/versions/1/publish/", {"time_limit_s": 20})

        assert response["Location"] == f"/tasks/{task.pk}/"
        task.refresh_from_db()
        version.refresh_from_db()
        assert (task.published_version, version.time_limit_s) == (version, 20)

    @pytest.mark.parametrize("seconds", [5, 500])
    def test_limit_stays_within_the_profile(
        self, client: Client, world: World, seconds: int
    ) -> None:
        a = world.a
        task, _ = make_task(a.teacher, "Yangi", publish=False)
        as_(client, a.teacher)

        response = client.post(f"/tasks/{task.pk}/versions/1/publish/", {"time_limit_s": seconds})

        assert response.status_code == 400
        task.refresh_from_db()
        assert task.published_version is None

    def test_a_version_still_building_is_not_published(self, client: Client, world: World) -> None:
        a = world.a
        task, version = make_task(a.teacher, "Yangi", publish=False)
        TaskVersion.objects.filter(pk=version.pk).update(status="building")
        as_(client, a.teacher)

        client.post(f"/tasks/{task.pk}/versions/1/publish/", {"time_limit_s": 20})

        task.refresh_from_db()
        assert task.published_version is None


class TestWhoMayDoWhat:
    def test_manager_and_admin_look_without_changing(self, client: Client, world: World) -> None:
        a = world.a
        for viewer in (a.manager, a.admin):
            as_(client, viewer)
            listing = client.get("/tasks/").content.decode()
            assert "Savat hisobi" in listing
            assert "Topshiriq yaratish" not in listing
            assert client.get("/tasks/add/").status_code == 403
            assert client.get(f"/tasks/{a.task.pk}/versions/1/package/").status_code == 403
            assert client.get(f"/tasks/{a.task.pk}/versions/1/starter/").status_code == 200

    def test_students_have_no_task_pages(self, client: Client, world: World) -> None:
        as_(client, world.a.student)

        assert client.get("/tasks/").status_code == 403
        assert client.get(f"/tasks/{world.a.task.pk}/").status_code == 403

    def test_another_teachers_task_is_404(self, client: Client, world: World) -> None:
        assert (
            as_(client, world.a.other_teacher).get(f"/tasks/{world.a.task.pk}/").status_code == 404
        )

    def test_package_download_is_private(self, client: Client, world: World) -> None:
        response = as_(client, world.a.teacher).get(f"/tasks/{world.a.task.pk}/versions/1/package/")

        assert response.status_code == 200
        assert response["Content-Disposition"].startswith("attachment;")
        assert "no-store" in response["Cache-Control"]


class TestAssigning:
    def test_teacher_assigns_to_a_group_once(self, client: Client, world: World) -> None:
        a = world.a
        evening = Group.objects.create(center=a.center, name="Kechki", teacher=a.teacher)
        as_(client, a.teacher)

        page = client.get(f"/tasks/{a.task.pk}/assign/").content.decode()
        response = client.post(
            f"/tasks/{a.task.pk}/assign/",
            {
                "group": evening.pk,
                "opens_at": "2026-10-05T09:00",
                "deadline": "2026-10-12T18:00",
                "max_attempts": 5,
            },
        )

        assert "Flutter 1" not in page  # already assigned there
        assert response["Location"] == f"/tasks/{a.task.pk}/"
        assignment = Assignment.objects.get(group=evening)
        assert (assignment.max_attempts, assignment.allow_late) == (5, False)
        assert assignment.deadline.hour == 13  # 18:00 in Tashkent is 13:00 UTC

    def test_deadline_before_opening_is_refused(self, client: Client, world: World) -> None:
        a = world.a
        evening = Group.objects.create(center=a.center, name="Kechki", teacher=a.teacher)
        as_(client, a.teacher)

        response = client.post(
            f"/tasks/{a.task.pk}/assign/",
            {"group": evening.pk, "opens_at": "2026-10-12T09:00", "deadline": "2026-10-05T18:00"},
        )

        assert response.status_code == 200
        assert not Assignment.objects.filter(group=evening).exists()

    def test_an_unpublished_task_is_not_assigned(self, client: Client, world: World) -> None:
        task, _ = make_task(world.a.teacher, "Qoralama", publish=False)

        response = as_(client, world.a.teacher).get(f"/tasks/{task.pk}/assign/", follow=True)

        assert "Avval topshiriqning tayyor versiyasini" in response.content.decode()


def test_preview_is_sanitized(client: Client, world: World) -> None:
    html = (
        as_(client, world.a.teacher)
        .post("/tasks/preview/", {"statement_md": "**Savat** <script>alert(1)</script>"})
        .content.decode()
    )

    assert "<strong>Savat</strong>" in html
    assert "<script>" not in html


def test_archived_tasks_leave_students_pages(client: Client, world: World) -> None:
    a = world.a
    as_(client, a.teacher)

    client.post(f"/tasks/{a.task.pk}/archive/")

    a.task.refresh_from_db()
    assert a.task.is_archived
    assert not Assignment.objects.for_user(a.student).exists()


def test_starter_folder_is_named_after_the_package(world: World) -> None:
    with zipfile.ZipFile(io.BytesIO(zip_folder(CART))) as archive:
        assert "pubspec.yaml" in archive.namelist()
