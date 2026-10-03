from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts.models import Role
from apps.accounts.views import auth, groups, people

app_name = "accounts"
urlpatterns = [
    path("", auth.home, name="home"),
    path("login/", auth.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password/", auth.PasswordChangeView.as_view(), name="password_change"),
    path("teachers/", people.people_list, {"role": Role.TEACHER}, name="teachers"),
    path("teachers/add/", people.person_create, {"role": Role.TEACHER}, name="teacher_add"),
    path("students/", people.people_list, {"role": Role.STUDENT}, name="students"),
    path("students/add/", people.person_create, {"role": Role.STUDENT}, name="student_add"),
    path("managers/", people.people_list, {"role": Role.CENTER_MANAGER}, name="managers"),
    path("managers/add/", people.person_create, {"role": Role.CENTER_MANAGER}, name="manager_add"),
    path("people/<int:pk>/", people.person_detail, name="person"),
    path("people/<int:pk>/edit/", people.person_edit, name="person_edit"),
    path("people/<int:pk>/password/", people.person_reset_password, name="person_password"),
    path("people/<int:pk>/password/new/", people.person_new_password, name="person_new_password"),
    path("people/<int:pk>/delete/", people.person_delete, name="person_delete"),
    path("groups/", groups.group_list, name="groups"),
    path("groups/add/", groups.group_create, name="group_add"),
    path("groups/<int:pk>/", groups.group_detail, name="group"),
    path("groups/<int:pk>/edit/", groups.group_edit, name="group_edit"),
    path("groups/<int:pk>/delete/", groups.group_delete, name="group_delete"),
]
