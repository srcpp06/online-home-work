"""Profile pictures: whatever is uploaded becomes a small, clean WebP, or a clear refusal."""

import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.avatars import AVATAR_SIZE, MAX_UPLOAD_BYTES, avatar_from_upload


def picture(width: int, height: int, fmt: str = "PNG", **save: object) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (40, 90, 160)).save(buffer, fmt, **save)
    return SimpleUploadedFile(f"me.{fmt.lower()}", buffer.getvalue())


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "GIF"])
def test_any_common_picture_becomes_a_square_webp(fmt: str) -> None:
    data = avatar_from_upload(picture(640, 480, fmt))

    image = Image.open(io.BytesIO(data))
    assert (image.format, image.size) == ("WEBP", (AVATAR_SIZE, AVATAR_SIZE))


def test_camera_metadata_is_dropped() -> None:
    exif = Image.Exif()
    exif[0x0132] = "2026:10:03 12:00:00"  # DateTime
    exif[0x010F] = "Phone maker"  # Make

    data = avatar_from_upload(picture(300, 300, "JPEG", exif=exif.tobytes()))

    assert not Image.open(io.BytesIO(data)).getexif()


def test_a_file_that_is_not_a_picture_is_refused() -> None:
    with pytest.raises(ValidationError, match="rasm emas"):
        avatar_from_upload(SimpleUploadedFile("me.png", b"<?php echo 1; ?>"))


def test_a_large_file_is_refused() -> None:
    big = SimpleUploadedFile("me.png", b"0" * (MAX_UPLOAD_BYTES + 1))

    with pytest.raises(ValidationError, match="MB"):
        avatar_from_upload(big)


def test_a_huge_canvas_is_refused() -> None:
    """A tiny file can unpack into gigabytes (a decompression bomb)."""
    with pytest.raises(ValidationError, match="juda katta"):
        avatar_from_upload(picture(9000, 9000, "PNG", optimize=True))
