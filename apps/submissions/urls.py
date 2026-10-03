from django.urls import path

from apps.submissions import views

app_name = "submissions"
urlpatterns = [
    path("assignments/", views.my_assignments, name="assignments"),
    path("assignments/<int:pk>/", views.assignment_detail, name="assignment"),
    path("assignments/<int:pk>/starter/", views.assignment_starter, name="assignment_starter"),
    path("submissions/<int:pk>/", views.submission_detail, name="submission"),
    path("submissions/<int:pk>/live/", views.submission_live, name="submission_live"),
    path("submissions/<int:pk>/rejudge/", views.submission_rejudge, name="submission_rejudge"),
]
