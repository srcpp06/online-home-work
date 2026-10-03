from django.contrib import admin

from apps.system.models import Job, WorkerNode


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("pk", "kind", "lane", "status", "attempts", "worker_node", "created_at")
    list_filter = ("status", "kind", "lane")
    raw_id_fields = ("task_version", "submission")


@admin.register(WorkerNode)
class WorkerNodeAdmin(admin.ModelAdmin):
    list_display = ("name", "arch", "slots", "last_heartbeat")
