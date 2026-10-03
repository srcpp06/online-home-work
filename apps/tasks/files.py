"""Uploaded files leave only through views that checked the viewer, never a public URL
(CLAUDE.md, "Hech qachon")."""

from django.db.models.fields.files import FieldFile
from django.http import FileResponse, Http404


def private_download(file: FieldFile, name: str) -> FileResponse:
    if not file:
        raise Http404
    response = FileResponse(file.open("rb"), as_attachment=True, filename=name)
    response["Cache-Control"] = "private, no-store"
    return response
