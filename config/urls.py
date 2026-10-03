from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ui/", include("apps.ui.urls")),
    path("", include("apps.tasks.urls")),
    path("", include("apps.accounts.urls")),
]
