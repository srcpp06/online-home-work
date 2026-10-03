from django.contrib import admin

from apps.tasks.models import Assignment, RunnerProfile, Task, TaskVersion


@admin.register(RunnerProfile)
class RunnerProfileAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "direction", "lane", "is_active")
    list_filter = ("direction", "lane", "is_active")


class TaskVersionInline(admin.TabularInline):
    model = TaskVersion
    fields = ("number", "status", "time_limit_s", "image_tag", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "center", "author", "profile", "published_version", "is_archived")
    list_filter = ("center", "profile", "is_archived")
    search_fields = ("title",)
    raw_id_fields = ("author", "published_version")
    inlines = (TaskVersionInline,)


@admin.register(TaskVersion)
class TaskVersionAdmin(admin.ModelAdmin):
    list_display = ("task", "number", "status", "time_limit_s", "created_at")
    list_filter = ("status",)
    readonly_fields = ("sha256", "image_tag", "manifest", "import_rules", "build_log")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("task", "group", "opens_at", "deadline", "allow_late", "max_attempts")
    list_filter = ("group__center",)
