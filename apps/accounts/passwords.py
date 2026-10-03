"""Temporary passwords that an admin reads out or writes down for a new user."""

import secrets

# No 0/o, 1/l/i: easy to copy from paper. 12 characters give about 59 bits.
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def temporary_password() -> str:
    """Like "k7mq-4xpw-9hdz"; the user replaces it at the first sign-in."""
    chars = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return "-".join(chars[i : i + 4] for i in range(0, 12, 4))
