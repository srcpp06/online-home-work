"""Each person's own profile page, and profile pictures (Phase 1.5)."""

from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.access import get_for_user_or_404, visible_to
from apps.accounts.forms import ProfileForm
from apps.accounts.models import Group, User
from apps.accounts.stats import person_stats, recent_submissions


def profile(request: HttpRequest) -> HttpResponse:
    person = request.user
    form = ProfileForm(request.POST or None, request.FILES or None, instance=person)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil saqlandi.")
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile.html",
        {
            "person": person,
            "form": form,
            "stats": person_stats(person, person),
            "recent": recent_submissions(person, person),
            "groups": visible_to(Group, person)
            .filter(Q(students=person) | Q(teacher=person))
            .select_related("teacher")
            .distinct()
            .order_by("name"),
        },
        status=400 if request.method == "POST" else 200,
    )


def person_avatar(request: HttpRequest, pk: int) -> HttpResponse:
    """A picture leaves only to those who may see its person, never by a public URL."""
    person = get_for_user_or_404(User, request.user, pk=pk)
    if not person.avatar:
        raise Http404
    response = FileResponse(person.avatar.open("rb"), content_type="image/webp")
    # The URL carries the file's version (?v=), so a cached copy is never stale.
    response["Cache-Control"] = "private, max-age=86400"
    return response
