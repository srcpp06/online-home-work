"""Profile pictures (Phase 1.5): every upload is decoded and drawn again as a small WebP.

Re-encoding is the safety: whatever the file claimed to be, only pixels survive. Camera
metadata (location, device) is dropped, the size is fixed, and files that are not
pictures or that would unpack into huge images are refused before decoding.
"""

import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_SIZE = 256  # pixels, square
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000  # a 6000 x 6000 photo still fits; bombs don't
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "GIF"})


def avatar_from_upload(upload: UploadedFile) -> bytes:
    if (upload.size or 0) > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"Rasm hajmi {MAX_UPLOAD_BYTES // (1024 * 1024)} MB dan oshmasin. "
            "Kichikroq rasm tanlang."
        )
    upload.seek(0)
    try:
        with Image.open(upload) as image:
            if image.format not in ALLOWED_FORMATS:
                raise UnidentifiedImageError
            if image.width * image.height > MAX_PIXELS:
                raise ValidationError(
                    "Rasm oʻlchami juda katta. Uni kichraytirib (masalan, 1000 piksel) qayta "
                    "yuklang."
                )
            image.seek(0)
            picture = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError(
            "Bu fayl rasm emas yoki buzilgan. JPG, PNG yoki WebP rasm tanlang."
        ) from None
    square = ImageOps.fit(picture, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    square.save(buffer, "WEBP", quality=85)
    return buffer.getvalue()
