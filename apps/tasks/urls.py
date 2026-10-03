from django.urls import path

from apps.tasks import views

app_name = "tasks"
urlpatterns = [
    path("tasks/", views.task_list, name="tasks"),
    path("tasks/add/", views.task_create, name="task_add"),
    path("tasks/preview/", views.preview, name="preview"),
    path("tasks/<int:pk>/", views.task_detail, name="task"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/archive/", views.task_archive, name="task_archive"),
    path("tasks/<int:pk>/assign/", views.assign, name="assign"),
    path("tasks/<int:pk>/versions/add/", views.version_create, name="version_add"),
    path("tasks/<int:pk>/versions/<int:number>/", views.version_detail, name="version"),
    path(
        "tasks/<int:pk>/versions/<int:number>/status/",
        views.version_status,
        name="version_status",
    ),
    path(
        "tasks/<int:pk>/versions/<int:number>/publish/",
        views.version_publish,
        name="version_publish",
    ),
    path(
        "tasks/<int:pk>/versions/<int:number>/package/",
        views.version_package,
        name="version_package",
    ),
    path(
        "tasks/<int:pk>/versions/<int:number>/starter/",
        views.version_starter,
        name="version_starter",
    ),
]
