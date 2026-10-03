from django.urls import path

from apps.ui import views

app_name = "ui"
urlpatterns = [
    path("", views.styleguide, name="styleguide"),
]
