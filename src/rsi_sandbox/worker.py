from __future__ import annotations

import json
import sys

from .forecast import forecast_request


def main() -> int:
    try:
        request = json.load(sys.stdin)
        rows = [row.to_dict() for row in forecast_request(request)]
        json.dump({"schema_version": 1, "forecasts": rows}, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # the orchestrator records the typed failure
        print(f"worker refused request: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
