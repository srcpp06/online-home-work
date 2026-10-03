from django.contrib import admin

from apps.submissions.models import Submission, SubmissionTestResult


class ResultInline(admin.TabularInline):
    model = SubmissionTestResult
    fields = ("index", "name", "visibility", "status", "duration_ms", "message")
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("pk", "student", "assignment", "status", "verdict", "created_at")
    list_filter = ("status", "verdict")
    raw_id_fields = ("student", "assignment", "task_version")
    readonly_fields = ("sha256", "internal_log", "public_message")
    inlines = (ResultInline,)
