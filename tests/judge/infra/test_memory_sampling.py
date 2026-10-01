import pytest

from judge.infra.sandbox import _used_bytes

MB = 1024 * 1024


@pytest.mark.parametrize(
    ("memory", "used"),
    [
        pytest.param({"usage": 300 * MB, "stats": {"inactive_file": 100 * MB}}, 200 * MB, id="v2"),
        pytest.param(
            {"usage": 300 * MB, "stats": {"total_inactive_file": 50 * MB}}, 250 * MB, id="v1"
        ),
        pytest.param({"usage": 10 * MB}, 10 * MB, id="no-cache-stats"),
        pytest.param({}, 0, id="stopped-container"),
    ],
)
def test_memory_use_leaves_out_inactive_page_cache(memory: dict, used: int) -> None:
    assert _used_bytes(memory) == used
