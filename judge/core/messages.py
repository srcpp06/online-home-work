"""Texts the student reads (SPEC §3.8): a rejection's reason or a compile error."""

MAX_PUBLIC_MESSAGE = 2000


def cut(text: str, limit: int = MAX_PUBLIC_MESSAGE) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."
