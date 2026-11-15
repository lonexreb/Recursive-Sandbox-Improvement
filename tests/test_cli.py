import json

import pytest

from rsi_sandbox import cli
from rsi_sandbox.study import StudySpec


def test_study_cli_loads_preregistered_spec_and_writes_result(
    tmp_path, monkeypatch, capsys
) -> None:
    spec_path = tmp_path / "study.json"
    result_path = tmp_path / "result.json"
    series_path = tmp_path / "series.csv"
    catalog_path = tmp_path / "catalog.csv"
    raw_spec = {
        "folds": [
            {
                "train": ["2026-01-01"],
                "validation": ["2026-01-08"],
                "heldout": ["2026-01-15"],
                "horizons": [1, 3, 7],
                "embargo_days": 7,
            }
        ],
        "seeds": [7],
        "generations": 1,
        "candidates_per_generation": 1,
        "min_skill_gain": 0.002,
        "max_coverage_regression": 0.05,
    }
    spec_path.write_text(json.dumps(raw_spec))
    monkeypatch.setattr(cli, "load_series_file", lambda *args: "dataset")
    monkeypatch.setattr(cli, "LocalExecutor", lambda timeout: ("local", timeout))

    def fake_run_study(dataset, executor, spec):
        assert dataset == "dataset"
        assert executor == ("local", 60)
        assert isinstance(spec, StudySpec)
        assert spec.sha256 == StudySpec.from_dict(raw_spec).sha256
        return {
            "analysis": {
                "valid": True,
                "recursive_minus_control": {
                    "mean": 0.125,
                    "p_value_two_sided": 0.03125,
                },
            }
        }

    monkeypatch.setattr(cli, "run_study", fake_run_study)
    status = cli.main(
        [
            "study",
            "--series-file",
            str(series_path),
            "--catalog",
            str(catalog_path),
            "--spec",
            str(spec_path),
            "--out",
            str(result_path),
        ]
    )

    assert status == 0
    assert json.loads(result_path.read_text())["analysis"]["valid"] is True
    assert "recursive-control mean=+0.125000" in capsys.readouterr().out


def test_study_cli_requires_catalog_with_series_file(tmp_path) -> None:
    with pytest.raises(SystemExit, match="--catalog is required"):
        cli.main(
            [
                "study",
                "--series-file",
                str(tmp_path / "series.csv"),
                "--spec",
                str(tmp_path / "study.json"),
                "--out",
                str(tmp_path / "result.json"),
            ]
        )
