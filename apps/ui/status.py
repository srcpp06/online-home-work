"""How a submission's state is shown: words, icon and tone (docs/UI.md §5, §9).

A status is never colour alone: every entry has the words and an icon too.
"""

from dataclasses import dataclass
from enum import StrEnum


class Tone(StrEnum):
    PASS = "pass"  # noqa: S105 -- a tone, not a password
    FAIL = "fail"
    WARN = "warn"
    INK = "ink"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class StatusLook:
    label: str
    icon: str  # a file in apps/ui/icons
    tone: Tone


# Keys are submission states and judge verdicts (judge.core.verdict.Verdict).
STATUSES: dict[str, StatusLook] = {
    "queued": StatusLook("Navbatda", "clock", Tone.NEUTRAL),
    "running": StatusLook("Tekshirilmoqda", "loader-circle", Tone.INK),
    "accepted": StatusLook("Qabul qilindi", "check", Tone.PASS),
    "wrong_answer": StatusLook("N-testda xato", "x", Tone.FAIL),
    "compile_error": StatusLook("Kompilyatsiya xatosi", "file-x", Tone.FAIL),
    "time_limit": StatusLook("Vaqt limiti oshdi", "timer-off", Tone.WARN),
    "memory_limit": StatusLook("Xotira limiti oshdi", "memory-stick", Tone.WARN),
    "runtime_error": StatusLook("Bajarilishda xato", "triangle-alert", Tone.FAIL),
    "rejected": StatusLook("Rad etildi", "ban", Tone.FAIL),
    "system_error": StatusLook(
        "Tizim xatosi — urinish hisoblanmaydi", "server-crash", Tone.NEUTRAL
    ),
}


def status_look(status: str, failed_test: int | None = None) -> StatusLook:
    """The look of a status; wrong_answer names the failed test ("3-testda xato")."""
    look = STATUSES[status]
    if status == "wrong_answer":
        label = f"{failed_test}-testda xato" if failed_test else "Testda xato"
        return StatusLook(label, look.icon, look.tone)
    return look
