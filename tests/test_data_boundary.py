from pathlib import Path

from rsi_sandbox.data import Dataset, Point, day_of
from rsi_sandbox.models import CandidateConfig


def test_request_never_contains_future_truth() -> None:
    origin = "2026-01-05"
    dataset = Dataset(
        series={
            "gpu": [
                Point(day=day_of("2026-01-04"), value=1.0),
                Point(day=day_of("2026-01-05"), value=1.1),
                Point(day=day_of("2026-01-06"), value=99.0),
            ]
        },
        source_path=Path("fixture.csv"),
        source_sha256="fixture",
        cutoff="2026-01-05",
        scope="test",
    )

    request = dataset.history_request(origin, (1, 3, 7), CandidateConfig(name="flat").to_dict())

    assert request["series"]["gpu"] == [["2026-01-04", 1.0], ["2026-01-05", 1.1]]
    assert "truth" not in request
