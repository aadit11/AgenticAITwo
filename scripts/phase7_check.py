"""Phase 7 check. Curl the live server and require trace and route before the answer."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HOST = "127.0.0.1"
PORT = 8765
BASE = f"http://{HOST}:{PORT}"
QUESTION = "What does PEP 8 say about imports?"


def curl(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["curl.exe", "-sS", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def wait_for_health(proc: subprocess.Popen) -> dict:
    last = ""
    for _ in range(40):
        if proc.poll() is not None:
            raise SystemExit(f"server exited early: {proc.stderr.read() if proc.stderr else ''}")
        result = curl([f"{BASE}/health"])
        last = result.stdout
        if result.returncode == 0 and last.startswith("{"):
            return json.loads(last)
        time.sleep(0.25)
    raise SystemExit(f"health did not come up: {last}")


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    events = []
    kind = ""
    for line in raw.splitlines():
        if line.startswith("event:"):
            kind = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and kind:
            events.append((kind, json.loads(line.split(":", 1)[1].strip())))
            kind = ""
    return events


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    body = ROOT / "eval" / "_phase7_body.json"
    body.write_text(json.dumps({"query": QUESTION, "history": []}), encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        health = wait_for_health(proc)
        print("HEALTH", json.dumps(health), flush=True)
        if not health.get("ok") or int(health.get("chroma_count") or 0) <= 0:
            raise SystemExit(f"health did not report a corpus: {health}")
        if health.get("providers_configured") is not True:
            raise SystemExit(f"providers are not configured: {health}")
        blob = json.dumps(health)
        if any(marker in blob for marker in ("sk-", "AIza", "tvly-", "tavilyApiKey")):
            raise SystemExit("health returned a key")

        page = curl([f"{BASE}/"])
        if "PEP briefing desk" not in page.stdout:
            raise SystemExit("GET / did not serve the static page")
        script = curl([f"{BASE}/static/app.js"])
        if "Phase 8" not in script.stdout:
            raise SystemExit("GET /static/app.js did not serve the script")

        empty = curl(
            ["-o", "-", "-w", "%{http_code}", "-X", "POST", f"{BASE}/api/chat", "-H", "Content-Type: application/json", "--data-binary", '{"query":"  ","history":[]}']
        )
        if not empty.stdout.strip().endswith("400"):
            raise SystemExit(f"empty query should be rejected, got {empty.stdout!r} {empty.stderr!r}")

        started = time.time()
        chat = curl(
            ["-N", "--max-time", "180", "-X", "POST", f"{BASE}/api/chat", "-H", "Content-Type: application/json", "--data-binary", f"@{body}"],
            timeout=200,
        )
        elapsed = round(time.time() - started, 1)
        raw = chat.stdout
        if not raw.lstrip().startswith(": ping"):
            raise SystemExit(f"stream did not start with a ping comment: {raw[:200]!r}")
        events = parse_sse(raw)
        kinds = [kind for kind, _ in events]
        print("EVENTS", " ".join(kinds), flush=True)
        print(f"elapsed {elapsed}s", flush=True)
        if "trace" not in kinds or "route" not in kinds or "token" not in kinds or kinds[-1] != "done":
            raise SystemExit(f"missing stream events: {kinds}")
        first_trace = kinds.index("trace")
        first_route = kinds.index("route")
        first_token = kinds.index("token")
        if first_trace >= first_token or first_route >= first_token:
            raise SystemExit("trace and route did not arrive before the answer tokens")
        answer = "".join(payload.get("text", "") for kind, payload in events if kind == "token").strip()
        print("ANSWER", answer[:500], flush=True)
        if not answer:
            raise SystemExit("the stream finished without answer text")
        route = next(payload for kind, payload in events if kind == "route")
        for field in ("agent", "provider", "model", "dimension", "reason"):
            if not route.get(field):
                raise SystemExit(f"route event is missing {field}: {route}")
        destination = ROOT / "eval" / "phase7_runs.json"
        destination.write_text(
            json.dumps(
                {
                    "question": QUESTION,
                    "health": health,
                    "events": kinds,
                    "elapsed_seconds": elapsed,
                    "answer": answer,
                    "first_route": route,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {destination}", flush=True)
    finally:
        body.unlink(missing_ok=True)
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
