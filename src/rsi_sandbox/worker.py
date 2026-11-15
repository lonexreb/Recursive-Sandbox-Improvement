from __future__ import annotations

import argparse
import base64
import json
import sys
import zlib

from .forecast import forecast_request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--request-zlib-b64")
    args = parser.parse_args(argv)
    try:
        if args.request_zlib_b64:
            compressed = base64.urlsafe_b64decode(args.request_zlib_b64.encode())
            request = json.loads(zlib.decompress(compressed))
        else:
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
