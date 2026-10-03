"""Time limit of a task version (SPEC §3.3, step 5)."""

import math

SOLUTION_TIME_FACTOR = 2.5


def time_limit_s(solution_wall_ms: int, min_time_s: int, max_time_s: int) -> int:
    """clamp(ceil(solution_wall_s * 2.5), min, max): room for slower but correct solutions.

    The builder passes the teacher's solution judged in the finished (warm) image.
    """
    if solution_wall_ms < 0:
        raise ValueError(f"solution_wall_ms must be >= 0, got {solution_wall_ms}")
    wanted = math.ceil(solution_wall_ms * SOLUTION_TIME_FACTOR / 1000)
    return max(min_time_s, min(wanted, max_time_s))
