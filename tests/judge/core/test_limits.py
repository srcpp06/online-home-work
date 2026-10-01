import pytest

from judge.core.limits import time_limit_s


@pytest.mark.parametrize(
    ("solution_wall_ms", "expected"),
    [
        pytest.param(4_000, 20, id="fast-solution-gets-the-minimum"),
        pytest.param(10_000, 25, id="two-and-a-half-times"),
        pytest.param(10_001, 26, id="rounds-up"),
        pytest.param(100_000, 120, id="slow-solution-gets-the-maximum"),
        pytest.param(0, 20, id="zero"),
    ],
)
def test_time_limit_is_clamped_solution_time(solution_wall_ms: int, expected: int) -> None:
    assert time_limit_s(solution_wall_ms, min_time_s=20, max_time_s=120) == expected


def test_negative_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="solution_wall_ms"):
        time_limit_s(-1, min_time_s=20, max_time_s=120)
