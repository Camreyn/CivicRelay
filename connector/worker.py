"""One bounded JSON request per child process; no secrets in argv or errors."""
import json
import sys

from connector import safe_dispatch

MAX_REQUEST = 300000


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            raise ValueError()
        request = json.loads(raw)
        if not isinstance(request, dict) or set(request) != {"tool", "arguments"} or not isinstance(request["tool"], str):
            raise ValueError()
        result = safe_dispatch(request["tool"], request["arguments"])
    except Exception:
        result = {"ok": False, "error": "Malformed or oversized connector request."}
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
